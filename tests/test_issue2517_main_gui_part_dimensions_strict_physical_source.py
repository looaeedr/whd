"""#2517 main GUI physical part sizes use the same strict Engine source as MFG.

The original part dimensions and multi-door physical cell API must not
fabricate positive dimensions from explicit bool, NaN or invalid Tk text.
True missing legacy schematic inputs retain their prior Engine defaults.
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
from tests.test_issue2517_door_part_projection_saved_source_parity import (
    _snapshot,
)


def _gui_recalculate(source):
    app = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(source),
        _settings_values={},
    )
    original_state = deepcopy(app._phase6_input_snapshot)
    try:
        result = bridge._phase6_recalculate_part_dimensions(app)
    except (ValueError, TypeError):
        # Failed Engine qualification cannot partially publish a new
        # part_dimensions map into the original operator project source.
        assert app._phase6_input_snapshot == original_state
        raise
    return result


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
@pytest.mark.parametrize("invalid", (True, False, None, 0, -1, "nan",
                                      "inf", "not-a-size", float("nan")))
def test_explicit_corrupt_main_gui_physical_mm_rejected_before_any_dimensions(
    family, field, invalid,
):
    source = _snapshot(family)
    source["multi_door_enabled"] = False
    source[field] = invalid
    prior = repr(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_part_dimensions(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        _gui_recalculate(source)
    assert repr(source) == prior


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field", ("t", "fw"))
@pytest.mark.parametrize("invalid", (True, False, None, 0, -1, "nan",
                                      "inf", "not-a-size", float("nan")))
def test_saved_multi_door_finished_dims_refuse_corrupt_material_source(
    family, field, invalid,
):
    source = _snapshot(family)
    source[field] = invalid
    prior = repr(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.door_part_projections(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_part_dimensions(source)
    assert repr(source) == prior


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_missing_legacy_preview_physical_fields_keep_original_default_profile(family):
    legacy = {"model": family}
    root = api.project_part_dimensions(legacy)
    assert root["box_body"] == {"width": 500.0, "height": 600.0}
    assert root["head"] == {"width": 500.0, "height": 200.0}
    assert root["tail"] == {"width": 500.0, "height": 200.0}
    assert "door" in root and "base_plate" in root

    multi = _snapshot(family)
    multi.pop("t")
    multi.pop("fw")
    with_default = _snapshot(family)
    with_default["t"] = 2.0
    with_default["fw"] = 25.0
    assert api.door_part_projections(multi) == api.door_part_projections(with_default)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_fractional_textual_mm_never_round_or_replace_actual_saved_dimensions(family):
    source = _snapshot(family)
    source.update({"w": "800.125", "h": "1600.25", "d": "350.375",
                   "t": "2.125", "fw": "29.25"})
    source["multi_door_enabled"] = False
    prior = deepcopy(source)
    result = api.project_part_dimensions(source)
    gui = _gui_recalculate(source)
    assert gui == result
    assert result["box_body"] == {"width": 800.125, "height": 1600.25}
    assert result["head"] == {"width": 800.125, "height": 350.375}
    assert result["tail"] == {"width": 800.125, "height": 350.375}
    assert source == prior


def test_actual_p6fold_reload_gui_2d_and_existing_real_engine_dxf_source(tmp_path):
    source = _snapshot("金庫型")
    source["multi_door_enabled"] = "true"
    source["t"], source["fw"] = 2.125, 25.25
    original = deepcopy(source)
    target = project.write_project(
        tmp_path / "physical-door-part-size.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    loaded = project.read_project(target)["snapshot"]
    before = deepcopy(loaded)
    gui = _gui_recalculate(loaded)
    engine = api.project_part_dimensions(loaded)
    assert gui == engine
    rows = api.door_part_projections(loaded)
    assert len(rows) == 2
    upper = rows[0]
    assert gui[upper.part_key] == pytest.approx({
        "width": upper.formed_width, "height": upper.formed_height,
    })
    spec = api.build_door_operator_part_spec(
        {
            "w": upper.start_width, "h": upper.start_height,
            "t": loaded["t"], "fw": loaded["fw"],
            "door_gap_w": loaded["door_gap_w"], "door_gap_h": loaded["door_gap_h"],
            "door_fold_l": 10.0, "door_fold_r": 10.0,
            "door_fold_t": 10.0, "door_fold_b": 10.0,
        },
        model_name="金庫型", frame_edges=upper.frame_edges,
    )
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    result = api.build_part_render_data(spec, context)
    assert result.material is not None and result.material.area > 0
    dxf = tmp_path / "real-door.dxf"
    saved = api.save_part_render_data_dxf(result, dxf, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(result, saved).ok
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in ezdxf.readfile(dxf).modelspace()
    }
    assert source == original and loaded == before
