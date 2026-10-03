"""Validate reproducible source inputs before starting a formal run."""

import hashlib
import subprocess
from pathlib import Path


def require_clean_tree(root: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        raise RuntimeError("Formal run requires committed, clean sources")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def verify_sources(root: Path, lock: dict) -> dict:
    root = root.resolve()
    issues = []
    for item in lock["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            issues.append({"path": item["path"], "code": "missing_or_outside_root"})
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            issues.append({"path": item["path"], "code": "hash_mismatch"})
    return {"ok": not issues, "issues": issues}
