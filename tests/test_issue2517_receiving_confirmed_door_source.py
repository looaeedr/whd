"""#2517: confirmed Receiving upper/lower Doors use the existing Engine DXF path."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.contracts import DoorPartSpec, ManufacturingContext

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
UPPER_LOWER = ((800.0, (1100.0, 500.0)),)


def _input(*, columns=UPPER_LOWER, confirmation="fresh_family_confirmed", saved=None):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "source-rev", "set-1", "bay-1"),
        source_dimensions_mm=SOURCE,
        operator_confirmation=confirmation,
        operator_snapshot=saved,
        door_layout_columns=columns,
    )


def _saved():
    state = family_policy.apply_fresh_family_defaults({}, "受電箱")
    state.update(SOURCE)
    state["box_body_structure_state"] = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    state["box_body_fold_profile"] = manufacturing_api.build_box_body_fold_profile(state)
    state["endcap_fold_profiles"] = {
        key: manufacturing_api.build_endcap_xy_fold_profiles(state, part_key=key)
        for key in ("head", "tail")
    }
    state["endcap_corner_policies"] = {
        key: family_policy.endcap_corner_policy(
            "受電箱", frame_width=state["fw"], thickness=state["t"],
            state=state["box_body_structure_state"],
        ) for key in ("head", "tail")
    }
    return state


def test_source_to_two_door_specs_uses_engine_physical_cells():
    source = deepcopy(SOURCE)
    parts = manufacturing_api.build_receiving_factory_confirmed_parts(
        source, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=UPPER_LOWER,
    )
    assert source == SOURCE
    assert [key for key, _ in parts] == [
        "box_body", "head", "tail", "door_c1_r1", "door_c1_r2",
    ]
    upper, lower = (spec for _, spec in parts[3:])
    assert isinstance(upper, DoorPartSpec)
    assert (upper.width, upper.height, lower.width, lower.height) == (
        800.0, 1100.0, 800.0, 500.0,
    )
    assert upper.frame_edges.bottom is False
    assert lower.frame_edges.bottom is True
    assert upper.feature_space == lower.feature_space == "finished_face"
    assert (upper.gap_w, upper.fold_top, lower.fold_bottom) == (3.5, 19.0, 19.0)


def test_source_confirmed_upper_lower_goes_through_verified_dxf_reopen(tmp_path):
    output = tmp_path / "out"
    proof = []
    result = export_verified_resolved_integration_bays(
        (_input(),), output, context=ManufacturingContext(resource_root=ROOT),
        pre_commit_guard=lambda: proof.append("source-current"),
    )
    assert proof == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert not result.external_cli_enabled
    assert len(result.output_files) == 7  # 3 body pieces + Head/Tail + upper/lower
    assert any(Path(path).name.endswith("door_c1_r1.dxf") for path in result.output_files.values())
    assert any(Path(path).name.endswith("door_c1_r2.dxf") for path in result.output_files.values())
    for path in result.output_files.values():
        layers = {e.dxf.layer for e in ezdxf.readfile(path).modelspace()}
        assert "CUTTING" in layers


def test_saved_door_topology_is_not_regenerated_or_replaced():
    saved = _saved()
    before = deepcopy(saved)
    parts = manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_door_layout_columns=UPPER_LOWER,
    )
    assert [key for key, _ in parts][-2:] == ["door_c1_r1", "door_c1_r2"]
    assert saved == before


@pytest.mark.parametrize("columns", [
    ((790.0, (1100.0, 500.0)),),
    ((800.0, (1100.0, 499.0)),),
    ((800.0, (True, 1599.0)),),
    ((800.0, (float("nan"), 500.0)),),
    ((800.0, (-1.0, 1601.0)),),
])
def test_invalid_confirmed_door_layout_rejected_before_dxf(columns, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        export_verified_resolved_integration_bays(
            (_input(columns=columns),), out, pre_commit_guard=lambda: None,
        )
    assert not out.exists()


def test_saved_door_changes_and_unverified_holes_fail_closed(tmp_path):
    saved = _saved()
    mismatched = deepcopy(saved)
    mismatched["door_layout_columns"] = ((800.0, (900.0, 700.0)),)
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        manufacturing_api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=mismatched,
            confirmed_door_layout_columns=UPPER_LOWER,
        )
    with_holes = deepcopy(saved)
    with_holes["part_features"] = {"door_c1_r1": [object()]}
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        manufacturing_api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=with_holes,
            confirmed_door_layout_columns=UPPER_LOWER,
        )
    assert not (tmp_path / "out").exists()


def test_legacy_three_part_source_and_source_only_guard_unchanged():
    result = manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
    )
    assert [key for key, _ in result] == ["box_body", "head", "tail"]
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmed_door_layout_columns=UPPER_LOWER,
        )
