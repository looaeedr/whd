"""#2517 Door-layout operator preview geometry, indicator and baseline ownership."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import ae, manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.sheetmetal_features import DoorIndicatorContext, resolve_door_indicator_layout
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, build_door_result
from gui_modules.application import door_render_host_adapter as gui_adapter


def values():
    return {
        "t": 2.0, "fw": 25.0, "door_gap_w": 3.5, "door_gap_h": 4.0,
        "door_fold_l": 15.0, "door_fold_r": 17.0,
        "door_fold_t": 12.0, "door_fold_b": 14.0,
    }


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_cell_result_matches_existing_structural_preview(family):
    v = values()
    edges = DoorFrameEdges(left=True, right=False, top=False, bottom=True)
    material_fw = family_policy.door_material_frame_width(
        family, frame_width=v["fw"], thickness=v["t"],
    )
    result = manufacturing_api.project_operator_door_cell_result(
        v, cell_width=420.0, cell_height=600.0,
        frame_edges=edges, material_frame_width=material_fw,
    )
    expected = build_door_result(
        w=420.0, h=600.0, t=v["t"], fw=material_fw,
        gap_w=v["door_gap_w"], gap_h=v["door_gap_h"],
        fold_left=v["door_fold_l"], fold_right=v["door_fold_r"],
        fold_top=v["door_fold_t"], fold_bottom=v["door_fold_b"],
        frame_edges=edges,
    )
    assert (result.width, result.height) == pytest.approx(
        (expected.width, expected.height),
    )
    assert result.outline == expected.outline
    assert result.bend_lines == expected.bend_lines


def _features(result, state, family="金庫型", **values_override):
    v = values() | values_override
    return manufacturing_api.project_operator_door_cell_features(
        result, (), state,
        cell_width=420.0, cell_height=600.0, frame_edges=DoorFrameEdges(),
        family_model=family, frame_width=v["fw"], thickness=v["t"],
        gap_w=v["door_gap_w"], gap_h=v["door_gap_h"],
        fold_left=v["door_fold_l"], fold_bottom=v["door_fold_b"],
    )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_indicator_lamp_projection_matches_previous_ae_layout(family):
    v = values()
    edges = DoorFrameEdges()
    fw = family_policy.door_material_frame_width(
        family, frame_width=v["fw"], thickness=v["t"],
    )
    structural = manufacturing_api.project_operator_door_cell_result(
        v, cell_width=420.0, cell_height=600.0,
        frame_edges=edges, material_frame_width=fw,
    )
    state = {"mode": "indicator", "groups": [2], "layers": 1,
             "offset_x": 10.0, "offset_y": 7.0}
    actual = _features(structural, state, family=family)
    finished = ae.calculate_door_finished_size(
        420.0, 600.0, fw, v["door_gap_w"], v["door_gap_h"], v["t"],
        frame_edges=edges,
    )
    expected = resolve_door_indicator_layout(
        DoorIndicatorContext(
            finished_width=float(finished[0]), finished_height=float(finished[1]),
            left_fold=v["door_fold_l"], bottom_fold=v["door_fold_b"],
        ), (2,), Vec2(10.0, 7.0),
    ).features
    assert actual == list(expected)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_indicator_box_opening_and_invalid_preview_only(family):
    v = values()
    fw = family_policy.door_material_frame_width(
        family, frame_width=v["fw"], thickness=v["t"],
    )
    structural = manufacturing_api.project_operator_door_cell_result(
        v, cell_width=420.0, cell_height=600.0,
        frame_edges=DoorFrameEdges(), material_frame_width=fw,
    )
    state = {"mode": "indicator_box", "groups": [2], "layers": 1,
             "offset_x": 3.0, "offset_y": -2.0}
    holes = _features(structural, state, family=family)
    assert len(holes) == 1
    hole = holes[0]
    assert hole.layer == "CUTTING"
    assert hole.source_type == "indicator_box_opening"
    assert (hole.width, hole.height) == pytest.approx(
        manufacturing_api.indicator_box_opening_size((2,), thickness=v["t"]),
    )
    finished = ae.calculate_door_finished_size(
        420.0, 600.0, fw, v["door_gap_w"], v["door_gap_h"], v["t"],
        frame_edges=DoorFrameEdges(),
    )
    assert (hole.center.x, hole.center.y) == pytest.approx((
        v["door_fold_l"] + finished[0] / 2 + 3.0,
        v["door_fold_b"] + finished[1] / 2 - 2.0,
    ))
    assert _features(structural, {"mode": "indicator", "groups": ["bad"]},
                     family=family) == []
    assert _features(structural, {"mode": "none"}, family=family) == []


def test_engine_baseline_projection_reuses_scene_and_invalidates_source(monkeypatch):
    scene = object()
    calls = []
    monkeypatch.setattr(ae, "has_baseline_part", lambda model, part: True)
    monkeypatch.setattr(ae, "baseline_expected_path",
                        lambda model, part: "/tmp/door-source.dxf")
    fingerprint = ["source-one"]
    monkeypatch.setattr(ae, "baseline_source_fingerprint",
                        lambda path: (fingerprint[0],))
    monkeypatch.setattr(ae, "baseline_source_label",
                        lambda model, part: "source:" + str(model))
    def stretch(model, *args, **kwargs):
        calls.append((model, args, kwargs))
        return SimpleNamespace(scene=scene)
    monkeypatch.setattr(ae, "get_stretched_door_data", stretch)
    cache = {}
    kwargs = dict(family_model="受電箱", cell_width=420.0, cell_height=600.0,
                  frame_edges=DoorFrameEdges(), cache=cache)
    a = manufacturing_api.project_operator_door_cell_baseline(values(), **kwargs)
    b = manufacturing_api.project_operator_door_cell_baseline(values(), **kwargs)
    assert a == b == (scene, "source:金庫型")
    assert len(calls) == 1
    assert calls[0][0] == "金庫型"
    assert calls[0][2]["frame_edges"] == kwargs["frame_edges"]
    assert calls[0][2]["nameplate_center_datum_top"] == (
        family_policy.door_nameplate_center_datum_top("受電箱")
    )
    fingerprint[0] = "source-two"
    manufacturing_api.project_operator_door_cell_baseline(values(), **kwargs)
    assert len(calls) == 2


def test_engine_baseline_missing_and_parse_error_keep_legacy_display(monkeypatch):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: False)
    monkeypatch.setattr(ae, "baseline_source_label",
                        lambda model, part: f"missing:{model}")
    assert manufacturing_api.project_operator_door_cell_baseline(
        values(), family_model="金庫型", cell_width=420.0, cell_height=600.0,
        frame_edges=DoorFrameEdges(),
    ) == (None, "missing:")
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: True)
    monkeypatch.setattr(ae, "baseline_expected_path", lambda *args: "/tmp/test.dxf")
    monkeypatch.setattr(ae, "baseline_source_fingerprint", lambda path: ("fp",))
    def bad(*args, **kwargs):
        raise ValueError("invalid baseline")
    monkeypatch.setattr(ae, "get_stretched_door_data", bad)
    assert manufacturing_api.project_operator_door_cell_baseline(
        values(), family_model="金庫型", cell_width=420.0, cell_height=600.0,
        frame_edges=DoorFrameEdges(),
    ) == (None, "未使用基準檔（程式計算生成）")


def test_gui_cell_preview_delegates_all_three_decisions(monkeypatch):
    tokens = (object(), object(), object())
    seen = []
    monkeypatch.setattr(manufacturing_api, "project_operator_door_cell_result",
                        lambda *a, **k: seen.append(("result", a, k)) or tokens[0])
    monkeypatch.setattr(manufacturing_api, "project_operator_door_cell_features",
                        lambda *a, **k: seen.append(("features", a, k)) or [tokens[1]])
    monkeypatch.setattr(manufacturing_api, "project_operator_door_cell_baseline",
                        lambda *a, **k: seen.append(("baseline", a, k)) or (tokens[2], "source"))
    class Var:
        def __init__(self, v):
            self.v = v
        def get(self):
            return self.v
    v = values()
    cell = SimpleNamespace(
        start_width=420.0, start_height=600.0, edges=DoorFrameEdges(),
    )
    host = SimpleNamespace(
        get_float_values=lambda: v,
        _door_material_frame_width=lambda fw, t: 25.0,
        door_layout_features={},
        _door_layout_indicator_state_for_key=lambda key: {"mode": "indicator"},
        _baseline_source_model=lambda: "金庫型",
        fw_z_var=Var(25.0), t_var=Var(2.0),
        door_gap_w_var=Var(3.5), door_gap_h_var=Var(4.0),
        door_fold_l_var=Var(15.0), door_fold_b_var=Var(14.0),
        _door_layout_baseline_cache={},
    )
    assert gui_adapter._door_layout_cell_result(host, cell, v) is tokens[0]
    assert gui_adapter._door_layout_cell_resolved_features(
        host, cell, tokens[0], "0:0",
    ) == [tokens[1]]
    assert gui_adapter._door_layout_baseline_scene(
        host, cell, v,
    ) == (tokens[2], "source")
    assert [x[0] for x in seen] == ["result", "features", "baseline"]
    assert seen[1][1][1] is host.door_layout_features["0:0"]
    assert seen[2][1][0] is v
    source = Path(gui_adapter.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import ae_engine.ae as ae", "build_door_result(",
        "ae.calculate_door_finished_size(", "ae.get_stretched_door_data(",
        "resolve_surface_features(", "resolve_door_indicator_layout(",
        "cabinet_family_policy.",
    ):
        assert forbidden not in source
