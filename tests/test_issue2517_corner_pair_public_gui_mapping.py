"""#2517: GUI Corner Pair presentation must depend on Engine public API."""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection


def test_public_pair_members_prove_certified_owner_and_bad_input_fail_closed():
    from ae_engine import project_operator_corner_pair_members
    from ae_engine.corner_state_transactions import MANUAL_CORNER_PAIR_KEYS
    assert project_operator_corner_pair_members is manufacturing_api.project_operator_corner_pair_members
    for key in ("top", "bottom"):
        before = dict(MANUAL_CORNER_PAIR_KEYS)
        assert project_operator_corner_pair_members(key) == MANUAL_CORNER_PAIR_KEYS[key]
        assert dict(MANUAL_CORNER_PAIR_KEYS) == before
    assert manufacturing_api.project_operator_corner_selection_target("top") == "top_left"
    assert manufacturing_api.project_operator_corner_selection_target("bottom") == "bottom_left"
    assert manufacturing_api.project_operator_corner_selection_target("top_right") == "top_right"
    for value in (None, True, 2, "", "TOP", "left", "foo", []):
        with pytest.raises(ValueError, match="CORNER_PAIR_KEY_INVALID"):
            project_operator_corner_pair_members(value)
        with pytest.raises(ValueError, match="CORNER_SELECTION_TARGET_INVALID"):
            manufacturing_api.project_operator_corner_selection_target(value)


def test_gui_pair_selection_uses_public_engine_and_has_same_physical_corner():
    from gui import Phase6ApplicationHost
    sel = CornerTypeSelection(CornerTypeId.C02)
    host = SimpleNamespace(
        manual_corner_state={"head": {
            "top_left": sel,
            "top_right": CornerTypeSelection(CornerTypeId.CROSS),
        }},
        manual_corner_pair_same={"head":{"top":True}},
    )
    assert Phase6ApplicationHost._manual_selection_for_target(host,"head","top") == manufacturing_api.operator_normalize_corner_selection(sel)
    assert Phase6ApplicationHost._manual_selection_for_target(host,"head","top_left") == manufacturing_api.operator_normalize_corner_selection(sel)


def test_corner_panels_do_not_access_private_pair_mapping():
    root = Path(__file__).resolve().parents[1]
    for rel in ("gui.py","gui_modules/parts/panels/assembly_corner.py"):
        text = (root/rel).read_text(encoding="utf-8")
        tree = ast.parse(text)
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "ae_engine.corner_type_ui"
            and any(alias.name == "CORNER_PAIR_CORNERS" for alias in node.names)
            for node in ast.walk(tree)
        ), rel
        assert "manufacturing_api.project_operator_corner_pair_members" in text



def test_gui_corner_selection_and_pair_toggle_stays_same_after_public_routing():
    from gui_modules.parts.panels.assembly_corner import (
        normalize_manual_corner_target, select_manual_corner,
    )

    class SelectionVar:
        def __init__(self, value):
            self.value=value
        def get(self):
            return self.value
        def set(self, value):
            self.value=value

    render_count=[]
    host=SimpleNamespace(
        manual_active_corner_var=SelectionVar("top"),
        manual_corner_pair_same={"head":{"top":False,"bottom":True}},
        manual_corner_state={"head":{"top_left":CornerTypeSelection(CornerTypeId.CROSS)}},
        _current_manual_corner_part_key=lambda:"head",
        _pair_for_corner_target=lambda key:
            "top" if key in ("top","top_left","top_right") else "bottom",
        refresh_corner_type_panel=lambda:render_count.append(True),
    )
    assert normalize_manual_corner_target(host,"head")=="top_left"
    select_manual_corner(host,"top")
    assert host.manual_active_corner_var.get()=="top_left"
    select_manual_corner(host,"top_right")
    assert host.manual_active_corner_var.get()=="top_right"
    host.manual_corner_pair_same["head"]["top"]=True
    select_manual_corner(host,"top_right")
    assert host.manual_active_corner_var.get()=="top"
    assert normalize_manual_corner_target(host,"head")=="top"
    assert len(render_count)==3
