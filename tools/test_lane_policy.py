"""Canonical pytest taxonomy / lane classification policy for WHD tests.

This module classifies tests for collection and reporting only.  It never changes
expected values, skips, xfails, production behavior, or domain authority.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import NamedTuple


PRIMARY_LANES = (
    "governance",
    "unit",
    "geometry",
    "projection",
    "persistence",
    "dxf",
    "architecture",
    "ui",
    "integration",
)

LANE_EXPRESSIONS = {
    "governance": "governance",
    "unit": "unit",
    "geometry": "geometry",
    "projection": "projection",
    "persistence": "persistence",
    "dxf": "dxf",
    "architecture": "architecture",
    "ui": "ui and not xvfb",
    "integration": "integration",
}
XVFB_UI_EXPRESSION = "ui and xvfb"

MARKER_DESCRIPTIONS = {
    "unit": "pure/state/model unit-level contract selected by WHD test taxonomy",
    "integration": "cross-module or fallback integration contract selected by WHD test taxonomy",
    "geometry": "manufacturing geometry / relief / fold / mesh contract",
    "projection": "2D/3D projection, drawing, render-data, or unfold contract",
    "persistence": "save/reload/project persistence or serialization contract",
    "dxf": "DXF export/reopen/serialization contract",
    "ui": "GUI/user-visible behavior contract",
    "xvfb": "UI contract that requires a real Tk/Xvfb display",
    "architecture": "module ownership, dependency, or single-source architecture contract",
    "governance": "knowledge/process governance contract",
    "characterization": "migration characterization snapshot requiring explicit promotion/retirement review",
    "legacy": "historical compatibility contract",
    "invariant": "protected invariant / manifest / schema contract",
    "requires_tk_display": "test requires a real Tk display; skipped only when DISPLAY is absent",
}

# T5 permanent responsibility directories are authoritative for the primary lane.
# Keep this narrow to the directories explicitly introduced by the #280 move
# manifest; legacy/root tests continue to use the established filename policy.
_DIRECTORY_PRIMARY_LANES = (
    ("tests/governance/", "governance"),
    ("tests/ui/", "ui"),
    ("tests/architecture/", "architecture"),
    ("tests/projection/", "projection"),
)

_ARCHITECTURE_EXACT = {
    "test_issue210_project_actions_move_contract.py",
    "test_issue211_renderer_dependency_gate.py",
}
_UI_TOKENS = (
    "_gui",
    "gui_",
    "_ui",
    "ui_",
    "viewport",
    "toolbar",
    "selector_visibility",
    "visual_contract",
    "notebook",
    "scroll",
    "dialog",
)
_ARCHITECTURE_TOKENS = (
    "architecture",
    "dependency",
    "module_ownership",
    "modularization",
)
_PERSISTENCE_TOKENS = (
    "persist",
    "reload",
    "project_file",
    "serialization",
    "save_reload",
)
_PROJECTION_TOKENS = (
    "projection",
    "2d_3d",
    "3d_2d",
    "render",
    "drawing",
    "unfold",
)
_GEOMETRY_TOKENS = (
    "geometry",
    "relief",
    "divider",
    "corner",
    "sheetmetal",
    "mesh",
    "fold",
    "assembly",
)
_UNIT_TOKENS = (
    "state",
    "policy",
    "registry",
    "semantics",
    "resolver",
    "parser",
    "normalization",
    "schema",
    "manifest",
)


class LaneClassification(NamedTuple):
    primary: str
    secondary: tuple[str, ...] = ()


def _norm(path: str) -> str:
    return PurePosixPath(str(path).replace("\\", "/")).as_posix().lstrip("./")


def classify_test(*, path: str, nodeid: str = "", requires_display: bool = False) -> LaneClassification:
    """Return one primary lane plus optional secondary markers for a collected test."""
    normalized = _norm(path)
    filename = PurePosixPath(normalized).name.lower()
    identity = f"{normalized}::{nodeid}".lower()

    primary = next(
        (lane for prefix, lane in _DIRECTORY_PRIMARY_LANES if normalized.startswith(prefix)),
        None,
    )
    if primary is None:
        if normalized.startswith("tests/knowledge/") or normalized.startswith("tests/process/"):
            primary = "governance"
        elif requires_display or any(token in filename for token in _UI_TOKENS):
            primary = "ui"
        elif filename in _ARCHITECTURE_EXACT or any(token in filename for token in _ARCHITECTURE_TOKENS):
            primary = "architecture"
        elif "dxf" in filename:
            primary = "dxf"
        elif any(token in filename for token in _PERSISTENCE_TOKENS):
            primary = "persistence"
        elif any(token in filename for token in _PROJECTION_TOKENS):
            primary = "projection"
        elif any(token in filename for token in _GEOMETRY_TOKENS):
            primary = "geometry"
        elif any(token in filename for token in _UNIT_TOKENS):
            primary = "unit"
        else:
            primary = "integration"

    secondary: list[str] = []
    if requires_display:
        secondary.append("xvfb")
    if "characterization" in identity:
        secondary.append("characterization")
    if "legacy" in identity or "historical" in identity:
        secondary.append("legacy")
    if "invariant" in identity or "manifest" in identity or "schema" in identity:
        secondary.append("invariant")

    return LaneClassification(primary=primary, secondary=tuple(dict.fromkeys(secondary)))
