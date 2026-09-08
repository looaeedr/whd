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
