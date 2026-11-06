"""#2517: registered Family aliases must keep the original certified selected-DXF route.

This tests the real public Engine route and serialized side DXF. No alternative
exporter, fixture-only manufacturing approval, or GUI geometry is introduced.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api


def _flags(**changes):
    flags = {
        "box_body": True, "head": False, "tail": False,
        "door": False, "base_plate": False,
        "indicator_box": False, "indicator_door": False,
    }
    flags.update(changes)
    return flags


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", " ReCeIvInG "))
def test_submitted_real_csv_receiving_alias_keeps_exact_certified_selection(model):
    from tests.test_issue1502_single_button_full_csv_receiving_export import _prepare

    source, _ = _prepare(False)
    assert source["nfb_config_submitted"] is True
    canonical_auto, canonical_csv = manufacturing_api.selected_export_manufacturing_policy(
        source, _flags(),
    )
    aliased = deepcopy(source)
    aliased["model"] = model
    auto, committed_csv = manufacturing_api.selected_export_manufacturing_policy(
        aliased, _flags(),
    )
    assert canonical_auto and canonical_csv
    assert auto and committed_csv == canonical_csv
    route = manufacturing_api.plan_selected_resolved_export_route(
        aliased, _flags(door=True, base_plate=True),
    )
    assert route.vault_composed is False
    assert route.legacy_guard_flags is None
    assert aliased["model"] == model and source["model"] == "受電箱"


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", " ReCeIvInG "))
def test_submitted_legacy_nfb_receiving_alias_never_bypasses_old_body_gate(model):
    source = {
        "model": model,
        "nfb_config_submitted": True,
        "nfb_config": {"holes": [{"model_filename": "supplier-base.dxf"}]},
    }
    flags = _flags(door=True, base_plate=True)
    route = manufacturing_api.plan_selected_resolved_export_route(source, flags)
    assert not route.vault_composed
    assert dict(route.legacy_guard_flags) == {**flags, "box_body": False}


@pytest.mark.parametrize("model", ("金庫型", "VAULT", "vault", "  VaUlT  "))
def test_registered_vault_alias_uses_original_composed_group_route(model):
    route = manufacturing_api.plan_selected_resolved_export_route(
        {"model": model}, _flags(door=True), group_mode="ALL",
    )
    assert route.vault_composed
    assert dict(route.legacy_guard_flags)["door"]


@pytest.mark.parametrize("model", ("UNKNOWN", "RO", ""))
def test_nonreceiving_family_never_inherits_committed_nfb_ear_authorization(model):
    source = {
        "model": model, "nfb_config_submitted": True,
        "nfb_config": {"holes": [{"model_filename": "supplier-base.dxf"}]},
    }
    assert manufacturing_api.selected_export_manufacturing_policy(
        source, _flags(),
    ) == (False, ())
    route = manufacturing_api.plan_selected_resolved_export_route(
        source, _flags(),
    )
    assert not route.vault_composed
    assert dict(route.legacy_guard_flags)["box_body"] is True


@pytest.mark.parametrize("model", ("RECEIVING", "receiving"))
def test_registered_receiving_alias_normal_export_reopens_real_ear_side_dxf(
    tmp_path, model,
):
    from gui_modules.project.export_actions import _export_selected_resolved_parts
    from tests.test_issue1503_auto_side_marks_in_normal_export import (
        _flags as real_flags, _host, _mark_lines,
    )
    from tests.test_issue1503_ear_side_check_only_dxf import _actual
    from tests.test_receiving_base_physical_3d_z_assembly import _assembled

    snapshot, geometry = _actual(_assembled)
    source = {**snapshot, "model": model}
    host, calls = _host(source, geometry)
    folder = tmp_path / "selected"
    filenames, errors = _export_selected_resolved_parts(
        host, str(folder), real_flags(),
    )
    assert not errors and calls == ["resolve"]
    for side in ("left_side", "right_side"):
        filename = f"box_body_box_body_{side}.dxf"
        assert filename in filenames
        # Read the actual serialized DXF MARKING layer; never infer approval
        # from in-memory preview geometry alone.
        assert _mark_lines(folder / filename)
    assert len(tuple(folder.glob("*.dxf"))) == len(filenames)
    assert source["model"] == model
