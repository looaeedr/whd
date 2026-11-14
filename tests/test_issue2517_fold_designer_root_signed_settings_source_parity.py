"""#2517 Fold Designer root 2D and PartSpecs share raw signed policy inputs.

Snapshot geometry cannot invent a 1-mm shrink or Indicator Fold by float(True).
The root overview is still display-only, NOT an independent per-cell source.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from gui_modules.application import fold_designer_snapshot_projection as gui
import phase6_project_file as project
from tests.test_issue2517_fold_designer_snapshot_dimensions_engine_api import (
    _controls, snapshot as _snapshot,
)


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("edge", ("left", "right", "top", "bottom"))
@pytest.mark.parametrize("invalid", (
    True, False, None, "nan", "inf", "invalid",
    float("nan"), float("inf"), [], {},
))
def test_invalid_raw_shrink_never_commits_fold_designer_part_dimensions(
    model, edge, invalid,
):
    source = _snapshot(model)
    source[f"base_plate_shrink_{edge}"] = invalid
    original = repr(source)
    with pytest.raises(ValueError, match="製造來源必須是有限非布林數值"):
        api.project_fold_designer_snapshot_dimensions(source, [2])
    ui = deepcopy(source)
    with pytest.raises(ValueError, match="製造來源必須是有限非布林數值"):
        gui._snapshot_part_dimensions(_controls([2]), ui)
    assert repr(ui) == original and repr(source) == original


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field", ("indicator_box_fold", "indicator_door_fold"))
@pytest.mark.parametrize("invalid", (
    True, False, None, "nan", "inf", "bad-fold",
    float("nan"), float("inf"), [], {},
))
def test_invalid_raw_indicator_fold_never_fabricates_physical_panel(
    model, field, invalid,
):
    source = _snapshot(model)
    source[field] = invalid
    original = repr(source)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        api.project_fold_designer_snapshot_dimensions(source, [2])
    ui = deepcopy(source)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        gui._snapshot_part_dimensions(_controls([2]), ui)
    assert repr(ui) == original and repr(source) == original


@pytest.mark.parametrize("field", ("door_gap_w", "door_gap_h"))
@pytest.mark.parametrize("invalid", (True, False, None, "nan", "inf", "bad-gap"))
def test_direct_root_door_gap_shares_original_partspec_source_rejection(
    field, invalid,
):
    source = _snapshot()
    source[field] = invalid
    prior = deepcopy(source)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        api.project_fold_designer_snapshot_dimensions(source, [2])
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        gui._snapshot_part_dimensions(_controls([2]), deepcopy(source))
    assert source == prior


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_valid_fractional_textual_sources_match_original_numeric_engine(
    model,
):
    source = _snapshot(model)
    source.update({
        "door_gap_w": "4.625", "door_gap_h": "3.125",
        "base_plate_shrink_left": "-1.75",
        "base_plate_shrink_right": "55.625",
        "base_plate_shrink_top": "54.125",
        "base_plate_shrink_bottom": "55.375",
        "indicator_box_fold": "49.125",
        "indicator_door_fold": "19.25",
    })
    before = deepcopy(source)
    numeric = deepcopy(source)
    for field in (
        "door_gap_w", "door_gap_h",
        "base_plate_shrink_left", "base_plate_shrink_right",
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "indicator_box_fold", "indicator_door_fold",
    ):
        numeric[field] = float(numeric[field])
    root = api.project_fold_designer_snapshot_dimensions(source, [2])
    expected = api.project_fold_designer_snapshot_dimensions(numeric, [2])
    assert root == expected
    ui = deepcopy(source)
    assert gui._snapshot_part_dimensions(_controls([2]), ui)["part_dimensions"] == root.part_dimensions
    assert root.part_dimensions["base_plate"]["width"] > 0
    assert source == before


def test_actual_p6fold_reload_root_2d_indicator_and_door_dxf_use_same_physical_source(
    tmp_path,
):
    source = _snapshot("金庫型")
    source.update({
        "door_gap_w": "4.625", "door_gap_h": "3.125",
        "base_plate_shrink_left": "56.125",
        "base_plate_shrink_right": "54.875",
        "base_plate_shrink_top": "55.25",
        "base_plate_shrink_bottom": "54.75",
        "indicator_box_fold": "49.125",
        "indicator_door_fold": "19.25",
    })
    prior = deepcopy(source)
    target = project.write_project(
        tmp_path / "fold-root-policy-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    saved = project.read_project(target)["snapshot"]
    saved_before = deepcopy(saved)
    ui = deepcopy(saved)
    gui._snapshot_part_dimensions(_controls([2]), ui)
    root = api.project_fold_designer_snapshot_dimensions(saved, [2])
    assert ui["part_dimensions"] == root.part_dimensions

    spec = api.build_door_operator_part_spec(
        {
            "w": saved["w"], "h": saved["h"], "t": saved["t"],
            "fw": saved["fw"],
            "door_gap_w": saved["door_gap_w"],
            "door_gap_h": saved["door_gap_h"],
            "door_fold_l": 19.0, "door_fold_r": 19.0,
            "door_fold_t": 19.0, "door_fold_b": 19.0,
        },
        model_name="金庫型",
    )
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    assert api.door_finished_face_size(spec, context) == pytest.approx(
        tuple(root.part_dimensions["door"].values()),
    )
    render = api.build_part_render_data(spec, context)
    assert render.material is not None and render.material.area > 0
    dxf = tmp_path / "root-verified-door.dxf"
    actual = api.save_part_render_data_dxf(render, dxf, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, actual).ok
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in ezdxf.readfile(dxf).modelspace()
    }
    assert source == prior and saved == saved_before
