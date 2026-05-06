#!/usr/bin/env python3
"""Remove generated Python/runtime artifacts from the repo tree."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXCLUDE_NAMES = {'.venv', 'venv', '.pytest_cache', '__pycache__', '.mypy_cache', '.ruff_cache'}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.db', '.sqlite', '.sqlite3', '.log'}


def should_remove(path: Path) -> bool:
    return path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES


def cleanup(root: Path, dry_run: bool = False) -> tuple[int, int]:
    files = dirs = 0
    for path in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and path.name in EXCLUDE_NAMES:
            dirs += 1
            print(f"DIR  {path}")
            if not dry_run:
                shutil.rmtree(path, ignore_errors=True)
        elif path.is_file() and should_remove(path):
            files += 1
            print(f"FILE {path}")
            if not dry_run:
                path.unlink(missing_ok=True)
    return files, dirs


def main() -> int:
    p = argparse.ArgumentParser(description='Clean generated artifacts')
    p.add_argument('path', nargs='?', default='.')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    files, dirs = cleanup(Path(args.path), args.dry_run)
    print(f"removed_files={0 if args.dry_run else files} removed_dirs={0 if args.dry_run else dirs} candidates_files={files} candidates_dirs={dirs}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
