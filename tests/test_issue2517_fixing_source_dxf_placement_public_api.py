"""#2517 original fixing-plate source DXF and saved Placement consume public Engine."""
from copy import deepcopy
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_base_fixing_plate_geometry import (
    save_independent_source_flat_dxf, SOURCE_DXF_SHA256,
)
from gui_modules.application import fold_designer_composition_state as gui
from tests.test_phase6_t16_receiving_placement import _snapshot as receiving_snapshot
from tests.test_issue37_vault_baseplate_placement import _vault_snapshot


def test_public_facade_reuses_same_source_writer_and_same_placement_owner():
    assert api.save_operator_fixing_plate_source_flat_dxf is save_independent_source_flat_dxf
    assert api.resolve_operator_assembly_placement is resolve_assembly_placement
    assert len(SOURCE_DXF_SHA256) == 64


@pytest.mark.parametrize("part_id", (
    "base_plate:fixing_plate:left",
    "base_plate:fixing_plate:right",
    "base_plate:fixing_plate:small_source",
))
def test_original_source_flat_dxf_real_save_and_reload(part_id, tmp_path):
    output = tmp_path / (part_id.rsplit(":", 1)[-1] + ".dxf")
    path = api.save_operator_fixing_plate_source_flat_dxf(part_id, output)
    assert str(path) == str(output)
    document = ezdxf.readfile(output)
    entities = tuple(document.modelspace())
    assert sum(x.dxf.layer == "CUTTING" and x.dxftype() == "LWPOLYLINE"
               for x in entities) == (3 if part_id.endswith("small_source") else 5)
    assert sum(x.dxf.layer == "BEND" and x.dxftype() == "LINE"
               for x in entities) == 1
    assert not any(x.dxf.layer == "MARKING" for x in entities)
    with pytest.raises(FileExistsError):
        api.save_operator_fixing_plate_source_flat_dxf(part_id, output)
    assert output.exists()


@pytest.mark.parametrize("invalid", (
    "base_plate",
    "base_plate:fixing_plate:wrong",
    "base_plate:fixing_plate:nfb_layer:0:left",
))
def test_unproven_part_or_tier_cannot_write_source_dxf(invalid, tmp_path):
    path = tmp_path / "must-not-exist.dxf"
    with pytest.raises(ValueError):
        api.save_operator_fixing_plate_source_flat_dxf(invalid, path)
    assert not path.exists()


@pytest.mark.parametrize("source", (receiving_snapshot, _vault_snapshot))
def test_saved_project_placement_uses_same_source_and_no_mutation(source):
    snapshot = source()
    before = deepcopy(snapshot)
    for key in ("base_plate", "door_c1_r1"):
        try:
            physical = resolve_assembly_placement(snapshot, key)
        except ValueError:
            continue
        assert api.resolve_operator_assembly_placement(snapshot, key) == physical
    assert snapshot == before


def test_gui_routes_both_source_flat_and_persisted_placement_via_engine_api():
    export = inspect.getsource(gui.export_selected_dxf_from_3d)
    assert "manufacturing_api.save_operator_fixing_plate_source_flat_dxf(" in export
    assert "from ae_engine.receiving_base_fixing_plate_geometry import" not in export
    assert "save_independent_source_flat_dxf(" not in export
    saved = inspect.getsource(gui.collect_workspace_state)
    assert "resolver=manufacturing_api.resolve_operator_assembly_placement" in saved
    assert "from ae_engine.assembly_placement import" not in saved
