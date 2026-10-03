"""Inspect only requested tools, without exposing the process environment."""

import hashlib
import shutil
import subprocess
from pathlib import Path


def inspect_tools(required: tuple[str, ...]) -> dict:
    tools = {}
    missing = []
    for name in required:
        executable = shutil.which(name)
        if executable is None:
            missing.append(name)
            continue
        try:
            result = subprocess.run(
                [executable, "--version"], capture_output=True, text=True, timeout=10
            )
            version = (result.stdout or result.stderr).strip()
            if result.returncode != 0 or not version:
                missing.append(name)
                continue
            binary = Path(executable).resolve()
            tools[name] = {
                "path": str(binary),
                "version": version.splitlines()[0],
                "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            }
        except (OSError, subprocess.TimeoutExpired) as error:
            missing.append(name)
            tools[name] = {"error": type(error).__name__}
    return {"ok": not missing, "tools": tools, "missing": missing}
