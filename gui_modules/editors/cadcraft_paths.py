"""Locate the bundled CADCraft portable binaries next to the WHD application.

./cadcraft is relative to the WHD entry point, NOT to the caller's current
working directory.  No environment-variable or PATH configuration is needed.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def whd_application_directory() -> Path:
    """Source checkout root or the directory containing the packaged WHD exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def cadcraft_directory() -> Path:
    return whd_application_directory() / "cadcraft"


def cadcraft_binary(kind: str) -> Path:
    """Return a deterministic local portable path; the caller checks existence."""
    if kind not in ("gui", "cli"):
        raise ValueError(f"Unsupported CADCraft binary kind: {kind}")
    stem = "cadcraft" if kind == "gui" else "cadcraft-cli"
    suffix = ".exe" if os.name == "nt" else ""
    return cadcraft_directory() / (stem + suffix)
