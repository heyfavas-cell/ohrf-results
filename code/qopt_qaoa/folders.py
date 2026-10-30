"""The one place folders are made: every script in this package asks here, so a missing folder cannot be forgotten.

A test fails if any other module calls `mkdir` or `makedirs` itself.
"""
from __future__ import annotations

from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent(path: Path | str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    return path


def write_text(path: Path | str, text: str) -> Path:
    path = ensure_parent(path)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
