"""#2517 Door-layout operator preview geometry, indicator and baseline ownership."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
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
    assert result.bends == expected.bends


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
        _door_material_frame_width=lambda *args, **kwargs:
            pytest.fail("GUI must not pre-resolve material FW for Door cell"),
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
    assert seen[0][1][0] is v
    assert seen[0][2] == {
        "cell_width": cell.start_width, "cell_height": cell.start_height,
        "frame_edges": cell.edges, "family_model": "金庫型",
    }
    assert seen[1][1][1] == []
    # A preview is read-only; missing source rows must not become saved Features.
    assert host.door_layout_features == {}
    assert seen[2][1][0] is v
    source = Path(gui_adapter.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import ae_engine.ae as ae", "build_door_result(",
        "ae.calculate_door_finished_size(", "ae.get_stretched_door_data(",
        "resolve_surface_features(", "resolve_door_indicator_layout(",
        "cabinet_family_policy.",
    ):
        assert forbidden not in source


@pytest.mark.parametrize("invalid", (
    {"groups": [True], "layers": 1},
    {"groups": [1.5], "layers": 1},
    {"groups": [0], "layers": 1},
    {"groups": [9], "layers": 1},
    {"groups": [2], "layers": True},
    {"groups": [2], "layers": 7},
    {"groups": [2], "layers": 1, "offset_x": float("nan")},
))
def test_preview_does_not_fabricate_physical_indicator_holes_from_bad_source(invalid):
    v = values()
    result = manufacturing_api.project_operator_door_cell_result(
        v, cell_width=420.0, cell_height=600.0,
        frame_edges=DoorFrameEdges(), material_frame_width=25.0,
    )
    raw = {
        "mode": "indicator", "groups": [2], "layers": 1,
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    raw.update(invalid)
    before = deepcopy(raw)
    assert _features(result, raw) == []
    assert raw == before


def test_gui_door_cell_2d_preview_does_not_invoke_mutating_display_accessor(monkeypatch):
    raw = {
        "mode": "indicator", "groups": [False, 2], "layers": 1,
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    before = deepcopy(raw)
    visited = []
    class Var:
        def __init__(self, v): self.v = v
        def get(self): return self.v
    def manufacturing_preview(result, features, state, **kwargs):
        visited.append(("engine", state))
        return []
    monkeypatch.setattr(
        manufacturing_api, "project_operator_door_cell_features",
        manufacturing_preview,
    )
    host = SimpleNamespace(
        door_layout_indicator_states={"0:0": raw},
        _door_layout_indicator_state_for_key=lambda key:
            pytest.fail("display accessor would mutate saved physical source"),
        door_layout_features={},
        _baseline_source_model=lambda: "金庫型",
        fw_z_var=Var(25.0), t_var=Var(2.0),
        door_gap_w_var=Var(3.5), door_gap_h_var=Var(4.0),
        door_fold_l_var=Var(15.0), door_fold_b_var=Var(14.0),
    )
    cell = SimpleNamespace(
        start_width=420.0, start_height=600.0, edges=DoorFrameEdges(),
    )
    assert gui_adapter._door_layout_cell_resolved_features(
        host, cell, object(), "0:0"
    ) == []
    assert visited == [("engine", raw)]
    assert host.door_layout_indicator_states["0:0"] is raw
    assert raw == before


def test_door_2d_preview_absent_cell_does_not_create_saved_state(monkeypatch):
    visited = []
    monkeypatch.setattr(
        manufacturing_api, "project_operator_door_cell_features",
        lambda result, features, state, **kwargs:
            visited.append(state) or [],
    )
    class Var:
        def __init__(self, v): self.v = v
        def get(self): return self.v
    host = SimpleNamespace(
        door_layout_indicator_states={},
        _door_layout_indicator_state_for_key=lambda key:
            pytest.fail("missing cell must not be initialized as physical source"),
        door_layout_features={},
        _baseline_source_model=lambda: "金庫型",
        fw_z_var=Var(25.0), t_var=Var(2.0),
        door_gap_w_var=Var(3.5), door_gap_h_var=Var(4.0),
        door_fold_l_var=Var(15.0), door_fold_b_var=Var(14.0),
    )
    cell = SimpleNamespace(
        start_width=420.0, start_height=600.0, edges=DoorFrameEdges(),
    )
    assert gui_adapter._door_layout_cell_resolved_features(
        host, cell, object(), "0:0"
    ) == []
    assert visited == [None]
    assert host.door_layout_indicator_states == {}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("edges", (
    DoorFrameEdges(),
    DoorFrameEdges(left=True, right=False, top=False, bottom=True),
))
def test_public_cell_preview_resolves_original_family_material_fw(family, edges):
    original = {**values(), "fw": "29.5", "t": "2.125"}
    before = dict(original)
    fw = manufacturing_api.door_material_frame_width(
        family, frame_width=original["fw"], thickness=original["t"],
    )
    direct = manufacturing_api.project_operator_door_cell_result(
        original, cell_width=420.0, cell_height=600.0,
        frame_edges=edges, family_model=family,
    )
    legacy_equivalent = manufacturing_api.project_operator_door_cell_result(
        original, cell_width=420.0, cell_height=600.0,
        frame_edges=edges, material_frame_width=fw,
    )
    assert direct.outline == legacy_equivalent.outline
    assert direct.bends == legacy_equivalent.bends
    assert (direct.width, direct.height) == pytest.approx(
        (legacy_equivalent.width, legacy_equivalent.height),
    )
    assert original == before


@pytest.mark.parametrize("source", (
    {"fw": True}, {"fw": float("nan")}, {"fw": 0},
    {"fw": "-1"}, {"t": False}, {"t": float("inf")}, {"t": "bad"},
))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_public_cell_preview_rejects_invalid_original_physical_fw_t_before_geometry(
    monkeypatch, family, source,
):
    original = {**values(), **source}
    before = dict(original)
    from ae_engine import operator_door_cell_projection as owner
    monkeypatch.setattr(
        owner, "build_door_result",
        lambda *args, **kw: pytest.fail("invalid physical frame reached geometry"),
    )
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_door_cell_result(
            original, cell_width=420.0, cell_height=600.0,
            frame_edges=DoorFrameEdges(), family_model=family,
        )
    assert original == before


def test_door_cell_preview_rejects_missing_or_competing_fw_owner():
    request = values()
    common = dict(cell_width=420.0, cell_height=600.0,
                  frame_edges=DoorFrameEdges())
    with pytest.raises(ValueError, match="DOOR_CELL_PREVIEW_FRAME_WIDTH_SOURCE_REQUIRED"):
        manufacturing_api.project_operator_door_cell_result(request, **common)
    with pytest.raises(ValueError, match="DOOR_CELL_PREVIEW_COMPETING_FRAME_WIDTH_SOURCES"):
        manufacturing_api.project_operator_door_cell_result(
            request, family_model="受電箱",
            material_frame_width=29.0, **common,
        )


def test_custom_cell_preview_uses_engine_familyless_fw_policy():
    request = values()
    result = manufacturing_api.project_operator_door_cell_result(
        request, cell_width=420.0, cell_height=600.0,
        frame_edges=DoorFrameEdges(), custom_source_model="自訂",
    )
    material_fw = family_policy.door_material_frame_width(
        None,
        frame_width=request["fw"], thickness=request["t"],
    )
    expected = build_door_result(
        w=420.0, h=600.0, t=request["t"], fw=material_fw,
        gap_w=request["door_gap_w"], gap_h=request["door_gap_h"],
        fold_left=request["door_fold_l"], fold_right=request["door_fold_r"],
        fold_top=request["door_fold_t"], fold_bottom=request["door_fold_b"],
        frame_edges=DoorFrameEdges(),
    )
    assert result.outline == expected.outline
    assert result.bends == expected.bends


@pytest.mark.parametrize("invalid_source", (
    {"fw": 0}, {"fw": ""}, {"t": 0}, {"t": ""},
))
def test_custom_cell_preview_keeps_engine_gate_for_invalid_fw_t(invalid_source):
    request = {**values(), **invalid_source}
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_door_cell_result(
            request, cell_width=420.0, cell_height=600.0,
            frame_edges=DoorFrameEdges(), custom_source_model="自訂",
        )


def test_gui_cell_preview_source_uses_explicit_custom_identity_only():
    import inspect
    text = inspect.getsource(gui_adapter._door_layout_cell_result)
    assert "custom_source_model" in text
    assert "operator_default_custom_model_name" in text
    assert "material_frame_width=" not in text
    assert "self._door_material_frame_width(" not in text


def test_gui_cell_preview_keeps_missing_source_gate_for_unknown_baseline(monkeypatch):
    seen = []
    original = manufacturing_api.project_operator_door_cell_result

    def capture(*args, **kwargs):
        seen.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(manufacturing_api, "project_operator_door_cell_result", capture)

    class Var:
        def get(self):
            return "未註冊型號"

    host = SimpleNamespace(
        get_float_values=values,
        _baseline_source_model=lambda: None,
        baseline_var=Var(),
    )
    cell = SimpleNamespace(start_width=420.0, start_height=600.0,
                           edges=DoorFrameEdges())
    with pytest.raises(ValueError, match="DOOR_CELL_PREVIEW_FRAME_WIDTH_SOURCE_REQUIRED"):
        gui_adapter._door_layout_cell_result(host, cell)
    assert seen == [{
        "cell_width": cell.start_width,
        "cell_height": cell.start_height,
        "frame_edges": cell.edges,
        "family_model": None,
    }]
