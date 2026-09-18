from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
DIVIDER = ROOT / "gui_modules" / "parts" / "panels" / "divider.py"

# Focused Task 5 divider characterization. This file intentionally drives RED
# before any divider production extraction is added.


def _load_divider_module():
    spec = importlib.util.spec_from_file_location("issue292_divider_panel", DIVIDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_divider_panel_owns_input_collection_not_geometry_authority():
    text = DIVIDER.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert "collect_divider_input" in functions
    for forbidden in (
        "derive_box_body_dividers",
        "build_box_body_divider_render_data",
        "divider_fold_contract",
        "DIVIDER_OUTSIDE_FIRST",
        "DIVIDER_FORMED_CORE",
        "DIVIDER_OUTSIDE_LAST",
    ):
        assert forbidden not in text, f"divider panel must not own geometry/manufacturing token: {forbidden}"


def test_divider_input_collection_preserves_authoritative_topology_values():
    module = _load_divider_module()
    payload = {
        "door_layout_columns": [[800, [1100, 500]], [200.5, [1600]]],
        "d": "350",
        "t": "2",
        "door_layout_scope": " receiving-main ",
        "door_handle_edges": {"door_c1_r1": "left"},
        "model": " 受電箱 ",
    }

    actual = module.collect_divider_input(
        "box_body:divider:h1",
        payload,
        default_depth=999.0,
        default_thickness=9.0,
    )

    assert actual == {
        "columns": ((800.0, (1100.0, 500.0)), (200.5, (1600.0,))),
        "depth": 350.0,
        "thickness": 2.0,
        "layout_scope": "receiving-main",
        "handle_edges": {"door_c1_r1": "left"},
        "model_name": "受電箱",
    }


def test_divider_input_collection_uses_existing_fallbacks_and_fails_closed_without_topology():
    module = _load_divider_module()

    actual = module.collect_divider_input(
        "box_body:divider:v1",
        {"door_layout_columns": [(800, (1600,))]},
        default_depth=350.0,
        default_thickness=2.0,
    )
    assert actual["depth"] == 350.0
    assert actual["thickness"] == 2.0
    assert actual["layout_scope"] == "main"
    assert actual["handle_edges"] == {}
    assert actual["model_name"] is None

    with pytest.raises(ValueError, match="中隔缺少 authoritative multi-door topology"):
        module.collect_divider_input(
            "box_body:divider:v1",
            {},
            default_depth=350.0,
            default_thickness=2.0,
        )


def test_gui_routes_divider_payload_collection_through_panel_boundary():
    import inspect
    from gui_modules.application import fold_designer_adapter as owner
    text = (ROOT / "gui_modules" / "application" / "fold_designer_adapter.py").read_text(encoding="utf-8")
    assert "from gui_modules.parts.panels.divider import collect_divider_input" in text
    source = inspect.getsource(owner._query_fold_designer_render_data)
    assert "collect_divider_input(" in source
    assert "derive_box_body_dividers" in source
    assert "build_box_body_divider_render_data" in source
