"""#2517: saved Door-cell indicator holes cannot vanish in confirmed factory DXF."""
from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_part_adapters import door_layout_part_key

SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((420.0, (760.0, 840.0)), (380.0, (760.0, 840.0)))


def _saved():
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved["model"] = "receiving"
    saved["multi_door_enabled"] = True
    saved["door_layout_columns"] = deepcopy(COLUMNS)
    saved["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        role: api.build_endcap_xy_fold_profiles(saved, part_key=role)
        for role in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        role: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"], thickness=saved["t"],
            state=saved["box_body_structure_state"],
        )
        for role in ("head", "tail")
    }
    return saved


def _build(saved):
    return api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_door_layout_columns=COLUMNS,
    )


def _indicator(mode="indicator", **updates):
    state = dict(mode=mode, layers=1, groups=[2, 2, 2, 2, 2, 2],
                 offset_x=0.0, offset_y=0.0, is_box_dist=False)
    state.update(updates)
    return state


@pytest.mark.parametrize("cell_key", ("0:0", (0, 0), "door_c1_r1"))
@pytest.mark.parametrize("mode", ("indicator", "indicator_box"))
def test_saved_illuminated_door_rejected_before_physical_part_spec(cell_key, mode):
    saved = _saved()
    saved["door_layout_indicator_states"] = {cell_key: _indicator(mode)}
    original = deepcopy(saved)
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        _build(saved)
    assert saved == original


def test_legacy_enabled_indicator_flag_also_blocks_holeless_factory_export():
    saved = _saved()
    source = _indicator()
    source.pop("mode")
    source["enabled"] = True
    saved["door_layout_indicator_states"] = {"0:0": source}
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        _build(saved)


@pytest.mark.parametrize("bad", (
    False, [], None, "invalid", {"0:0": _indicator(groups=[True])},
    {"0:0": _indicator(offset_x=float("nan"))},
    {"0:0": _indicator(mode="unknown")},
    {"0:0": _indicator(mode="indicator_box", layers=7)},
    {"0:0": _indicator(mode="indicator", groups=None)},
))
def test_invalid_saved_indicator_source_cannot_be_silently_omitted(bad):
    saved = _saved()
    saved["door_layout_indicator_states"] = bad
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        _build(saved)


@pytest.mark.parametrize("invalid", (False, None, [], "", {"door_c1_r1": None},
                                    {"door_c1_r1": False},
                                    {"door_c1_r1": ["saved-cut"]}))
def test_invalid_or_nonempty_saved_door_features_are_not_dropped(invalid):
    saved = _saved()
    saved["part_features"] = invalid
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        _build(saved)


def test_saved_duplicate_indicator_identity_is_ambiguous_and_fails_closed():
    saved = _saved()
    saved["door_layout_indicator_states"] = {
        "0:0": _indicator(mode="none"),
        "door_c1_r1": _indicator(mode="none"),
    }
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        _build(saved)


def test_saved_disabled_controls_and_empty_authored_features_keep_real_verified_dxf(tmp_path):
    saved = _saved()
    saved["part_features"] = {"door_c1_r1": [], "door_c2_r2": ()}
    saved["door_layout_indicator_states"] = {
        "0:0": _indicator(mode="none", layers=False, groups=[False]),
        "1:1": _indicator(mode="none", offset_x="invalid"),
    }
    prior = deepcopy(saved)
    parts = _build(saved)
    assert [key for key, _ in parts] == [
        "box_body", "head", "tail",
        "door_c1_r1", "door_c1_r2", "door_c2_r1", "door_c2_r2",
    ]
    assert all(spec.door_indicator is None for key, spec in parts if key.startswith("door_"))
    assert saved == prior

    bay = ManufacturingResolvedBayInput(
        family="receiving",
        source=ManufacturingSourceIdentity(
            "P1", "confirmed-operator-save", "Set-A", "Bay-1",
        ),
        confirmed_parts=parts,
        door_layout_columns=COLUMNS,
    )
    exported = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: None,
    )
    assert exported.physical_dxf_roundtrip_verified
    assert len(exported.output_files) == 9
    for filename in exported.output_files.values():
        assert Path(filename).is_file()
        layers = {item.dxf.layer for item in ezdxf.readfile(filename).modelspace()}
        assert "CUTTING" in layers


def test_saved_confirmed_door_hole_validation_uses_existing_engine_source():
    import ae_engine.receiving_factory_requests as owner

    source = inspect.getsource(owner._confirmed_door_parts)
    assert "project_operator_door_cell_indicator_manufacturing_source(" in source
    assert 'values.get("part_features") or {}' not in source
    assert "door_layout_indicator_states" in source
