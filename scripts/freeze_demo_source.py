"""Refresh the review fingerprint after intentionally changing deployment inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "Dockerfile.demo",
        root / "requirements-linux-py312.lock",
        root / "scripts/serve_demo.py",
        root / "scripts/verify_demo_deployment.py",
        *(root / "fraud").glob("*.py"),
        root / "web/index.html",
    ]
    hashes = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }
    digest = hashlib.sha256(
        json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = root / "deploy/image-source.json"
    if args.write:
        identity = {
            "base_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "input_sha256": digest,
            "files": hashes,
            "training": {"source": "synthetic", "seed": 42, "rows": 12000},
            "status": "UNCOMMITTED_REVIEW_ARTIFACT",
        }
        path.write_text(json.dumps(identity, indent=2) + "\n")
    else:
        identity = json.loads(path.read_text())
        if identity["files"] != hashes or identity["input_sha256"] != digest:
            raise SystemExit("Deployment inputs changed; review and run with --write to refreeze")
    print(digest)


if __name__ == "__main__":
    main()
