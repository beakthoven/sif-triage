#!/usr/bin/env python3
"""retrieve.py — parallel ranged download + sha256 verify for kernel outputs.

Usage: python3 retrieve.py <manifest.json> <urls.json> <outdir>
  manifest.json : train.py artifact manifest (files{name: {sha256, bytes}})
  urls.json     : {relative_file_name: download_url} from
                  list_notebook_session_output
Downloads with 8 concurrent 16 MB ranges per file, stall-guarded
(--speed-time/--speed-limit), retries, then verifies size + sha256 against
the kernel manifest. Skips files already verified on disk.
"""
import concurrent.futures as cf
import hashlib
import json
import pathlib
import subprocess
import sys

CHUNK = 16 * 1024 * 1024
WORKERS = 8


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_range(url, start, end, dest):
    for attempt in range(1, 7):
        r = subprocess.run(
            ["curl", "-sS", "-L", "--speed-time", "30", "--speed-limit",
             "10240", "--retry", "3", "-r", f"{start}-{end}", "-o",
             str(dest), url], check=False)
        if r.returncode == 0 and dest.exists() and \
                dest.stat().st_size == end - start + 1:
            return
    raise RuntimeError(f"range {start}-{end} failed for {url}")


def retrieve(name, url, want_size, want_sha, outdir):
    dest = outdir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == want_size \
            and sha256(dest) == want_sha:
        return name, "cached"
    if want_size <= CHUNK:
        fetch_range(url, 0, want_size - 1, dest)
    else:
        ranges = [(s, min(s + CHUNK, want_size) - 1)
                  for s in range(0, want_size, CHUNK)]
        parts = [outdir / f"{name}.part{i:03d}" for i in range(len(ranges))]
        with cf.ThreadPoolExecutor(WORKERS) as ex:
            futs = [ex.submit(fetch_range, url, s, e, p)
                    for (s, e), p in zip(ranges, parts)]
            for f in futs:
                f.result()
        with open(dest, "wb") as out:
            for p in parts:
                out.write(p.read_bytes())
        for p in parts:
            p.unlink()
    assert dest.stat().st_size == want_size, f"{name}: size mismatch"
    got = sha256(dest)
    assert got == want_sha, f"{name}: sha256 {got} != manifest {want_sha}"
    return name, f"ok ({want_size} B, sha256 verified)"


def main():
    manifest = json.load(open(sys.argv[1]))
    urls = json.load(open(sys.argv[2]))
    outdir = pathlib.Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    failures = []
    skipped = []
    for name, meta in sorted(manifest["files"].items(),
                             key=lambda kv: kv[1]["bytes"]):
        if name not in urls:
            failures.append(f"{name}: NO URL in session output")
            continue
        if urls[name] is None:
            skipped.append(name)
            print(f"{name}: skipped (deferred, still in kernel bundle)",
                  flush=True)
            continue
        try:
            n, msg = retrieve(name, urls[name], meta["bytes"],
                              meta["sha256"], outdir)
            print(f"{n}: {msg}", flush=True)
        except Exception as e:
            failures.append(f"{name}: {e}")
            print(f"{name}: FAILED {e}", flush=True)
    if failures:
        print(f"{len(failures)} FAILURES: {failures}")
        sys.exit(1)
    print(f"all {len(manifest['files'])} files retrieved + verified")


if __name__ == "__main__":
    main()
