# -*- coding: utf-8 -*-
"""#2517 certified Family CornerType GUI source changes via Engine atomic draft."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
import gui
from ae_engine import manufacturing_api as api
from ae_engine import corner_type_ui as owner
from ae_engine.endcap_factory_fold import selection_from_raw, selection_to_raw
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, normalize_corner_selection,
)


ROOT = Path(__file__).resolve().parents[1]


def _seed():
    return (
        owner.new_manual_corner_state(("head", "tail")),
        owner.new_manual_corner_pair_same_state(("head", "tail")),
    )


def _legacy_expected(state, pairs, baseline_model, family, reset):
    """Characterize the exact old GUI behavior on a detached source."""
    state, pairs = deepcopy(state), deepcopy(pairs)
    model = str(baseline_model or "").strip()
    if not model or owner.is_unknown_model(model):
        return state, pairs
    fixed = owner.known_model_corner_state(state.keys(), cabinet_family=family)
    for part, rows in fixed.items():
        if part not in state:
            continue
        for corner, selected in rows.items():
            old = normalize_corner_selection(state[part][corner])
            if reset or old.type_id is not selected.type_id:
                state[part][corner] = selected
        if reset and part in pairs:
            pairs[part]["top"] = True
            pairs[part]["bottom"] = True
    return state, pairs


def test_new_public_ports_own_original_certified_registry_callable():
    assert api.operator_known_model_corner_state is owner.known_model_corner_state
    assert ae_engine.operator_known_model_corner_state is owner.known_model_corner_state
    assert api.propose_operator_known_model_corner_draft is owner.propose_operator_known_model_corner_draft
    assert ae_engine.propose_operator_known_model_corner_draft is owner.propose_operator_known_model_corner_draft
    assert "operator_known_model_corner_state" in ae_engine.__all__
    assert "propose_operator_known_model_corner_draft" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("reset", (False, True))
def test_public_engine_typed_draft_matches_original_gui_rule(family, reset):
    state, pairs = _seed()
    for part in ("head", "tail"):
        state[part]["top_left"] = CornerTypeSelection(CornerTypeId.CROSS)
        pairs[part]["top"] = False
    before = deepcopy((state, pairs))
    expected = _legacy_expected(state, pairs, family, family, reset)
    actual = api.propose_operator_known_model_corner_draft(
        state, pairs, baseline_model=family,
        cabinet_family=family, reset_all=reset,
    )
    assert actual == expected
    assert (state, pairs) == before
    assert actual[0] is not state and actual[1] is not pairs
    assert all(
        isinstance(value, CornerTypeSelection)
        for corners in actual[0].values() for value in corners.values()
    )
    # Existing Save→Reload contract remains typed CornerType -> raw JSON -> typed.
    for corners in actual[0].values():
        for selection in corners.values():
            wire = json.loads(json.dumps(selection_to_raw(selection)))
            assert selection_from_raw(wire) == normalize_corner_selection(selection)


def test_same_type_manual_parameter_override_is_preserved_unless_reset_requested():
    state, pairs = _seed()
    fixed = owner.known_model_corner_state(("head",), cabinet_family="金庫型")["head"]
    anchor = fixed["top_left"]
    current = CornerTypeSelection(anchor.type_id, amount_t=1.75,
        secondary_retain_t=0.5 if anchor.type_id is CornerTypeId.INSERT_OVERLAY else None,
        secondary_depth_t=2.0 if anchor.type_id is CornerTypeId.INSERT_OVERLAY else None)
    state["head"]["top_left"] = current
    not_reset, _ = api.propose_operator_known_model_corner_draft(
        state, pairs, baseline_model="金庫型", cabinet_family="金庫型",
    )
    reset, _ = api.propose_operator_known_model_corner_draft(
        state, pairs, baseline_model="金庫型", cabinet_family="金庫型", reset_all=True,
    )
    assert not_reset["head"]["top_left"] == current
    assert reset["head"]["top_left"] == anchor
    assert state["head"]["top_left"] == current


@pytest.mark.parametrize("baseline", ("", "自訂", "未知類型"))
def test_custom_and_empty_baselines_do_not_change_physical_corner_state(baseline):
    state, pairs = _seed()
    before = deepcopy((state, pairs))
    assert api.propose_operator_known_model_corner_draft(
        state, pairs, baseline_model=baseline, cabinet_family="金庫型",
        reset_all=True,
    ) == before
    assert (state, pairs) == before


def test_invalid_corner_source_fails_before_any_saved_source_mutation():
    state, pairs = _seed()
    state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.CROSS)
    state["head"].pop("bottom_right")
    original = deepcopy((state, pairs))
    with pytest.raises(KeyError):
        api.propose_operator_known_model_corner_draft(
            state, pairs, baseline_model="金庫型", cabinet_family="金庫型",
            reset_all=True,
        )
    assert (state, pairs) == original
    pairs["head"] = None
    original = deepcopy((state, pairs))
    with pytest.raises((ValueError, KeyError)):
        api.propose_operator_known_model_corner_draft(
            state, pairs, baseline_model="金庫型", cabinet_family="金庫型",
            reset_all=True,
        )
    assert (state, pairs) == original
    with pytest.raises(ValueError, match="KNOWN_CORNER_DRAFT_SOURCE_INVALID"):
        api.propose_operator_known_model_corner_draft(
            [], pairs, baseline_model="金庫型", cabinet_family="金庫型",
        )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("reset", (False, True))
def test_main_gui_commit_matches_original_engine_and_preserves_live_dict_aliases(family, reset):
    state, pairs = _seed()
    state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.CROSS)
    state["tail"]["bottom_right"] = CornerTypeSelection(CornerTypeId.CROSS)
    expected = _legacy_expected(state, pairs, family, family, reset)
    ids = {p: (id(state[p]), id(pairs[p])) for p in state}
    host = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: family),
        manual_corner_state=state, manual_corner_pair_same=pairs,
    )
    gui.Phase6ApplicationHost._enforce_known_model_corner_types(host, reset_all=reset)
    assert (state, pairs) == expected
    assert {p: (id(state[p]), id(pairs[p])) for p in state} == ids


def test_main_gui_no_longer_mutates_certified_registry_or_imports_private_owner():
    gui_source = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert "    known_model_corner_state," not in gui_source
    assert "manufacturing_api.operator_known_model_corner_state(" in gui_source
    assert "manufacturing_api.propose_operator_known_model_corner_draft(" in gui_source
    fn_start = gui_source.index("    def _enforce_known_model_corner_types(")
    fn_end = gui_source.index("    def _phase6_external_sync_envelope", fn_start)
    method = gui_source[fn_start:fn_end]
    assert "fixed_selection" not in method
    assert "normalize_corner_selection(" not in method
