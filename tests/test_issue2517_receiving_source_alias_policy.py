"""#2517 Receiving aliases must not split BasePlate, fixing EAR and PAD source."""
from copy import deepcopy

import pytest

from ae_engine.cabinet_types.policy import canonical_family_name
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
from tests.test_issue1502_source_derived_center_base import _source_snapshot
from tests.test_receiving_nfb_pad_delivery import installed_pair


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "))
def test_registered_aliases_use_same_committed_physical_base_source(model):
    snapshot = _source_snapshot(shallow="2P400")
    original = receiving_base_plate_values(snapshot)
    assert original is not None and original["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    snapshot["model"] = model
    assert canonical_family_name(snapshot) == "受電箱"
    assert receiving_base_plate_values(snapshot) == original


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "))
def test_aliases_project_identical_source_ear_without_inventing_mfg(model):
    snapshot = {
        "model": model, "w": 800, "t": 2,
        "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"},
    }
    parts = receiving_base_fixing_plate_previews(
        snapshot, available_parts=("base_plate",),
    )
    assert len(parts) == 2
    assert tuple(p.part_id for p in parts) == (
        "base_plate:fixing_plate:left", "base_plate:fixing_plate:right"
    )
    assert all(p.applicable_slot_pair_indexes == (0, 3)
               and p.manufacturing_ready is False for p in parts)


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_pad_projection_cannot_disappear_only_on_registered_alias(model):
    source, _parts = installed_pair()
    original = committed_nfb_pad_draft_parts(source)
    assert original and all(part.part_id.startswith("nfb_pad:") for part in original)
    aliased = deepcopy(source)
    aliased["model"] = model
    candidate = committed_nfb_pad_draft_parts(aliased)
    assert tuple(part.part_id for part in candidate) == tuple(part.part_id for part in original)


@pytest.mark.parametrize("model", ("金庫型", "UNKNOWN", "RO"))
def test_non_receiving_family_must_not_project_source_parts(model):
    snapshot = _source_snapshot(shallow="2P400")
    snapshot["model"] = model
    assert receiving_base_plate_values(snapshot) is None
    assert not receiving_base_fixing_plate_previews(
        snapshot, available_parts=("base_plate",),
    )
    assert not committed_nfb_pad_draft_parts(snapshot)
