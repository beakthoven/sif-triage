"""Build-time explanation pre-warming for the full-feature image.

Walks every report in the seeded demo DB and generates its explanation
through the app's own build_explanation (app/explain.py), writing into the
same `precomputed` table the serving path reads. Cache keys therefore match
the live path exactly (text + model_version + threshold +
EXPLANATION_VERSION — see app/explain.py explain_key), so judges opening
the 4,548-row register get the cached LLM rewording instantly instead of a
~30 s cold reword per report.

Runs inside the Docker build with `ollama serve` already up (the Dockerfile
RUN step starts it, pulls qwen3:4b, then invokes this script). SIF_DB_PATH
points at the demo seed copy; the warmed DB is tarred into the image and
substituted for the pristine seed by deploy/entrypoint-ollama.sh.

Idempotent: rows whose key is already cached are skipped, so a re-run after
a partial build continues instead of restarting.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.explain import build_explanation  # noqa: E402
from app.schemas import PredictionOut  # noqa: E402
from app.storage import SQLiteStorage  # noqa: E402


def main() -> int:
    db_path = os.environ.get("SIF_DB_PATH")
    if not db_path or not Path(db_path).exists():
        print(f"[precompute] SIF_DB_PATH missing or not found: {db_path!r}",
              file=sys.stderr)
        return 1

    storage = SQLiteStorage(Path(db_path))
    threshold = float(os.environ.get("SIF_FLAG_THRESHOLD_OVERRIDE", "0.5647"))
    model_version = os.environ.get(
        "SIF_MODEL_VERSION_OVERRIDE",
        "onnx:masked-v2/sif_multitask_int8.onnx",
    )

    rows = storage._conn.execute(
        "SELECT r.id, r.text, p.rule_probs, p.well_control, p.evidence_spans,"
        "       p.gate_states, p.sif_score, p.score_spread, p.n_variants,"
        "       p.variant_scores, p.verdict_stability"
        "  FROM reports r JOIN predictions p ON p.report_id = r.id"
    ).fetchall()

    total = len(rows)
    done = 0
    skipped = 0
    failed = 0
    t0 = time.time()
    for rid, text, rule_probs, well_control, spans, gates, score, spread, n_var, v_scores, v_stab in rows:
        import json
        pred = PredictionOut(
            sif_score=score,
            rule_probs=json.loads(rule_probs),
            well_control=bool(well_control),
            evidence_spans=json.loads(spans) if spans else [],
            gate_states=json.loads(gates) if gates else [],
            model_version=model_version,
            score_spread=spread,
            n_variants=n_var,
            variant_scores=json.loads(v_scores) if v_scores else [],
            verdict_stability=v_stab,
        )
        try:
            from app.explain import explain_key
            if storage.load_precomputed(
                explain_key(text, model_version, threshold)
            ) is not None:
                skipped += 1
                continue
            build_explanation(
                pred, text, storage,
                use_llm=True, threshold=threshold,
            )
            done += 1
        except Exception as exc:  # template fallback is the designed floor
            failed += 1
            print(f"[precompute] row {rid} failed ({exc}); template stands",
                  file=sys.stderr)
        if (done + skipped) % 250 == 0:
            rate = (done + skipped) / max(time.time() - t0, 1)
            print(f"[precompute] {done + skipped}/{total}"
                  f" ({rate:.1f}/s, {failed} failed)", flush=True)

    print(
        f"[precompute] complete: {done} generated, {skipped} already cached,"
        f" {failed} failed (template fallback), {total} rows,"
        f" {time.time() - t0:.0f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
