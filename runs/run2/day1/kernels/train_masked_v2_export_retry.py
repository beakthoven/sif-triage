#!/usr/bin/env python3
"""SIF26165 masked export-retry kernel (v2).

v1 trained all 3 epochs but crashed in train.py's fp32-parity stage
(np.concatenate over variable-length span_logits). This kernel attaches the
v1 output bundle as a data source, restores ckpt-ep3.pt into /kaggle/working,
fetches the FIXED train.py (parity compares per batch; --resume with all
epochs complete recomputes the val eval instead of NameError), and reruns
train.py --resume: zero retraining, straight to eval -> thresholds -> export
-> gate -> latency -> manifest.
"""
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import time

CONFIG = "masked"
WORK = pathlib.Path("/kaggle/working")
PREV = pathlib.Path("/kaggle/input/sif26165-train-masked-v1")
CORPUS = WORK / "corpus"
CORPUS.mkdir(parents=True, exist_ok=True)

CORPUS_SHA = {
    "train.jsonl": "19690e9d6ce4d1dc7540349d011c4ebfd2c844e127bd9cd785a9ba9cd438cbff",
    "val.jsonl": "0b2e8db9e4afc558ca3bb9d60ca4c39a552e1a68a0a833555dfe3146d4b3e6ad",
    "test.jsonl": "9e912f100d7cce799a6b2ed6e9b560f19b56c6cec39aec2da388216a5fba37ff",
}
FETCH = {
    "train.py": (
        "https://files.catbox.moe/g3dx5q.py",
        "6337ec327078fc452aac6819f0d67878cb3f140379b8b0ca0a4f5fbb3bde8acd"),
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
        print(f"cached ok  {rel}", flush=True)
        return
    for attempt in range(1, 6):
        subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "5",
                        "-o", str(dest), url], check=False)
        if dest.exists() and sha256(dest) == sha:
            print(f"fetched ok {rel} (sha256 verified)", flush=True)
            return
        time.sleep(5 * attempt)
    raise RuntimeError(f"cannot fetch {rel} from {url}")


def main():
    t_start = time.time()
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("No GPU allocated - re-probe; do not train on CPU")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"GPU: {name} capability sm_{cap[0]}{cap[1]} "
          f"torch {torch.__version__}", flush=True)
    if cap < (7, 0):
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

    # --- restore v1 state from the attached output bundle -------------------
    assert (PREV / "ckpt-ep3.pt").exists(), "v1 bundle missing ckpt-ep3.pt"
    shutil.copy(PREV / "ckpt-ep3.pt", WORK / "ckpt-ep3.pt")
    print(f"restored ckpt-ep3.pt ({(WORK / 'ckpt-ep3.pt').stat().st_size} B)",
          flush=True)
    for f, sha in CORPUS_SHA.items():
        dest = CORPUS / f
        shutil.copy(PREV / "corpus" / f, dest)
        assert sha256(dest) == sha, f"corpus copy corrupt: {f}"
    print("corpus restored from v1 bundle (sha256 verified)", flush=True)

    for rel, (url, sha) in FETCH.items():
        fetch(rel, url, sha)

    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "transformers==4.57.6", "onnxruntime==1.29.0",
                    "onnxscript", "onnx"], check=True)

    # --- resume: all 3 epochs done -> val eval + export + gate + manifest ---
    t0 = time.time()
    r = subprocess.run([sys.executable, "train.py",
                        "--corpus-dir", str(CORPUS),
                        "--config", CONFIG,
                        "--epochs", "3", "--batch", "32", "--seq", "128",
                        "--lr", "2e-5", "--out", str(WORK), "--resume"],
                       cwd=WORK, check=False)
    print(f"train.py exit={r.returncode} ({(time.time() - t0) / 60:.1f} min)",
          flush=True)

    try:
        from transformers import AutoTokenizer
        AutoTokenizer.from_pretrained(
            "answerdotai/ModernBERT-base").save_pretrained(WORK / "tokenizer")
        print("tokenizer saved to /kaggle/working/tokenizer", flush=True)
    except Exception as e:
        print(f"tokenizer save failed (non-fatal): {e}", flush=True)

    print(f"kernel total {(time.time() - t_start) / 60:.1f} min", flush=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
