"""#2517: main GUI recalculated BasePlate sizes share the Receiving Family owner.

The Fold Designer root snapshot and PartSpec were fixed separately, but the
existing public Engine project_part_dimensions was still case-sensitive and
could invent Vault-style per-cell BasePlates for genuine Receiving aliases.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types.policy import canonical_family_name
from ae_engine.contracts import ManufacturingContext
from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions
import fold_designer_bridge as bridge
import phase6_project_file as project
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import (
    _configured, _part_spec,
)

_ALIASES = ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ")


def _with_door_cells(model):
    source = _configured(model)
    source["multi_door_enabled"] = "true"
    source["door_layout_columns"] = [[800.0, [1100.0, 500.0]]]
    return source


def _gui_recalculated(source):
    holder = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(source),
        _settings_values={},
    )
    derived = bridge._phase6_recalculate_part_dimensions(holder)
    assert holder._phase6_input_snapshot["part_dimensions"] == derived
    return derived


@pytest.mark.parametrize("model", _ALIASES)
def test_main_gui_and_fold_designer_root_share_one_real_baseplate_for_alias(model):
    source = _with_door_cells(model)
    before = deepcopy(source)
    assert canonical_family_name(source) == "受電箱"

    expected = receiving_base_plate_blank_dimensions(source)
    root = api.project_fold_designer_snapshot_dimensions(source, [2]).part_dimensions
    direct = api.project_part_dimensions(source)
    via_gui = _gui_recalculated(source)
    assert tuple(root["base_plate"].values()) == pytest.approx(expected)
    assert direct["base_plate"] == pytest.approx(root["base_plate"])
    assert via_gui["base_plate"] == pytest.approx(root["base_plate"])
    assert "door_c1_r1" in direct and "door_c1_r2" in direct
    assert "base_plate_c1_r1" not in direct
    assert "base_plate_c1_r2" not in direct
    assert not any(k.startswith("base_plate_c") for k in via_gui)
    values, spec = _part_spec(source)
    assert spec.receiving_bend_pattern == values["receiving_bend_pattern"]
    assert source == before


@pytest.mark.parametrize("model", _ALIASES)
def test_actual_reload_keeps_same_baseplate_in_all_public_gui_dimensions(
    tmp_path, model,
):
    source = _with_door_cells(model)
    original = deepcopy(source)
    saved = project.write_project(
        tmp_path / ("saved-" + model.strip() + ".p6fold"),
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    reloaded = project.read_project(saved)["snapshot"]
    assert canonical_family_name(reloaded) == "受電箱"
    before = deepcopy(reloaded)
    expected = api.project_fold_designer_snapshot_dimensions(
        reloaded, [2],
    ).part_dimensions["base_plate"]
    projected = api.project_part_dimensions(reloaded)
    assert projected["base_plate"] == pytest.approx(expected)
    assert _gui_recalculated(reloaded)["base_plate"] == pytest.approx(expected)
    assert not any(k.startswith("base_plate_c") for k in projected)
    assert reloaded == before and source == original


def test_actual_gui_recalculation_matches_original_receiving_formed_dxf(tmp_path):
    source = _with_door_cells("receiving")
    target = project.write_project(
        tmp_path / "receiving-physical-base.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    restored = project.read_project(target)["snapshot"]
    dimensions = _gui_recalculated(restored)["base_plate"]
    physical = receiving_base_plate_blank_dimensions(restored)
    assert tuple(dimensions.values()) == pytest.approx(physical)
    _values, spec = _part_spec(restored)
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    render = api.build_part_render_data(spec, context)
    assert render.material is not None and render.material.area > 0
    path = tmp_path / "physical-receiving-base.dxf"
    saved = api.save_part_render_data_dxf(render, path, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, saved).ok
    reopened = ezdxf.readfile(path)
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in reopened.modelspace()
    }


def test_vault_multi_door_keeps_distinct_per_cell_baseplates_without_borrowing_receiving():
    source = _with_door_cells("金庫型")
    before = deepcopy(source)
    assert canonical_family_name(source) == "金庫型"
    via_gui = _gui_recalculated(source)
    direct = api.project_part_dimensions(source)
    assert via_gui == direct
    assert direct["base_plate"] == {"width": 690.0, "height": 1490.0}
    assert "base_plate_c1_r1" in direct and "base_plate_c1_r2" in direct
    assert source == before
