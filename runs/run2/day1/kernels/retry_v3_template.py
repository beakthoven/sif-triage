#!/usr/bin/env python3
"""SIF26165 export-retry kernel (v3) — __CONFIG__.

The v1 runs trained all 3 epochs; train.py then crashed at the value_info
strip (FileExistsError on the dynamo external-data sidecar) and the span
fp32 parity compared pad positions. Both fixed in train.py v3
(sha 62fa606b…). This kernel restores ckpt-ep3.pt (shuttled via catbox
190 MB chunks, sha256-verified), fetches fixed train.py, and runs
train.py --resume: zero retraining — val eval recompute -> thresholds ->
export -> two-tier parity gate -> latency -> manifest.
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

CKPT_SHA = "__CKPT_SHA__"
CKPT_CHUNKS = __CKPT_CHUNKS__

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
        "https://files.catbox.moe/71ci5r.py",
        "62fa606b03f0fb104acb128a5f3d0d7eb2b11a7c971a5470351740f6fc6da3b6"),
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


def fetch_url(dest, url):
    dest = pathlib.Path(dest)
    for attempt in range(1, 6):
        subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "5",
                        "-o", str(dest), url], check=False)
        if dest.exists() and dest.stat().st_size > 0:
            return
        time.sleep(5 * attempt)
    raise RuntimeError(f"cannot fetch {url}")


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

    # --- restore ckpt-ep3.pt from catbox chunks ------------------------------
    ckpt = WORK / "ckpt-ep3.pt"
    if ckpt.exists() and sha256(ckpt) == CKPT_SHA:
        print("ckpt cached ok", flush=True)
    else:
        parts = []
        for i, url in enumerate(CKPT_CHUNKS):
            part = WORK / f"ckpt.part{i:02d}"
            if not part.exists():
                fetch_url(part, url)
            parts.append(part)
        with open(ckpt, "wb") as out:
            for p in parts:
                out.write(p.read_bytes())
        assert sha256(ckpt) == CKPT_SHA, "ckpt reassembly hash mismatch"
        for p in parts:
            p.unlink()
        print(f"ckpt-ep3.pt reassembled ({ckpt.stat().st_size} B, "
              f"sha256 verified)", flush=True)

    # --- corpus + fixed code -------------------------------------------------
    for rel, (url, sha) in FILES.items():
        dest = WORK / rel
        if dest.exists() and sha256(dest) == sha:
            print(f"cached ok  {rel}", flush=True)
            continue
        fetch_url(dest, url)
        assert sha256(dest) == sha, f"hash mismatch: {rel}"
        print(f"fetched ok {rel} (sha256 verified)", flush=True)

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
        print("tokenizer saved", flush=True)
    except Exception as e:
        print(f"tokenizer save failed (non-fatal): {e}", flush=True)

    print(f"kernel total {(time.time() - t_start) / 60:.1f} min", flush=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
