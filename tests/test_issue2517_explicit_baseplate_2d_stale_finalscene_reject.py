"""#2517 explicit Receiving BasePlate 2D cannot reuse stale verified FinalScene."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

import phase6_project_file as project
from ae_engine import manufacturing_api as api
from ae_engine.contracts import (
    ManufacturingContext, ResolvedManufacturingGeometry, ResolvedManufacturingPart,
)
from gui_modules.application.render_snapshots import base_plate_render_snapshot
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import (
    _configured, _part_spec,
)


def _real_installed_part(source):
    _values, spec = _part_spec(source)
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    rendered = api.build_part_render_data(spec, context)
    assert rendered.unfolded_topology is not None
    assert rendered.metadata["receiving_bend_pattern"] == spec.receiving_bend_pattern
    assert not rendered.material.is_empty
    return rendered, ResolvedManufacturingGeometry(
        parts=(ResolvedManufacturingPart("base_plate", rendered),),
    )


def _gui(host_source, resolved):
    designer = SimpleNamespace(
        _phase6_input_snapshot=host_source,
        _phase6_resolve_manufacturing_geometry=lambda: resolved,
        designer_workspace=SimpleNamespace(active_part="base_plate"),
    )
    return SimpleNamespace(fold_designer_app=designer)


@pytest.mark.parametrize("model", ("受電箱", "receiving", "ReCeIvInG"))
def test_real_explicit_config_without_numeric_csv_keeps_same_2d_3d_dxf_and_project(
    model, tmp_path,
):
    original = _configured(model)
    assert original.get("nfb_config_submitted") is not True
    stored = deepcopy(original)
    target = project.write_project(
        tmp_path / "explicit-base.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    reloaded = project.read_project(target)["snapshot"]
    assert reloaded["receiving_base_plate"] == stored["receiving_base_plate"]
    real, resolved = _real_installed_part(reloaded)
    projected = api.project_receiving_base_plate_2d_snapshot(
        reloaded, resolved, active_part="base_plate",
    )
    assert projected["render_data"] is real
    assert projected["receiving_physical_part_key"] == "base_plate"
    assert base_plate_render_snapshot(_gui(reloaded, resolved), reloaded) == projected
    assert original == stored

    # The same current physical FinalScene material/structural BEND sources
    # are independently reopened as actual sheet DXF, not simulated filename.
    dxf = tmp_path / "actual-physical-explicit-base.dxf"
    written = api.save_part_render_data_dxf(
        real, dxf, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(real, written).ok
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in ezdxf.readfile(dxf).modelspace()
    }


@pytest.mark.parametrize("model", ("受電箱", "receiving"))
@pytest.mark.parametrize("field,value", (
    ("height", 380.0),
    ("shrink_left", 30.0),
    ("pattern", "CENTER_DOUBLE_SIDE_FOLD"),
))
def test_authored_plate_change_rejects_stale_2d_even_without_submitted_csv(
    model, field, value,
):
    current = _configured(model)
    _render, resolved = _real_installed_part(current)
    assert api.project_receiving_base_plate_2d_snapshot(
        current, resolved,
    )["receiving_physical_part_key"] == "base_plate"

    changed = deepcopy(current)
    changed["receiving_base_plate"][field] = value
    before = deepcopy(changed)
    with pytest.raises(ValueError, match="實體來源與已載入 2D 實體板型不一致"):
        api.project_receiving_base_plate_2d_snapshot(changed, resolved)
    with pytest.raises(ValueError, match="實體來源與已載入 2D 實體板型不一致"):
        base_plate_render_snapshot(_gui(changed, resolved), changed)
    assert changed == before


def test_missing_authoritative_explicit_plate_does_not_redisplay_old_real_sheet():
    source = _configured("receiving")
    _render, resolved = _real_installed_part(source)
    stale = deepcopy(source)
    stale.pop("receiving_base_plate")
    with pytest.raises(ValueError, match="尚未設定實體來源型式"):
        api.project_receiving_base_plate_2d_snapshot(stale, resolved)
