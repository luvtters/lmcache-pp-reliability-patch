#!/usr/bin/env python3
"""Apply the tested Python-only reliability patch to an existing LMCache."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Directory containing lmcache/")
    parser.add_argument("--check", action="store_true", help="Check without changing files")
    args = parser.parse_args()
    if args.root is None:
        spec = importlib.util.find_spec("lmcache")
        if spec is None or spec.origin is None:
            parser.error("LMCache was not found; use the service's Python or supply --root")
        root = Path(spec.origin).resolve().parent.parent
    else:
        root = args.root.resolve()
    delivery = Path(__file__).resolve().parent
    if not root.is_dir():
        parser.error("The target directory does not exist")
    print("LMCache target:", root / "lmcache", flush=True)
    print("Supported bases: native PP 89d93a2, or delayed STORE fix 2570c2c; target: 02ffb69", flush=True)
    git = ["git", "-c", "core.autocrlf=false", "-C", str(root), "apply"]
    env = os.environ.copy()
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    failures = []
    for name in (
        "lmcache-reliability-89d93a2-to-02ffb69.patch",
        "lmcache-reliability-2570c2c-to-02ffb69.patch",
    ):
        patch = delivery / name
        if not patch.is_file():
            parser.error("Delivery is incomplete; update this clone before applying")
        checked = subprocess.run(
            git + ["--check", str(patch)], env=env, capture_output=True, text=True,
        )
        if checked.returncode == 0:
            break
        failures.append((name, checked.stderr))
    else:
        print("NO FILES CHANGED: neither supported patch matches this installation", file=sys.stderr)
        for name, error in failures:
            print(name + ":\n" + error, file=sys.stderr)
        raise SystemExit(1)
    print("Selected patch:", patch.name, flush=True)
    stat = subprocess.check_output(git + ["--numstat", str(patch)], text=True, env=env)
    paths = [line.split("\t", 2)[2] for line in stat.splitlines()]
    if len(paths) != 14 or any(
        not name.startswith("lmcache/") or not name.endswith(".py")
        or ".." in Path(name).parts for name in paths
    ):
        raise RuntimeError("The patch is not the expected 14-file Python change")
    if args.check:
        print("CHECK PASSED; no target files changed")
        return
    backup = Path(tempfile.mkdtemp(prefix="backup-before-02ffb69-", dir=patch.parent))
    original = {}
    for name in paths:
        source = root / name
        original[name] = source.exists()
        if source.exists():
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    (backup / "backup.json").write_text(
        json.dumps({"target_root": str(root), "patch_file": patch.name, "originally_present": original}, indent=2),
        encoding="utf-8",
    )
    shutil.copy2(patch, backup / "applied.patch")
    print("Backup:", backup, flush=True)
    subprocess.run(git + [str(patch)], check=True, env=env)
    for name in paths:
        compile((root / name).read_bytes(), str(root / name), "exec")
    print("APPLIED: 14 Python files; syntax checks passed")
    print("No package import, dependency installation, native rebuild, or service restart performed")
    print("Update both model/cache launch environments before restarting them together")


if __name__ == "__main__":
    main()
