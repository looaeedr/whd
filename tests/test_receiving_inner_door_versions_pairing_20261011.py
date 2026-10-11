"""Independent inner-door candidates reuse allocation mechanics, never endcap data."""
from copy import deepcopy

import pytest

from ae_engine.receiving_hole_candidates import (
    create_candidate, candidate_features, version_label,
)
from ae_engine.receiving_inner_door_candidates import (
    KEY, ROLE, create_inner_candidate, update_inner_candidate,
    normalize_inner_candidates, inner_config, inner_versions,
    delete_inner_candidate, duplicate_inner_candidate,
)
from ae_engine.receiving_inner_door_pairing import (
    paired_bay_parts, paired_set_parts, validate_inner_door_allocation,
)
from ae_engine.receiving_quantity_allocation import AllocationDraft
from ae_engine.receiving_layout import new_receiving_layout, project_receiving_bay_legacy_aliases
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from phase6_quantity_model import normalize_quantity_snapshot


def fixture():
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    adapter.set_bay_count(2)
    adapter.set_set_count(2)
    adapter.select_set(2)
    adapter.set_bay_count(2)
    adapter.select_set(1)
    return adapter


def test_inner_versions_are_own_deep_copied_candidate_library():
    library, first = create_inner_candidate(
        None, {"layers": 1, "models": ["BH_25X95.dxf", ""]}
    )
    library, second = duplicate_inner_candidate(library, first)
    assert (first, second) == ("inner-door-v1", "inner-door-v2")
    assert [version_label(v) for v in (first, second)] == ["版本一", "版本二"]
    changed = update_inner_candidate(
        library, second,
        {"layers": 2, "models": ["BH_25X95_02.dxf", "BH_25X95_03.dxf"]}
    )
    assert inner_config(library, second)["layers"] == 1
    assert inner_config(changed, first)["models"] == ["BH_25X95.dxf", ""]
    changed = delete_inner_candidate(changed, first)
    changed, third = create_inner_candidate(
        changed, {"layers": 1, "models": ["", ""]}
    )
    assert third == "inner-door-v3"
    assert [v["id"] for v in inner_versions(changed)] == [second, third]
    with pytest.raises(ValueError):
        create_inner_candidate(changed, {"layers": 1, "models": ["x.dxf", "y.dxf"]})
    with pytest.raises(ValueError):
        update_inner_candidate(changed, "head-v1", {"layers": 1, "models": ["", ""]})
    clone = deepcopy(changed)
    clone["next_number"] = 2
    with pytest.raises(ValueError):
        normalize_inner_candidates(clone)


def test_true_set_bay_pairing_across_two_sets_and_independent_endcaps():
    adapter = fixture()
    endcaps, h = create_candidate(None, "head", [{"tag": "head"}])
    adapter.apply_candidate_to_bays("head", 0, (0, 1), candidate_features(endcaps, "head", h))
    adapter.apply_candidate_to_bays("tail", 0, (0, 1), [{"tag": "tail"}])
    inner, door1 = create_inner_candidate(None, {"layers": 1, "models": ["A.dxf", ""]})
    inner, door2 = create_inner_candidate(inner, {"layers": 2, "models": ["B.dxf", "C.dxf"]})
    assert adapter.apply_inner_door_candidate_to_bays(
        inner_config(inner, door2), 0, (0, 1)
    ) == (0, 1)
    paired = paired_set_parts(adapter.layout, set_index=0)
    assert len(paired) == 2
    assert all(p["inner_door"]["models"] == ["B.dxf", "C.dxf"] for p in paired)
    assert all(p["head_features"] == [{"tag": "head"}] for p in paired)
    assert all(p["tail_features"] == [{"tag": "tail"}] for p in paired)
    # Same two-Bay length in another Set is NOT the same physical box.
    other = paired_bay_parts(adapter.layout, set_index=1, bay_index=0)
    assert other["set_id"] != paired[0]["set_id"]
    assert other["bay_id"] != paired[0]["bay_id"]
    assert other["inner_door"]["models"] == ["", ""]
    projected = project_receiving_bay_legacy_aliases(
        {"cabinet_type": "受電箱", "receiving_layout": adapter.layout},
        set_index=0, bay_index=0,
        validate_common=False,
    )
    assert projected["receiving_inner_door_models"] == ["B.dxf", "C.dxf"]
    assert projected["receiving_inner_door_layers"] == 2
    # No edit crosses into the head/tail candidate library.
    assert candidate_features(endcaps, "head", h) == [{"tag": "head"}]


def test_inner_quantity_two_stage_atomic_and_compatible_with_endcaps():
    adapter = fixture()
    inner, v1 = create_inner_candidate(None, {"layers": 1, "models": ["A.dxf", ""]})
    inner, v2 = create_inner_candidate(inner, {"layers": 2, "models": ["B.dxf", "C.dxf"]})
    draft = AllocationDraft(
        (2, 2), roles=(ROLE,),
        validate_role=lambda key: key if key == ROLE else ValueError("unsupported"),
    )
    draft.add_version(ROLE, v1)
    draft.set_quantity(ROLE, v1, 2)
    draft.add_version(ROLE, v2)
    draft.set_quantity(ROLE, v2, 2)
    assert draft.ready_for_positioning(ROLE)
    draft.active_version[ROLE] = v1
    draft.assign(ROLE, 0, 0)
    draft.assign(ROLE, 1, 1)
    draft.active_version[ROLE] = v2
    draft.assign(ROLE, 0, 1)
    draft.assign(ROLE, 1, 0)
    before = adapter.layout
    bad = dict(draft.assigned[ROLE])
    bad[(1, 1)] = v2
    with pytest.raises(ValueError):
        adapter.apply_inner_door_quantity_configuration(
            inner, draft.quantities[ROLE], bad, expected_counts=(2, 2)
        )
    with pytest.raises(ValueError):
        adapter.apply_inner_door_quantity_configuration(
            inner, draft.quantities[ROLE], draft.assigned[ROLE],
            expected_counts=(4,),
        )
    assert adapter.layout == before
    plan = validate_inner_door_allocation(
        adapter.layout, inner, draft.quantities[ROLE], draft.assigned[ROLE],
        expected_counts=(2, 2),
    )
    assert len(plan) == 4
    assert adapter.apply_inner_door_quantity_configuration(
        inner, draft.quantities[ROLE], draft.assigned[ROLE],
        expected_counts=(2, 2),
    ) == 4
    for si, bi, config in plan:
        row = adapter.layout["sets"][si]
        assert setting_value(row, bi, "inner_door_layers") == config["layers"]
        assert setting_value(row, bi, "inner_door_models") == config["models"]


def test_inner_versions_persist_in_project_without_mutating_endcap_versions():
    inner, door = create_inner_candidate(
        None, {"layers": 2, "models": ["A.dxf", "B.dxf"]}
    )
    snapshot = {
        "cabinet_type": "受電箱", "active_mode": "set_bay",
        "receiving_layout": fixture().layout,
        KEY: inner,
    }
    saved = normalize_quantity_snapshot(snapshot, for_save=True)
    assert saved[KEY] == inner
    assert inner_config(saved[KEY], door)["models"] == ["A.dxf", "B.dxf"]
    broken = deepcopy(snapshot)
    broken[KEY]["next_number"] = 1
    with pytest.raises(ValueError):
        normalize_quantity_snapshot(broken, for_save=True)
