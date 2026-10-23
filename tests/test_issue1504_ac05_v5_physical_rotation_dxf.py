# -*- coding: utf-8 -*-
"""#1504 AC-05: current source CSV quarter turns in *real* inner-door/plate DXF.

Uses the canonical committed NFBConfig -> WHD FinalScene -> original operator
pair-export path; compares actual CUTTING coordinates independently to the
numeric CSV corners, not the historical native DXF/SHADOW test samples.
Whole-cabinet welding, NC, Windows operator GUI remain separate.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.receiving_nfb_manufacturing_release import _resolve_physical_panel
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from tests.test_issue1502_current_csv_original_pair_dxf import _scene, _export
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current

ROTATIONS = {
    0: ((1., 0.), (0., 1.)),
    90: ((0., 1.), (-1., 0.)),
    180: ((-1., 0.), (0., -1.)),
    270: ((0., -1.), (1., 0.)),
}


def _one_switch(angle):
    snap = _current()
    config = snap["nfb_config"]
    config["holes"] = [config["holes"][0]]
    config["holes"][0]["rotation_deg"] = angle
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(config)
    return snap


def _as_vertices(points):
    return tuple(sorted((round(float(x), 5), round(float(y), 5)) for x, y in points))


def _expected_source_vertices(snap, rotation):
    panel, placement = _resolve_physical_panel(snap, "upper")
    assert panel == next(p for p in derive_inner_door_panels(snap)
                         if p.stable_id == panel.stable_id)
    hole = snap["nfb_config"]["holes"][0]
    source = model_spec("士林", "2P400")
    assert source is not None and len(source.opening_corners_xy_mm) == 4
    core_width = panel.unfolded_width - panel.fold_left - panel.fold_right
    u = (float(panel.fold_left) + core_width / 2
         + float(hole["manual_x_mm"]) - float(placement.world_offset[0]))
    v = project_nfb_inner_door_nominal_y(
        snap, "upper", layer_count=1, slot_index=0,
    ).unfolded_uv_y_mm
    x_axis, y_axis = ROTATIONS[rotation]
    # Independent source-local -> physical UV quarter turn: no engine
    # AXES/project_nfb_v5_to_panel calls for expected vertex coordinates.
    vertices = tuple(
        (u + x*x_axis[0] + y*y_axis[0],
         v + x*x_axis[1] + y*y_axis[1])
        for x, y in source.opening_corners_xy_mm
    )
    return _as_vertices(vertices)


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
def test_ac05_committed_v5_rotation_real_finalscene_and_saved_dxf_match_numeric_csv(
    tmp_path, angle,
):
    snapshot = _one_switch(angle)
    before = deepcopy(snapshot)
    expected = _expected_source_vertices(snapshot, angle)
    parts = _scene(snapshot)
    door = next(p for p in parts if "inner_door" in str(p.part_key))
    source_contours = tuple(
        _as_vertices(tuple((v.x, v.y) for v in line.points))
        for line in door.render_data.scene.primitives
        if isinstance(line, PolylinePrimitive) and line.closed
        and line.layer.upper() == "CUTTING"
    )
    assert source_contours.count(expected) == 1
    assert door.render_data.metadata["nfb_v5_hole_ids"] == ("nfb:0",)
    assert door.render_data.metadata["nfb_trial_export_approved"] is False

    receipt = _export(snapshot, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:0",)
    assert len(receipt.check_q_key) == 64
    assert Path(receipt.inner_door_path).is_file()
    assert Path(receipt.base_plate_path).is_file()
    assert len(tuple(tmp_path.glob("*.dxf"))) == 2
    saved = ezdxf.readfile(receipt.inner_door_path).modelspace()
    saved_contours = tuple(
        _as_vertices(tuple(poly.get_points("xy")))
        for poly in saved
        if poly.dxftype() == "LWPOLYLINE" and poly.closed
        and poly.dxf.layer.upper() == "CUTTING"
    )
    assert saved_contours.count(expected) == 1
    assert snapshot == before, "Preview/export must not mutate committed NFB source"


def test_ac05_quarter_turn_pivot_is_world_x_stable_and_no_mirror(tmp_path):
    footprints = {}
    for angle in ROTATIONS:
        snap = _one_switch(angle)
        pattern = _expected_source_vertices(snap, angle)
        footprints[angle] = pattern
        assert tuple(sorted(ROTATIONS[angle][0]+ROTATIONS[angle][1]))
        x_axis, y_axis = ROTATIONS[angle]
        assert x_axis[0]*y_axis[1] - x_axis[1]*y_axis[0] == 1
        assert round(sum(p[0] for p in pattern)/4, 5) == round(
            sum(p[0] for p in footprints[0])/4, 5
        )
        assert round(sum(p[1] for p in pattern)/4, 5) == round(
            sum(p[1] for p in footprints[0])/4, 5
        )
    source = model_spec("士林", "2P400")
    size = sorted((round(max(v[i] for v in footprints[0])
                         - min(v[i] for v in footprints[0]), 5)
                   for i in (0, 1)))
    expected = sorted((
        round(max(p[i] for p in source.opening_corners_xy_mm)
              - min(p[i] for p in source.opening_corners_xy_mm), 5)
        for i in (0, 1)
    ))
    assert size == expected
    assert footprints[90] != footprints[0]
    assert footprints[270] != footprints[0]
    assert footprints[180] == footprints[0]  # symmetric rectangle; saved angle distinguishes


@pytest.mark.parametrize("bad", (-90, 45, 360, True, 90.0))
def test_ac05_invalid_rotation_fails_before_any_dxf_is_published(tmp_path, bad):
    snapshot = _one_switch(0)
    snapshot["nfb_config"]["holes"][0]["rotation_deg"] = bad
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snapshot["nfb_config"]
    )
    with pytest.raises(ValueError, match="rotation|旋轉|angle|NFB"):
        _scene(snapshot)
    assert not list(tmp_path.glob("*.dxf"))
