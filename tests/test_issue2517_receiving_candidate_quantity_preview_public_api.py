# -*- coding: utf-8 -*-
"""#2517: GUI Head/Tail allocation readiness uses authoritative Engine."""
from copy import deepcopy
import inspect
import pytest
import ae_engine
from ae_engine import manufacturing_api
from ae_engine.receiving_hole_candidates import create_candidate, role_key, version_label
from ae_engine.receiving_quantity_allocation import validate_quantity_allocation
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.receiving_quantity_allocation_ui import ReceivingQuantityAllocationUI


def _inputs():
    hole = CircleFeature(diameter=6.4, anchor=FeatureAnchor.TOP_LEFT, offset=Vec2(20, 30))
    library, h1 = create_candidate(None, "head", [hole])
    library, h2 = create_candidate(library, "head", [hole])
    library, _ = create_candidate(library, "tail", [hole])
    entries = {role: deepcopy(library[role]["versions"]) for role in ("head", "tail")}
    quantities = {h1: 2, h2: 1}
    assigned = {(0, 0): h1, (0, 1): h2, (1, 0): h1}
    return library, entries, quantities, assigned


def test_public_preview_identical_to_canonical_engine_allocation_and_pure():
    library, entries, quantities, assigned = _inputs()
    before = deepcopy((entries, quantities, assigned))
    expected = validate_quantity_allocation(
        {"sets": [{"bays": [None, None]}, {"bays": [None]}]},
        library, "head", quantities, assigned, expected_counts=(2, 1),
    )
    result = manufacturing_api.validate_receiving_candidate_quantity_preview(
        entries, (2, 1), "head", quantities, assigned, expected_counts=(2, 1),
    )
    assert result == expected and len(result) == 3
    assert before == (entries, quantities, assigned)
    assert ae_engine.validate_receiving_candidate_quantity_preview is (
        manufacturing_api.validate_receiving_candidate_quantity_preview
    )
    assert ae_engine.validate_receiving_candidate_role is role_key
    assert ae_engine.receiving_candidate_version_label is version_label


@pytest.mark.parametrize("counts", ((), (0,), (True,), (2.0,), ("2",), (1, -1)))
def test_bad_physical_bay_counts_never_make_a_preview(counts):
    _, entries, quantities, assigned = _inputs()
    original = deepcopy(entries)
    with pytest.raises(ValueError, match="套／連"):
        manufacturing_api.validate_receiving_candidate_quantity_preview(
            entries, counts, "head", quantities, assigned, expected_counts=counts,
        )
    assert entries == original


def test_duplicate_wrong_role_and_invalid_features_all_reject_without_mutation():
    _, entries, quantities, assigned = _inputs()
    wrong = deepcopy(entries)
    wrong["head"][0]["id"] = "tail-v88"
    duplicate = deepcopy(entries)
    duplicate["head"][1]["id"] = "head-v1"
    invalid = deepcopy(entries)
    invalid["head"][0]["features"] = [{"fake": "hole"}]
    for source in (wrong, duplicate, invalid):
        before = deepcopy(source)
        with pytest.raises(ValueError):
            manufacturing_api.validate_receiving_candidate_quantity_preview(
                source, (2, 1), "head", quantities, assigned, expected_counts=(2, 1),
            )
        assert source == before


def test_topology_drift_and_missing_bay_rejected_by_existing_canonical_gate():
    _, entries, quantities, assigned = _inputs()
    for q, allocation, current_counts in (
        ({"head-v1": 1, "head-v2": 1}, assigned, (2, 1)),
        (quantities, {(0, 0): "head-v1"}, (2, 1)),
        (quantities, assigned, (3,)),
    ):
        with pytest.raises(ValueError):
            manufacturing_api.validate_receiving_candidate_quantity_preview(
                entries, (2, 1), "head", q, allocation,
                expected_counts=current_counts,
            )


def test_gui_real_readiness_no_tk_respects_engine_and_original_live_validator():
    _, entries, quantities, assigned = _inputs()
    ui = object.__new__(ReceivingQuantityAllocationUI)
    ui.role = "head"
    ui.draft = manufacturing_api.AllocationDraft((2, 1))
    ui.draft.quantities["head"] = quantities
    ui.draft.assigned["head"] = assigned
    ui.get_counts = lambda: (2, 1)
    ui.get_ports = lambda: {"versions": lambda role: entries[role]}
    assert ui._ready_to_apply() is True
    ui.get_counts = lambda: (3,)
    assert ui._ready_to_apply() is False
    ui.get_counts = lambda: (2, 1)

    def live_reject(*args):
        raise ValueError("LIVE_OWNER_REJECTED")

    ui.get_ports = lambda: {"validate_quantity": live_reject}
    assert ui._ready_to_apply() is False


def test_gui_must_not_derive_candidate_counter_or_fake_physical_topology():
    source = inspect.getsource(ReceivingQuantityAllocationUI._ready_to_apply)
    assert "manufacturing_api.validate_receiving_candidate_quantity_preview(" in source
    assert "normalize_candidates(" not in source
    assert '"next_number"' not in source
    assert '"bays": [None]' not in source
    gui = inspect.getsource(ReceivingQuantityAllocationUI)
    assert "from ae_engine.receiving_hole_candidates" not in gui
