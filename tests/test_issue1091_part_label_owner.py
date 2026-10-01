from __future__ import annotations

import ast
from pathlib import Path

import phase6_part_navigation as nav
import fold_designer_bridge as bridge

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
NAV = ROOT / "phase6_part_navigation.py"


def test_operator_part_label_preserves_current_dynamic_labels():
    base = {"box_body": "箱身", "head": "封頭"}
    receiving = {"model": "受電箱", "door_layout_columns": [1]}
    assert nav.operator_part_label("box_body", base_labels=base) == "箱身"
    assert nav.operator_part_label("box_body:back", base_labels=base) == "後面板"
    assert nav.operator_part_label("door_c1_r1", snapshot=receiving, base_labels=base) == "上門"
    assert nav.operator_part_label("door_c1_r2", snapshot=receiving, base_labels=base) == "下門"
    assert nav.operator_part_label("base_plate_c1_r1", snapshot=receiving, base_labels=base) == "上門底板"
    assert nav.operator_part_label("box_body:divider:HORIZONTAL:1", base_labels=base) == "箱身中隔（橫向）"
    assert nav.operator_part_label("inner_door:upper:panel", base_labels=base) == "上層內門門板"
    assert nav.operator_part_label("inner_door:lower:left_frame", base_labels=base) == "下層內門左框"


def test_navigation_owner_stays_pure_and_does_not_reverse_import_bridge():
    source = NAV.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "fold_designer_bridge" not in imports
    assert "tkinter" not in imports
    assert not [name for name in imports if name.startswith("ae_engine") or "manufacturing" in name]
    assert "designer_workspace" not in source


def test_bridge_part_label_is_thin_compatibility_wrapper():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_phase6_part_label")
    assert len(fn.body) <= 2
    text = ast.unparse(fn)
    assert "_dm7_operator_part_label" in text
    assert "re.fullmatch" not in text


def test_bridge_compatibility_surface_matches_new_owner():
    samples = (
        "box_body", "box_body:left_side", "box_body:back", "box_body:right_side",
        "door_c1_r1", "door_c2_r3", "base_plate_c1_r2",
        "box_body:divider:VERTICAL:7", "inner_door:upper:panel",
        "inner_door:lower:right_frame",
    )
    snapshot = {"model": "受電箱", "door_layout_columns": [1]}
    for key in samples:
        assert bridge._phase6_part_label(key, snapshot=snapshot) == nav.operator_part_label(
            key, snapshot=snapshot, base_labels=bridge.PART_LABELS
        )


def test_bridge_loc_ratchets_below_6330():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6330, f"Bridge regrew past #1091 ratchet: {loc}"
