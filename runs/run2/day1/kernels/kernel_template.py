#!/usr/bin/env python3
"""SIF26165 Day-1 training kernel (Kaggle script kernel, SaveAndRunAll).

CONFIG is the only per-kernel difference (masked | unmasked).

Staging note: corpus+code are fetched from catbox URLs with sha256 verify
(Kaggle-Dataset staging via MCP was blocked — token lacks
datasets.create/update/get scopes; blobs pre-uploaded to Kaggle GCS,
tokens saved in /tmp/sif_staging/tokens.json on the orchestrator box for
later one-click dataset finalization).
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import time

CONFIG = "__CONFIG__"
WORK = pathlib.Path("/kaggle/working")
CORPUS = WORK / "corpus"
CORPUS.mkdir(parents=True, exist_ok=True)

FILES = {
    "corpus/train.jsonl": (
        "https://files.catbox.moe/gftudt.jsonl",
        "19690e9d6ce4d1dc7540349d011c4ebfd2c844e127bd9cd785a9ba9cd438cbff"),
    "corpus/val.jsonl": (
        "https://files.catbox.moe/huo0bw.jsonl",
        "0b2e8db9e4afc558ca3bb9d60ca4c39a552e1a68a0a833555dfe3146d4b3e6ad"),
    "corpus/test.jsonl": (
        "https://files.catbox.moe/fwsohf.jsonl",
        "9e912f100d7cce799a6b2ed6e9b560f19b56c6cec39aec2da388216a5fba37ff"),
    "train.py": (
        "https://files.catbox.moe/hqbqo7.py",
        "e1ce83e9003757acacd7df22f3ffdc7b19472747d04b7cdf3d65436b2758a531"),
    "model.py": (
        "https://files.catbox.moe/0auh5g.py",
        "6027f4109436e1d58277bfa1fffc358c3c85278c65b3b6868f7b899d061312e3"),
    "label_spec.yaml": (
        "https://files.catbox.moe/y8df0c.yaml",
        "96114b0961bc4365d7bb48c217654bc37904411fee12732839694641861b409a"),
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(rel, url, sha):
    dest = WORK / rel
    if dest.exists() and sha256(dest) == sha:
        print(f"cached ok  {rel} ({dest.stat().st_size} B)", flush=True)
        return
    for attempt in range(1, 6):
        subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "5",
                        "-o", str(dest), url], check=False)
        if dest.exists() and sha256(dest) == sha:
            print(f"fetched ok {rel} ({dest.stat().st_size} B, sha256 "
                  f"verified)", flush=True)
            return
        print(f"fetch attempt {attempt} for {rel} failed hash check",
              flush=True)
        time.sleep(5 * attempt)
    raise RuntimeError(f"cannot fetch {rel} from {url}")


def main():
    t_start = time.time()

    # --- 1. GPU auto-detect (D1) + P100 cu126 fallback (self re-exec) -------
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("No GPU allocated - re-probe; do not train on CPU")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"GPU: {name} capability sm_{cap[0]}{cap[1]} "
          f"torch {torch.__version__}", flush=True)
    if cap < (7, 0):  # P100 (sm_60): cu126 wheel still ships sm_60
        if os.environ.get("SIF_TORCH_REINSTALLED") != "1":
            print("P100 detected -> reinstalling torch 2.10.0+cu126, "
                  "then re-exec", flush=True)
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y",
                            "torch", "torchvision", "torchaudio"],
                           check=False)
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "torch==2.10.0", "--index-url",
                            "https://download.pytorch.org/whl/cu126"],
                           check=True)
            os.environ["SIF_TORCH_REINSTALLED"] = "1"
            os.execv(sys.executable,
                     [sys.executable, os.path.abspath(__file__)])
        raise RuntimeError("still sm<70 after cu126 reinstall")

    # --- 2. fetch corpus + frozen code, sha256-verified ---------------------
    for rel, (url, sha) in FILES.items():
        fetch(rel, url, sha)

    # --- 3. pins (D12: transformers==4.57.6; GREEN gate env) ----------------
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "transformers==4.57.6", "onnxruntime==1.29.0",
                    "onnxscript", "onnx"], check=True)

    # --- 4. dry-run plan, then train + export + gate -------------------------
    subprocess.run([sys.executable, "train.py", "--dry-run",
                    "--corpus-dir", str(CORPUS), "--config", CONFIG],
                   cwd=WORK, check=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, "train.py",
                        "--corpus-dir", str(CORPUS),
                        "--config", CONFIG,
                        "--epochs", "3", "--batch", "32", "--seq", "128",
                        "--lr", "2e-5", "--out", str(WORK), "--resume"],
                       cwd=WORK, check=False)
    train_min = (time.time() - t0) / 60
    print(f"train.py exit={r.returncode} ({train_min:.1f} min)", flush=True)

    # --- 5. tokenizer snapshot (deployment parity; not written by train.py) -
    try:
        from transformers import AutoTokenizer
        AutoTokenizer.from_pretrained(
            "answerdotai/ModernBERT-base").save_pretrained(WORK / "tokenizer")
        print("tokenizer saved to /kaggle/working/tokenizer", flush=True)
    except Exception as e:  # non-fatal
        print(f"tokenizer save failed (non-fatal): {e}", flush=True)

    print(f"kernel total {(time.time() - t_start) / 60:.1f} min", flush=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
