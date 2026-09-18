# -*- coding: utf-8 -*-
"""#341 T8 — formal three-layer visual acceptance harness contract."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "issue341_visual_acceptance.py"


def _harness_source() -> str:
    return HARNESS.read_text(encoding="utf-8") if HARNESS.exists() else ""


def test_t8_red_three_layer_visual_acceptance_harness_exists():
    source = _harness_source()
    required = (
        "def probe_geometry_reachability",
        "def probe_effective_styles",
        "def capture_window_png",
        "def inspect_pixels",
        "def build_visual_checklist",
        "geometry.json",
        "styles.json",
        "pixels.json",
        "visual-checklist.md",
        "small",
        "medium",
        "large",
        "winfo_containing",
        "WHD_THEME",
    )
    missing = [token for token in required if token not in source]
    assert not missing, (
        "#341 EXPECTED RED: formal T8 evidence harness is incomplete; "
        f"missing={missing!r}"
    )


def test_t8_harness_stays_acceptance_only():
    source = _harness_source()
    if not source:
        return
    forbidden = (
        "ae_engine.manufacturing_api.",
        "PartSpec(",
        "save_project_file(",
        "designer_workspace.add_part(",
        "designer_workspace.remove_part(",
    )
    leaks = [token for token in forbidden if token in source]
    assert not leaks, f"T8 harness must not become product/domain authority: {leaks!r}"


def test_t8_harness_parses_when_present():
    source = _harness_source()
    if source:
        ast.parse(source)
