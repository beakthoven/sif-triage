"""One-shot runtime-bundle fetcher for container cold starts.

Two sources, selected by argument:

  fetch_bundle.py <bundle_dir> <hf_repo_id>
      Hugging Face dataset mode. Downloads every file listed in the
      dataset's bundle_manifest.txt into bundle_dir, preserving relative
      paths (masked-v2/, embeddings/, demo_pre.db). Auth: HF_TOKEN env.

  fetch_bundle.py <bundle_dir> --github <owner/repo@tag>
      GitHub Release mode. Downloads sif-runtime-bundle.tar.gz from the
      private release <tag> of <owner/repo> and extracts it into
      bundle_dir (the tar preserves the same relative layout). Auth:
      GITHUB_TOKEN env (read-only PAT for that repo).

Run by deploy/entrypoint.sh; the image installs huggingface_hub for the
first mode. The second mode needs only stdlib.
"""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import urllib.request


def _fetch_github(bundle_dir: str, repo_at_tag: str) -> int:
    if "@" not in repo_at_tag:
        print(f"--github wants <owner/repo@tag>, got {repo_at_tag!r}", file=sys.stderr)
        return 2
    repo, tag = repo_at_tag.rsplit("@", 1)
    token = os.environ.get("GITHUB_TOKEN")
    url = (f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "sif-triage-bootstrap",
    })
    import json
    with urllib.request.urlopen(req, timeout=60) as r:
        release = json.load(r)
    asset = next((a for a in release.get("assets", [])
                  if a.get("name") == "sif-runtime-bundle.tar.gz"), None)
    if asset is None:
        print(f"release {tag} of {repo} has no sif-runtime-bundle.tar.gz asset",
              file=sys.stderr)
        return 1
    dl = urllib.request.Request(asset["url"], headers={
        "Accept": "application/octet-stream",
        "Authorization": f"Bearer {token}",
        "User-Agent": "sif-triage-bootstrap",
    })
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with urllib.request.urlopen(dl, timeout=900) as r:
            while chunk := r.read(1 << 20):
                tmp.write(chunk)
        tmp_path = tmp.name
    os.makedirs(bundle_dir, exist_ok=True)
    with tarfile.open(tmp_path, "r:gz") as tf:
        tf.extractall(bundle_dir, filter="data")
    os.unlink(tmp_path)
    print(f"[fetch_bundle] extracted {asset['name']} into {bundle_dir}", flush=True)
    return 0


def _fetch_hf(bundle_dir: str, repo_id: str) -> int:
    from huggingface_hub import hf_hub_download

    token = os.environ.get("HF_TOKEN")
    manifest_path = hf_hub_download(
        repo_id=repo_id, filename="bundle_manifest.txt",
        repo_type="dataset", token=token,
    )
    with open(manifest_path, encoding="utf-8") as fh:
        files = [
            line.strip() for line in fh
            if line.strip() and line.strip() != "bundle_manifest.txt"
        ]
    for done, rel in enumerate(files, start=1):
        print(f"[fetch_bundle] {done}/{len(files)} {rel}", flush=True)
        hf_hub_download(
            repo_id=repo_id, filename=rel, repo_type="dataset",
            token=token, local_dir=bundle_dir,
        )
    print(f"[fetch_bundle] {len(files)} files ready under {bundle_dir}", flush=True)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 3 and args[1] == "--github":
        return _fetch_github(args[0], args[2])
    if len(args) == 2:
        return _fetch_hf(args[0], args[1])
    print(f"usage: {sys.argv[0]} <bundle_dir> (<hf_repo_id> | --github <owner/repo@tag>)",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
