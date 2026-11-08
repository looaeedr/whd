# -*- coding: utf-8 -*-
"""#2517: Main GUI blank summary must use public Engine topology, not GUI bbox."""
import inspect
from types import SimpleNamespace
import pytest
from shapely.geometry import box
import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_render_data import (
    project_operator_main_blank_summary_dimensions as owner,
)
from gui_modules.application import calculation_controller as gui


def _render(w, h, topology=None):
    return api.PartRenderData(scene=object(), material=box(0, 0, w, h),
                              unfolded_topology=topology)


def _topology(w, h):
    return api.UnfoldedBlankTopology(
        piece_id="test",
        x_segments=(api.MaterialSegment("X", "core", w, "fold"),),
        y_segments=(api.MaterialSegment("Y", "core", h, "fold"),),
        source="fold",
    )


def test_public_root_facade_and_engine_owner_are_identical():
    assert api.project_operator_main_blank_summary_dimensions is owner
    assert ae_engine.project_operator_main_blank_summary_dimensions is owner
    assert "project_operator_main_blank_summary_dimensions" in ae_engine.__all__


@pytest.mark.parametrize("key", ["box_body", "head", "tail"])
def test_single_blank_matches_canonical_measurement(key):
    render = _render(422, 250)
    info = api.measure_unfolded_blanks(render, part_key=key)[0]
    assert owner(render, part_key=key) == (info.width, info.height)


def test_material_relief_does_not_shrink_canonical_blank():
    material = box(0, 0, 422, 250).difference(box(400, 225, 422, 250))
    raw = api.PartRenderData(scene=object(), material=material,
                             unfolded_topology=_topology(422, 250))
    assert owner(raw, part_key="head") == (422, 250)
    assert api.measure_unfolded_blanks(raw, part_key="head")[0].area < 422 * 250


def test_multipart_canonical_strip_not_exploded_summary():
    parts = (
        api.BoxBodyPieceRenderData("left", "left", 0, 100, (), _render(365, 596)),
        api.BoxBodyPieceRenderData("back", "back", 100, 700, (), _render(795, 596)),
        api.BoxBodyPieceRenderData("right", "right", 700, 800, (), _render(365, 596)),
    )
    source = api.BoxBodyStructureRenderData(
        structure_type="three_piece_side_back_split", pieces=parts,
        preview_render_data=_render(9999, 9999),
        canonical_strip_render_data=_render(800, 596, _topology(800, 596)),
    )
    assert owner(source, part_key="box_body") == (800, 596)
    assert len(api.measure_unfolded_blanks(source, part_key="box_body")) == 3


def test_missing_multipart_strip_fails_closed():
    source = SimpleNamespace(pieces=(object(),), material=box(0, 0, 9999, 9999))
    with pytest.raises(ValueError, match="CANONICAL_SUMMARY_STRIP_REQUIRED"):
        owner(source, part_key="box_body")


@pytest.mark.parametrize("key", ["door", "base_plate", ""])
def test_invalid_role_never_claims_endcap_or_box_body(key):
    with pytest.raises(ValueError, match="unsupported"):
        owner(_render(10, 10), part_key=key)


class Var:
    def __init__(self):
        self.value = None
    def set(self, value):
        self.value = value


def test_gui_delegates_real_box_and_head_to_engine(monkeypatch):
    calls = []
    def tracking(data, *, part_key):
        calls.append(part_key)
        return owner(data, part_key=part_key)
    monkeypatch.setattr(api, "project_operator_main_blank_summary_dimensions", tracking)
    values = {"w": 800., "h": 1600., "t": 2., "fw": 25.}
    host = SimpleNamespace(
        get_float_values=lambda: values,
        _box_body_part_spec=lambda val: "box_body",
        _end_cap_part_spec=lambda val, is_tail=False: "tail" if is_tail else "head",
        _authoritative_render_data=lambda part, ctx: _render(
            900 if part == "box_body" else 460, 596 if part == "box_body" else 250),
        _manufacturing_context=lambda **kwargs: None,
        _baseline_source_model=lambda: "",
        _phase6_current_existing_parts=lambda: {"head"},
        workspace_controller=SimpleNamespace(part_profiles_snapshot=lambda: {"head": (object(),)}),
        _phase6_logical_part_present=lambda parts, part: False,
        _door_material_frame_width=lambda fw, t: fw,
        multi_door_enabled_var=SimpleNamespace(get=lambda: False),
        _clear_indicator_box_result_values=lambda: None,
        _phase6_refresh_presence_ui=lambda parts: None,
        draw_preview=lambda: None,
    )
    for key in ("z", "z_h", "y_w", "y_d", "door_w", "door_h",
                "base_plate_w", "base_plate_h", "ib_w", "ib_h",
                "ib_door_w", "ib_door_h"):
        setattr(host, "result_" + key + "_var", Var())
    gui.update_calculations(host)
    assert calls == ["box_body", "head"]
    assert host.result_z_var.value == "900.00 mm"
    assert host.result_y_w_var.value == "460.00 mm"
    assert host.result_y_d_var.value == "250.00 mm"


def test_gui_source_contains_no_material_bbox_formula():
    code = inspect.getsource(gui.update_calculations)
    assert "project_operator_main_blank_summary_dimensions(" in code
    assert "canonical_strip_render_data" not in code
    assert ".material.bounds" not in code
    assert "from ae_engine import manufacturing_api" not in code
