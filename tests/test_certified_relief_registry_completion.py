# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
)


def _sel_signature(value):
    return (
        value.type_id,
        value.cross_mode,
        value.direction,
        value.amount_t,
        value.secondary_retain_t,
        value.secondary_depth_t,
    )


def test_vault_fixed_corner_rules_are_all_certified_and_queryable():
    from ae_engine.certified_relief_registry import (
        CertifiedReliefStatus,
        lookup_certified_corner_state,
        registered_certified_corner_policy_rules,
    )

    rules = registered_certified_corner_policy_rules()
    vault_ids = {rule.rule_id for rule in rules if rule.cabinet_family == "金庫型"}
    assert {
        "VAULT_ENDCAP_FIXED_POLICY_V1",
        "VAULT_DOOR_CROSS_RETAIN_WIDTH_V1",
        "VAULT_INDICATOR_BOX_CROSS_RETAIN_WIDTH_V1",
        "VAULT_INDICATOR_DOOR_CROSS_RETAIN_WIDTH_V1",
        "VAULT_BASE_PLATE_CROSS_STANDARD_V1",
    } <= vault_ids
    assert all(rule.status is CertifiedReliefStatus.CERTIFIED for rule in rules)

    state = lookup_certified_corner_state(
        cabinet_family="金庫型",
        part_keys=("head", "tail", "door", "indicator_box", "indicator_door", "base_plate"),
    )
    top = state["head"]["top_left"]
    bottom = state["head"]["bottom_left"]
    assert _sel_signature(top) == _sel_signature(CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY,
        amount_t=1.0, secondary_retain_t=0.5, secondary_depth_t=2.0,
    ))
    assert _sel_signature(bottom) == _sel_signature(CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    ))
    for part in ("door", "indicator_box", "indicator_door"):
        assert _sel_signature(state[part]["top_left"]) == _sel_signature(CornerTypeSelection(
            CornerTypeId.CROSS,
            cross_mode=CrossCornerMode.RETAIN,
            direction=CornerDirection.WIDTH,
            amount_t=1.0,
        ))
    assert _sel_signature(state["base_plate"]["top_left"]) == _sel_signature(
        CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    )


def test_receiving_fixed_endcap_rule_is_family_specific():
    from ae_engine.certified_relief_registry import lookup_certified_corner_state

    state = lookup_certified_corner_state(cabinet_family="受電箱", part_keys=("head", "tail"))
    for part in ("head", "tail"):
        assert state[part]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY
        assert state[part]["top_left"].amount_t == pytest.approx(1.0)
        bottom = state[part]["bottom_left"]
        assert bottom.type_id is CornerTypeId.CROSS
        assert bottom.cross_mode is CrossCornerMode.STANDARD


def test_known_model_corner_state_routes_through_family_registry():
    from ae_engine.corner_type_ui import known_model_corner_state

    vault = known_model_corner_state(("head",), cabinet_family="金庫型")
    receiving = known_model_corner_state(("head",), cabinet_family="受電箱")
    assert vault["head"]["bottom_left"].type_id is CornerTypeId.CROSS
    assert receiving["head"]["bottom_left"].type_id is CornerTypeId.CROSS
    assert receiving["head"]["bottom_left"].cross_mode is CrossCornerMode.STANDARD


def test_all_standard_assembly_intents_have_active_certified_formula_rules():
    from ae_engine.certified_relief_registry import registered_certified_relief_rules
    from ae_engine.corner_type_ui import BOX_ASSEMBLY_TYPE_IDS

    rules = [r for r in registered_certified_relief_rules() if r.status.value in {"CERTIFIED", "CERTIFIED_FROM_3D"}]
    intents = {r.assembly_intent for r in rules}
    assert set(BOX_ASSEMBLY_TYPE_IDS) <= intents
    assert any(r.assembly_intent is CornerTypeId.INSERT and "STANDARD" in r.rule_id for r in rules)
    assert any(r.assembly_intent is CornerTypeId.OVERLAY for r in rules)
    assert any(r.assembly_intent is CornerTypeId.INSERT_OVERLAY for r in rules)


def test_certified_rule_revision_lookup_is_explicit():
    from ae_engine.certified_relief_registry import certified_rule_revision_exists

    assert certified_rule_revision_exists("ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", 1) is True
    assert certified_rule_revision_exists("ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", 999) is False
    assert certified_rule_revision_exists("NO_SUCH_RULE", 1) is False


def test_registry_rejects_ambiguous_corner_policy_rules(monkeypatch):
    import ae_engine.certified_relief_registry as registry

    rule = registry.registered_certified_corner_policy_rules()[0]
    monkeypatch.setattr(registry, "_CORNER_POLICY_RULES", (rule, rule))
    with pytest.raises(registry.CertifiedReliefRegistryAmbiguityError):
        registry.lookup_certified_corner_state(cabinet_family=rule.cabinet_family, part_keys=(rule.part_roles[0],))


def test_promotion_candidate_is_manifest_only_and_requires_verified_provisional():
    from types import SimpleNamespace
    from ae_engine.certified_relief_registry import build_relief_promotion_candidate

    provisional = SimpleNamespace(
        verified=True,
        trust_level="PROVISIONAL_3D",
        rule_id=None,
        rule_revision=None,
        corner_reliefs=(),
    )
    candidate = build_relief_promotion_candidate(
        provisional,
        cabinet_family="自訂",
        part_role="head",
        joint_face="TOP",
        assembly_intent=CornerTypeId.OVERLAY,
        source_signature={"w": 400, "t": 2},
    )
    assert candidate["status"] == "PROMOTION_CANDIDATE"
    assert candidate["mutates_registry"] is False
    assert candidate["assembly_intent"] == "OVERLAY"

    certified = SimpleNamespace(
        verified=True,
        trust_level="CERTIFIED",
        rule_id="X",
        rule_revision=1,
        corner_reliefs=(),
    )
    with pytest.raises(ValueError):
        build_relief_promotion_candidate(
            certified,
            cabinet_family="自訂", part_role="head", joint_face="TOP",
            assembly_intent=CornerTypeId.OVERLAY, source_signature={},
        )


def test_vault_door_adapter_reads_fixed_policy_from_registry(monkeypatch):
    import ae_engine.certified_relief_registry as registry
    from ae_engine import sheetmetal_part_adapters as adapters
    from ae_engine.sheetmetal_geometry import FourCornerTypePolicy, build_four_side_outline

    standard = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    forced = FourCornerTypePolicy(standard, standard, standard, standard, fw=25.0)
    monkeypatch.setattr(registry, "certified_corner_policy_for_part", lambda *args, **kwargs: forced, raising=False)

    result = adapters.build_door_result(
        w=400, h=600, t=2, fw=25,
        gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
    )
    expected = build_four_side_outline(result.topology, forced)
    assert [(p.x, p.y) for p in result.outline] == pytest.approx([(p.x, p.y) for p in expected])


def test_bridge_known_model_state_uses_model_family_not_legacy_cabinet_type_field():
    import fold_designer_bridge as bridge

    class Var:
        def get(self): return "受電箱"

    dummy = type("Dummy", (), {})()
    dummy.available_parts = ("head",)
    dummy.baseline_model_var = Var()
    dummy._phase6_input_snapshot = {"model": "受電箱"}
    state = bridge._phase6_known_model_corner_state(dummy)
    assert state["head"]["bottom_left"].type_id is CornerTypeId.CROSS
    assert state["head"]["bottom_left"].cross_mode is CrossCornerMode.STANDARD


def test_every_active_registry_rule_has_unique_versioned_identity_and_evidence():
    from ae_engine.certified_relief_registry import (
        CertifiedReliefStatus,
        registered_certified_corner_policy_rules,
        registered_certified_relief_rules,
    )

    active = {CertifiedReliefStatus.CERTIFIED, CertifiedReliefStatus.CERTIFIED_FROM_3D}
    all_rules = tuple(registered_certified_relief_rules()) + tuple(registered_certified_corner_policy_rules())
    identities = [(rule.rule_id, int(rule.revision)) for rule in all_rules if rule.status in active]
    assert len(identities) == len(set(identities))
    for rule in all_rules:
        if rule.status not in active:
            continue
        assert rule.rule_id.strip()
        assert int(rule.revision) >= 1
        assert str(rule.source_evidence or "").strip()
        if hasattr(rule, "evaluator"):
            assert rule.evaluator is not None
            assert str(rule.formula_x or "").strip()
            assert str(rule.formula_y or "").strip()
        else:
            assert set(rule.corner_selections) == {"bottom_left", "bottom_right", "top_left", "top_right"}


def test_registry_driven_gui_matrix_covers_every_active_assembly_intent():
    from ae_engine.certified_relief_registry import (
        CertifiedReliefStatus,
        registered_certified_relief_rules,
    )
    from tests.test_phase6_assembly_registry_gui_matrix import REGISTERED_CERTIFIED_INTENTS

    active = {CertifiedReliefStatus.CERTIFIED, CertifiedReliefStatus.CERTIFIED_FROM_3D}
    expected = {
        rule.assembly_intent
        for rule in registered_certified_relief_rules()
        if rule.status in active and rule.assembly_intent is not None
    }
    assert set(REGISTERED_CERTIFIED_INTENTS) == expected
