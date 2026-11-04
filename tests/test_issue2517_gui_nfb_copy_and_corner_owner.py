"""#2517: real GUI NFB copy direction and fixed EndCap labels use public Engine."""
from __future__ import annotations

from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.assembly_joint import AssemblyJointRelation, set_part_edge_relation
from gui_modules.application import fold_designer_composition_receiving as receiving
from gui_modules.parts.panels.assembly_corner import fixed_corner_summary


def _two_bays(*, first_committed=True, second_committed=False):
    return {
        "sets": [{
            "stable_id": "s-actual",
            "bays": [
                {"stable_id": "bay-left", "nfb_config_submitted": first_committed},
                {"stable_id": "bay-right", "nfb_config_submitted": second_committed},
            ],
        }],
    }


@pytest.mark.parametrize("selection", ((0, 1), (1, 0)))
def test_engine_nfb_copy_selects_real_committed_source_independent_target(selection):
    layout = _two_bays()
    before = deepcopy(layout)
    indices, owners = manufacturing_api.select_operator_nfb_copy_bays(
        layout, 0, selection,
    )
    assert indices == selection
    assert {i: owners[i]["stable_id"] for i in indices} == {
        0: "bay-left", 1: "bay-right",
    }
    assert manufacturing_api.plan_operator_nfb_copy_direction(
        layout, 0, selection, verified_target_indices=(1,),
    ) == (0, 1)
    assert layout == before


@pytest.mark.parametrize("bad_indices", (
    None, 1, (), (0,), (0, 0), (0, True), (0, 1.0),
    ([], 1), (0, {}), (0, 2), (0, -1),
))
def test_engine_nfb_copy_does_not_use_invalid_gui_highlights(bad_indices):
    with pytest.raises(ValueError):
        manufacturing_api.select_operator_nfb_copy_bays(
            _two_bays(), 0, bad_indices,
        )


@pytest.mark.parametrize("bad_set", (True, 0.0, "0", None, [], -1, 1))
def test_engine_nfb_copy_requires_real_set_index(bad_set):
    with pytest.raises(ValueError):
        manufacturing_api.plan_operator_nfb_copy_direction(
            _two_bays(), bad_set, (0, 1), verified_target_indices=(1,),
        )


@pytest.mark.parametrize("verified", ((), (0,), (True,), (1, 1), ([],), (2,)))
def test_engine_nfb_copy_rejects_missing_forged_or_duplicate_target_proofs(verified):
    layout = _two_bays()
    before = deepcopy(layout)
    with pytest.raises(ValueError):
        manufacturing_api.plan_operator_nfb_copy_direction(
            layout, 0, (0, 1), verified_target_indices=verified,
        )
    assert layout == before


def test_engine_nfb_copy_blocks_unsubmitted_or_ambiguous_direction():
    for layout, verified in (
        (_two_bays(first_committed=False), (1,)),
        (_two_bays(first_committed=True, second_committed=True), (0, 1)),
    ):
        frozen = deepcopy(layout)
        with pytest.raises(ValueError, match="不明確的複製方向"):
            manufacturing_api.plan_operator_nfb_copy_direction(
                layout, 0, (0, 1), verified_target_indices=verified,
            )
        assert layout == frozen


def test_gui_nfb_copy_wrapper_is_only_a_public_engine_forwarder(monkeypatch):
    layout = _two_bays()
    calls = []
    original = manufacturing_api.select_operator_nfb_copy_bays

    def forwarded(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(manufacturing_api, "select_operator_nfb_copy_bays", forwarded)
    indices, owners = receiving._checked_nfb_copy_selection(layout, 0, (1, 0))
    assert calls == [(layout, 0, (1, 0))]
    assert indices == (1, 0) and owners[0]["stable_id"] == "bay-left"
    src = getsource(receiving)
    assert "manufacturing_api.plan_operator_nfb_copy_direction(" in src
    assert 'if selected[source_bi].get("nfb_config_submitted")' not in src


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
@pytest.mark.parametrize("role", ("head", "tail"))
def test_engine_corner_summary_accepts_all_registered_receiving_aliases(family, role):
    host = SimpleNamespace(
        assembly_joint_state={},
        _FIXED_CORNER_SUMMARIES={role: "OLD_VAULT_CORNER_FALLBACK"},
    )
    expected = manufacturing_api.project_operator_fixed_corner_summary(
        "受電箱", role, {},
    )
    assert expected is not None and "上方：嵌入貼外型" in expected
    assert manufacturing_api.project_operator_fixed_corner_summary(
        family, role, {},
    ) == expected
    assert fixed_corner_summary(host, role, family) == expected


def test_engine_corner_display_follows_real_bottom_joint_without_mutation():
    state = {"assembly_type": "WRAP_OVERLAY"}
    updated = set_part_edge_relation(
        state, "head", "BOTTOM", AssemblyJointRelation.INSERT,
    )
    before = deepcopy(updated)
    caption = manufacturing_api.project_operator_fixed_corner_summary(
        "receiving", "head", updated,
    )
    assert "BOTTOM＝嵌入" in caption
    assert updated == before


def test_other_families_keep_existing_legacy_corner_labels():
    host = SimpleNamespace(
        assembly_joint_state={},
        _FIXED_CORNER_SUMMARIES={"head": "金庫型既有固定截角"},
    )
    for family in ("金庫型", "RO", "未知"):
        assert manufacturing_api.project_operator_fixed_corner_summary(
            family, "head", {},
        ) is None
        assert fixed_corner_summary(host, "head", family) == "金庫型既有固定截角"
    assert manufacturing_api.project_operator_fixed_corner_summary(
        "受電箱", "door", {},
    ) is None


def test_fixed_corner_gui_contains_no_embedded_family_or_joint_rules():
    src = getsource(fixed_corner_summary)
    assert "manufacturing_api.project_operator_fixed_corner_summary(" in src
    assert "edge_relation_for_part" not in src
    assert "AssemblyJointRelation" not in src
    assert 'current_cabinet_type_name in' not in src
