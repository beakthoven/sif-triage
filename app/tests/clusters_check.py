"""Cluster and rule-cue endpoint check; uses a throwaway DB and server.

Run: .venv/bin/python app/tests/clusters_check.py
Default port: an OS-assigned free local port; set SIF_TEST_PORT to override.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

HOT_TEXT = "Welding was in progress near the open drain."
HOT_TWIN = "Welding was in progress near the open drain!"
UNIQUE_TEXTS = (
    "Driver secured the truck after the seat belt alarm started flashing.",
    "Technician entered a confined tank before completing the atmosphere test.",
    "A crane operator inspected a damaged sling beside the storage yard.",
)
RELEASE_TEXT = (
    "The pressure valve suddenly ruptured, causing an explosion and flying fragments."
)
RULE_KEYS = {
    "confined_space", "driving", "energy_isolation", "hot_work", "line_of_fire",
    "safe_mechanical_lifting", "working_at_height",
}


def _port() -> int:
    configured = os.environ.get("SIF_TEST_PORT")
    if configured:
        return int(configured)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def main() -> int:
    port = _port()
    base = f"http://127.0.0.1:{port}/api"
    with tempfile.TemporaryDirectory(prefix="sif-clusters-") as temp_dir:
        env = dict(
            os.environ,
            SIF_DB_PATH=str(Path(temp_dir) / "clusters.db"),
            SIF_MODEL_PATH=str(REPO_ROOT / "artifacts/models/masked-v2/sif_multitask_int8.onnx"),
            SIF_TOKENIZER_PATH=str(REPO_ROOT / "artifacts/models/masked-v2/tokenizer/tokenizer.json"),
            SIF_EXPLAIN_LLM="0",
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(port)],
            cwd=REPO_ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(150):
                if server.poll() is not None:
                    raise AssertionError(f"uvicorn exited early with {server.returncode}")
                try:
                    status, _ = _request(base, "GET", "/health")
                    if status == 200:
                        break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.2)
            else:
                raise AssertionError(f"server did not start on 127.0.0.1:{port}")

            print("[1] empty-ish clusters response shape")
            status, empty = _request(base, "GET", "/clusters")
            _check(status == 200, "GET /clusters -> 200")
            _check(set(empty) == {"threshold", "n_scored", "n_skipped", "dim", "n_clusters", "n_members", "clusters"},
                   "response has the fixed top-level contract")
            _check(empty["threshold"] == 0.91 and empty["n_scored"] == 0
                   and empty["n_skipped"] == 0 and empty["dim"] == 0
                   and empty["n_clusters"] == 0 and empty["n_members"] == 0
                   and empty["clusters"] == [], "empty DB returns zero counts and no groups")

            print("[2] pair-only star clustering and rule cue hits")
            stored_ids: dict[str, int] = {}
            for text in (HOT_TEXT, HOT_TWIN, *UNIQUE_TEXTS, RELEASE_TEXT):
                status, prediction = _request(base, "POST", "/classify?persist=1", {"text": text})
                _check(status == 200, "persisting classify -> 200")
                hits = prediction.get("rule_cue_hits")
                _check(isinstance(hits, dict) and set(hits) == RULE_KEYS,
                       "classify includes exactly the seven rule cue flags")
                stored_ids[text] = prediction["report_id"]

            pair = (HOT_TEXT, HOT_TWIN)
            _check(stored_ids[HOT_TEXT] < stored_ids[HOT_TWIN], "lower report id is the pair founder")
            status, clusters = _request(base, "GET", "/clusters")
            _check(status == 200 and clusters["n_scored"] == 6 and clusters["n_skipped"] == 0
                   and clusters["dim"] == 384, "cluster counts disclose six 384-d vectors")
            _check(clusters["n_clusters"] == 1 and clusters["n_members"] == 2,
                   "only the near-identical pair forms a duplicate group")
            group = clusters["clusters"][0]
            expected_pair = [stored_ids[text] for text in pair]
            _check(group["member_ids"] == expected_pair and group["n"] == 2,
                   "pair members are ascending and no unique text joined")
            _check(group["exemplar_id"] == expected_pair[0] and group["max_cos"] >= 0.91,
                   "unreviewed exemplar is the lower id and cosine clears threshold")
            _check(all(stored_ids[text] not in group["member_ids"] for text in UNIQUE_TEXTS + (RELEASE_TEXT,)),
                   "the three unique texts and cue probe are outside all duplicate groups")

            print("[3] review-aware exemplar preference")
            reviewed_id = expected_pair[1]
            status, _ = _request(base, "POST", "/review", {
                "report_id": reviewed_id, "field": "sif_label",
                "new_value": "sif_potential", "labeler": "clusters_check",
            })
            _check(status == 201, "review override stored on higher-id pair member")
            status, reviewed_clusters = _request(base, "GET", "/clusters")
            _check(status == 200, "clusters refresh after review")
            reviewed_group = reviewed_clusters["clusters"][0]
            _check(reviewed_group["reviewed_member_ids"] == [reviewed_id]
                   and reviewed_group["exemplar_id"] == reviewed_id,
                   "reviewed member is disclosed and becomes exemplar")

            print("[4] cue disclosure on direct and stored reads")
            for text, cue, expected in ((HOT_TEXT, "hot_work", True),
                                        (RELEASE_TEXT, "hot_work", False),
                                        (RELEASE_TEXT, "line_of_fire", True)):
                status, prediction = _request(base, "POST", "/classify", {"text": text})
                _check(status == 200 and prediction["rule_cue_hits"][cue] is expected,
                       f"classify cue {cue}={expected} for test narrative")
                rid = stored_ids[text]
                status, report = _request(base, "GET", f"/reports/{rid}")
                _check(status == 200 and report["prediction"]["rule_cue_hits"][cue] is expected,
                       f"stored report cue {cue}={expected} is reconstituted")

            print("[5] invalid threshold")
            status, _ = _request(base, "GET", "/clusters?min_cos=1.0")
            _check(status == 422, "min_cos=1.0 is rejected with 422")
        finally:
            server.terminate()
            server.wait(timeout=15)
    print("\nCLUSTERS CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
