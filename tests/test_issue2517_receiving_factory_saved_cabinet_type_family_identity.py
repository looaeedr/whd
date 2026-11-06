"""#2517: Receiving saved operator must use the same Family Registry as GUI.

A previously saved project may name its Family in cabinet_type rather than
model. That is a real committed source, not permission to use fresh defaults.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest,
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)
import ae_engine.receiving_factory_requests as owner


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _saved_committed_receiving():
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved.update({"fw": 31.0, "yl1": 19.0, "yr1": 21.0, "ytop1": 18.0})
    saved["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        role: api.build_endcap_xy_fold_profiles(saved, part_key=role)
        for role in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        role: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"],
            thickness=saved["t"],
            state=saved["box_body_structure_state"],
        )
        for role in ("head", "tail")
    }
    return saved


@pytest.mark.parametrize("key,alias", (
    ("model", "受電箱"),
    ("model", "receiving"),
    ("model", "ReCeIvInG"),
    ("cabinet_type", "受電箱"),
    ("cabinet_type", "RECEIVING"),
    ("cabinet_type", "receiving"),
    ("cabinet_type", "ReCeIvInG"),
    ("cabinet_type", "  receiving  "),
))
def test_saved_snapshot_registry_alias_uses_committed_manufacturing_not_fresh_defaults(
    key, alias,
):
    saved = _saved_committed_receiving()
    saved.pop("model", None)
    saved[key] = alias
    original = deepcopy(saved)
    assert family_policy.canonical_family_name(saved) == "受電箱"

    parts = api.build_receiving_factory_confirmed_parts(
        deepcopy(SOURCE), confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
    )
    assert tuple(name for name, _ in parts) == ("box_body", "head", "tail")
    specs = dict(parts)
    assert all(spec.model_name == "受電箱" for spec in specs.values())
    assert specs["box_body"].frame_width == 31.0
    assert specs["head"].fold_left == 19.0
    assert specs["tail"].fold_right == 21.0
    assert specs["head"].fold_top == 18.0
    assert (specs["box_body"].width, specs["box_body"].height,
            specs["box_body"].depth, specs["box_body"].thickness) == (
        SOURCE["w"], SOURCE["h"], SOURCE["d"], SOURCE["t"],
    )
    assert saved == original


def test_empty_model_with_valid_saved_cabinet_type_follows_same_registry():
    saved = _saved_committed_receiving()
    saved["model"] = ""
    saved["cabinet_type"] = "receiving"
    assert family_policy.canonical_family_name(saved) == "受電箱"
    assert dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
    ))["box_body"].frame_width == 31.0


@pytest.mark.parametrize("override", [
    {"cabinet_type": "金庫型"},
    {"cabinet_type": "unknown-family"},
    {"model": "金庫型", "cabinet_type": "receiving"},
    {"model": "unknown-family", "cabinet_type": "receiving"},
])
def test_saved_registry_fails_closed_for_wrong_or_conflicting_family(override):
    saved = _saved_committed_receiving()
    saved.pop("model", None)
    saved.update(override)
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
        )
    assert saved == before


def test_saved_cabinet_type_does_not_bypass_physical_dimensions_or_state():
    saved = _saved_committed_receiving()
    saved.pop("model")
    saved["cabinet_type"] = "receiving"
    prior = deepcopy(saved)
    modified = deepcopy(saved)
    modified["w"] = 801
    with pytest.raises(ValueError, match="RECEIVING_SOURCE_SAVED_DIMENSIONS_CONFLICT"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=modified,
        )
    modified = deepcopy(saved)
    del modified["box_body_fold_profile"]
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=modified,
        )
    assert saved == prior


def test_saved_cabinet_type_verified_real_physical_dxf_roundtrip(tmp_path):
    saved = _saved_committed_receiving()
    saved.pop("model")
    saved["cabinet_type"] = "receiving"
    before = deepcopy(saved)
    bay = ManufacturingResolvedBayInput(
        family="receiving",
        source=ManufacturingSourceIdentity(
            "P1", "confirmed-revision", "set-1", "bay-1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
    )
    calls = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified-dxf",
        context=ManufacturingContext(
            resource_root=Path(__file__).resolve().parents[1],
        ),
        pre_commit_guard=lambda: calls.append("confirmed"),
    )
    assert calls == ["confirmed", "confirmed"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 5
    for filename in result.output_files.values():
        path = Path(filename)
        assert path.is_file()
        assert "CUTTING" in {entity.dxf.layer for entity in ezdxf.readfile(path).modelspace()}
    assert saved == before
    blocked = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", "receiving", bay.source),
    )
    assert blocked.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"


def test_saved_family_gate_reads_entire_registry_snapshot_not_model_only():
    code = inspect.getsource(owner._saved_operator_state)
    assert "family_policy.canonical_family_name(saved)" in code
    assert 'canonical_family_name(saved.get("model"))' not in code
