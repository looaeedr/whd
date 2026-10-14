# -*- coding: utf-8 -*-
"""Guard the WHD one-way contract: 3D input -> sheet -> assembly projection.

The single-piece Fold input must never fetch the assembled world's mesh as
its own source. Assembly is the consumer of that input, not its owner.
"""
from dataclasses import fields
from types import SimpleNamespace

from phase6_final_scene_contracts import FinalSceneDependencies
from phase6_final_scene_view import Phase6FinalSceneViewAdapter


def test_physical_3d_input_preview_never_reads_back_from_assembly():
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import DrawingScene

    editor_x = (
        {"len": 22.0, "angle": -90.0},
        {"len": 20.0, "angle": 90.0},
        {"len": 25.0, "angle": -90.0},
        {"len": 346.0, "angle": -90.0},
        {"len": 16.0},
    )
    editor_y = ({"len": 1596.0},)
    source_sheet = SimpleNamespace(
        material=box(0.0, 0.0, 429.0, 1596.0),
        scene=DrawingScene(),
        fold_guides=(),
    )

    def invalid_assembly_read(*args, **kwargs):
        raise AssertionError(
            "3D input is the source; assembly must not feed input preview"
        )

    noop = lambda *args, **kwargs: None
    ports = {
        field.name: noop
        for field in fields(FinalSceneDependencies)
        if field.default is None
    }
    ports.update(
        is_physical_piece_key=lambda key: key == "box_body:left_side",
        physical_piece_render_data=lambda key: source_sheet,
        final_render_provider=lambda: source_sheet,
        resolve_geometry=invalid_assembly_read,
        active_mesh_profiles=lambda material: (editor_x, editor_y),
        active_part=lambda: "box_body:left_side",
        input_snapshot=lambda: {"t": 2.0},
        settings_values=lambda: {"t": 2.0},
        display_mode=lambda: "single",
        operator_dimensions=lambda key=None: (800.0, 1600.0, 350.0),
        alpha_bend=lambda: 0.85,
        corner_dimension_text=lambda material: "",
        blank_text=lambda material, **kw: "",
    )
    request = Phase6FinalSceneViewAdapter(
        dependencies=FinalSceneDependencies(**ports)
    ).build_request()

    assert request.render_data is source_sheet
    assert request.x_profile == editor_x
    assert request.y_profile == editor_y


def test_manufacturing_adapter_reads_active_3d_input_not_assembly_result():
    from phase6_manufacturing_adapter import _profile_inputs_for_part

    x = [{"len": 16.0, "angle": -90.0}, {"len": 346.0}]
    y = [{"len": 1500.0}]
    app = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="box_body:right_side"),
        state=SimpleNamespace(profiles={"X": x, "Y": y}),
        _phase6_input_snapshot={},
        _settings_values={},
    )
    raw_x, raw_y = _profile_inputs_for_part(app, "box_body:right_side")
    assert raw_x == tuple(x)
    assert raw_y == tuple(y)
