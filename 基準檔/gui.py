# -*- coding: utf-8 -*-
"""Compatibility launcher for the authoritative Phase6 GUI.

This directory used to contain a complete stale copy of the application.
Running it meant users could keep seeing an old 3D layout even after the
project root had been updated.  Keep this file only as a redirect so every
entry point executes the single authoritative root ``gui.py``.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_GUI = PROJECT_ROOT / "gui.py"


def main():
    os.chdir(PROJECT_ROOT)
    root_text = str(PROJECT_ROOT)
    if not sys.path or sys.path[0] != root_text:
        try:
            sys.path.remove(root_text)
        except ValueError:
            pass
        sys.path.insert(0, root_text)
    return runpy.run_path(str(ROOT_GUI), run_name="__main__")


if __name__ == "__main__":
    main()
