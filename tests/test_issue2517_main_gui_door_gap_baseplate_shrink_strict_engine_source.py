"""#2517: main GUI Door gap/BasePlate shrink must match original PartSpec source.

Unlike W/H/D/T/FW, the existing Engine part-dimensions API previously used
_num on authored gap/shrink, turning True into one millimetre and invalid
strings into plausible defaults. GUI may display only the physical source
that the actual Door/BasePlate PartSpecs will accept.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
import fold_designer_bridge as bridge
import phase6_project_file as project
from tests.test_issue2517_door_part_projection_saved_source_parity import _snapshot


def _gui_part_dimensions(source):
    host = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(source),
        _settings_values={},
    )
    before = deepcopy(host._phase6_input_snapshot)
    try:
        dimensions = bridge._phase6_recalculate_part_dimensions(host)
    except (ValueError, TypeError):
        assert host._phase6_input_snapshot == before
        raise
    assert host._phase6_input_snapshot["part_dimensions"] == dimensions
    return dimensions


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("enabled", (False, "true"))
@pytest.mark.parametrize("field", ("door_gap_w", "door_gap_h"))
@pytest.mark.parametrize("invalid", (
    True, False, None, float("nan"), float("inf"),
    "nan", "inf", "not-a-gap", [], {},
))
def test_corrupt_door_gap_cannot_become_gui_single_or_multi_door_mm(
    family, enabled, field, invalid,
):
    source = _snapshot(family)
    source["multi_door_enabled"] = enabled
    source[field] = invalid
    before = repr(source)
    if enabled == "true":
        with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
            api.door_part_projections(source)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        api.project_part_dimensions(source)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        _gui_part_dimensions(source)
    assert repr(source) == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("enabled", (False, "true"))
@pytest.mark.parametrize("edge", ("left", "right", "top", "bottom"))
@pytest.mark.parametrize("invalid", (
    True, False, None, float("nan"), float("inf"),
    "nan", "inf", "not-a-shrink", [], {},
))
def test_corrupt_baseplate_shrink_cannot_change_manufacturing_part_inventory(
    family, enabled, edge, invalid,
):
    source = _snapshot(family)
    source["multi_door_enabled"] = enabled
    source[f"base_plate_shrink_{edge}"] = invalid
    before = repr(source)
    with pytest.raises(ValueError, match="製造來源必須是有限非布林數值"):
        api.project_part_dimensions(source)
    with pytest.raises(ValueError, match="製造來源必須是有限非布林數值"):
        _gui_part_dimensions(source)
    assert repr(source) == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_missing_legacy_gap_and_shrink_use_only_original_missing_defaults(family):
    source = _snapshot(family)
    source["multi_door_enabled"] = "true"
    for key in ("door_gap_w", "door_gap_h", "base_plate_shrink_left",
                "base_plate_shrink_right", "base_plate_shrink_top",
                "base_plate_shrink_bottom"):
        source.pop(key, None)
    before = deepcopy(source)
    explicit = deepcopy(source)
    explicit.update({
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "base_plate_shrink_left": 55.0, "base_plate_shrink_right": 55.0,
        "base_plate_shrink_top": 55.0, "base_plate_shrink_bottom": 55.0,
    })
    assert api.door_part_projections(source) == api.door_part_projections(explicit)
    assert api.project_part_dimensions(source) == api.project_part_dimensions(explicit)
    assert source == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_signed_fractional_legacy_settings_keep_original_engine_semantics(family):
    source = _snapshot(family)
    source.update({
        "door_gap_w": "0.125", "door_gap_h": "4.625",
        "base_plate_shrink_left": "-1.75",
        "base_plate_shrink_right": "55.625",
        "base_plate_shrink_top": "54.125",
        "base_plate_shrink_bottom": "55.375",
    })
    before = deepcopy(source)
    dims = api.project_part_dimensions(source)
    assert dims == _gui_part_dimensions(source)
    assert dims["base_plate"] == {
        "width": pytest.approx(800.0 + 1.75 - 55.625),
        "height": pytest.approx(1600.0 - 54.125 - 55.375),
    }
    cell = api.door_part_projections(source)[0]
    spec = api.build_door_operator_part_spec(
        {
            "w": cell.start_width, "h": cell.start_height,
            "t": source["t"], "fw": source["fw"],
            "door_gap_w": source["door_gap_w"],
            "door_gap_h": source["door_gap_h"],
            "door_fold_l": 19.0, "door_fold_r": 19.0,
            "door_fold_t": 19.0, "door_fold_b": 19.0,
        },
        model_name=family, frame_edges=cell.frame_edges,
    )
    assert (cell.formed_width, cell.formed_height) == pytest.approx(
        api.door_finished_face_size(spec),
    )
    assert source == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field", ("door_gap_w", "door_gap_h"))
def test_negative_gap_is_rejected_by_original_door_forming_solver_not_sanitized(
    family, field,
):
    source = _snapshot(family)
    source[field] = "-0.125"
    before = deepcopy(source)
    # Operator number parsing preserves signed text, but the original
    # formed-face/physical Door solver prohibits a negative clearance.
    with pytest.raises(ValueError, match="FW and gaps nonnegative"):
        api.door_part_projections(source)
    with pytest.raises(ValueError, match="FW and gaps nonnegative"):
        api.project_part_dimensions(source)
    with pytest.raises(ValueError, match="FW and gaps nonnegative"):
        _gui_part_dimensions(source)
    assert source == before


def test_real_p6fold_reopen_main_gui_2d_matches_engine_door_dxf_and_signed_shrink(
    tmp_path,
):
    source = _snapshot("金庫型")
    source["multi_door_enabled"] = "true"
    source.update({
        "door_gap_w": "4.625", "door_gap_h": "3.125",
        "base_plate_shrink_left": "56.125",
        "base_plate_shrink_right": "54.875",
        "base_plate_shrink_top": "55.25",
        "base_plate_shrink_bottom": "54.75",
    })
    original = deepcopy(source)
    target = project.write_project(
        tmp_path / "verified-signed-door-gap-base-shrink.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    restored = project.read_project(target)["snapshot"]
    before = deepcopy(restored)
    gui = _gui_part_dimensions(restored)
    assert gui == api.project_part_dimensions(restored)
    upper = api.door_part_projections(restored)[0]
    assert gui[upper.part_key] == pytest.approx({
        "width": upper.formed_width, "height": upper.formed_height,
    })
    assert gui["base_plate"] == pytest.approx({
        "width": 800.0 - 56.125 - 54.875,
        "height": 1600.0 - 55.25 - 54.75,
    })
    spec = api.build_door_operator_part_spec(
        {
            "w": upper.start_width, "h": upper.start_height,
            "t": restored["t"], "fw": restored["fw"],
            "door_gap_w": restored["door_gap_w"],
            "door_gap_h": restored["door_gap_h"],
            "door_fold_l": 19.0, "door_fold_r": 19.0,
            "door_fold_t": 19.0, "door_fold_b": 19.0,
        },
        model_name="金庫型", frame_edges=upper.frame_edges,
    )
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    assert api.door_finished_face_size(spec, context) == pytest.approx(
        (upper.formed_width, upper.formed_height),
    )
    real = api.build_part_render_data(spec, context)
    assert real.material is not None and real.material.area > 0
    path = tmp_path / "verified-door.dxf"
    written = api.save_part_render_data_dxf(real, path, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(real, written).ok
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in ezdxf.readfile(path).modelspace()
    }
    assert source == original and restored == before
