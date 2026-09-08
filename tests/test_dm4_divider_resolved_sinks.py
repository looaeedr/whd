from __future__ import annotations

import pytest


def test_main_scene_callback_refuses_direct_divider_nominal_rebuild():
    """Divider must reach the scene through ResolvedManufacturingGeometry only."""
    import gui
    from ae_engine.door_dividers import derive_box_body_dividers

    columns = ((800.0, (800.0, 800.0)),)
    divider = derive_box_body_dividers(
        columns,
        depth=350.0,
        thickness=2.0,
        layout_scope="main",
        model_name="受電箱",
        frame_width=31.0,
    )[0]
    payload = {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 31.0,
        "door_layout_scope": "main",
        "door_layout_columns": columns,
        "door_handle_edges": {},
    }

    app = object.__new__(gui.BoxCalculatorGUI)
    with pytest.raises(RuntimeError, match="ResolvedManufacturingGeometry"):
        app._query_fold_designer_render_data(divider.stable_id, payload)


def test_main_scene_callback_source_has_no_divider_geometry_builder():
    import inspect
    import gui

    source = inspect.getsource(gui.BoxCalculatorGUI._query_fold_designer_render_data)
    assert "derive_box_body_dividers" not in source
    assert "build_box_body_divider_render_data" not in source


def test_active_divider_final_query_consumes_resolved_part(monkeypatch):
    from types import SimpleNamespace
    import fold_designer_bridge as bridge

    divider_key = "box_body:divider:main:HORIZONTAL:C0_R0|R1"
    canonical_render = object()

    class Resolved:
        def part(self, key):
            assert key == divider_key
            return SimpleNamespace(render_data=canonical_render)

    designer = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part=divider_key),
        _phase6_input_snapshot={},
    )
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _self: Resolved()
    )

    assert bridge._phase6_query_final_render_data(designer) is canonical_render
