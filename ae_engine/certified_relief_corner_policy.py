# -*- coding: utf-8 -*-
"""Certified fixed CornerType policy registry."""
from __future__ import annotations

from .sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    FourCornerTypePolicy,
)
from .certified_relief_models import (
    CertifiedReliefStatus,
    CertifiedReliefRegistryAmbiguityError,
    CertifiedCornerPolicyRule,
    _active_status,
    _family_key,
)

def _cross_standard() -> CornerTypeSelection:
    return CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)


def _cross_retain_width_1t() -> CornerTypeSelection:
    return CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.WIDTH,
        amount_t=1.0,
    )


def _cross_extra_both_half_t() -> CornerTypeSelection:
    return CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    )


def _insert_overlay_vault_top() -> CornerTypeSelection:
    return CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY,
        amount_t=1.0,
        secondary_retain_t=0.5,
        secondary_depth_t=2.0,
    )


def _insert_overlay_receiving_bottom() -> CornerTypeSelection:
    return CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY,
        amount_t=0.5,
        secondary_retain_t=0.5,
        secondary_depth_t=2.0,
    )


_CORNER_POLICY_RULES: tuple[CertifiedCornerPolicyRule, ...] = (
    CertifiedCornerPolicyRule(
        rule_id="VAULT_ENDCAP_FIXED_POLICY_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="金庫型",
        part_roles=("head", "tail"),
        corner_selections={
            "top_left": _insert_overlay_vault_top(),
            "top_right": _insert_overlay_vault_top(),
            "bottom_left": _cross_extra_both_half_t(),
            "bottom_right": _cross_extra_both_half_t(),
        },
        source_evidence="既有金庫型固定 C04(top)+C03(bottom) 製造契約",
    ),
    CertifiedCornerPolicyRule(
        rule_id="VAULT_DOOR_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="金庫型",
        part_roles=("door",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="既有 Door C02 固定映射",
    ),
    CertifiedCornerPolicyRule(
        rule_id="VAULT_INDICATOR_BOX_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="金庫型",
        part_roles=("indicator_box",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="既有指示燈盒 C02 固定映射",
    ),
    CertifiedCornerPolicyRule(
        rule_id="VAULT_INDICATOR_DOOR_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="金庫型",
        part_roles=("indicator_door",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="既有指示燈小門 C02 固定映射",
    ),
    CertifiedCornerPolicyRule(
        rule_id="VAULT_BASE_PLATE_CROSS_STANDARD_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="金庫型",
        part_roles=("base_plate",),
        corner_selections={key: _cross_standard() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="既有底板 C01 固定映射",
    ),
    CertifiedCornerPolicyRule(
        rule_id="RECEIVING_ENDCAP_FIXED_POLICY_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="受電箱",
        part_roles=("head", "tail"),
        corner_selections={
            "top_left": _insert_overlay_vault_top(),
            "top_right": _insert_overlay_vault_top(),
            "bottom_left": _cross_standard(),
            "bottom_right": _cross_standard(),
        },
        source_evidence=(
            "Joint Graph migration：上方保留既有固定投影；下方只保留 STANDARD 母體。"
            "INSERT/WRAP 等組合語意由 Resolved BOTTOM Joint + Certified Relief Registry 衍生"
        ),
    ),
    # 受電箱 Door/Indicator/Base 目前沿用相同既有固定公式；family 規則明列，
    # 避免 fallback 靜默借用金庫型造成未來 family 分化時污染。
    CertifiedCornerPolicyRule(
        rule_id="RECEIVING_DOOR_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="受電箱",
        part_roles=("door",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="受電箱第一階段沿用 Door 固定截角",
    ),
    CertifiedCornerPolicyRule(
        rule_id="RECEIVING_INDICATOR_BOX_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="受電箱",
        part_roles=("indicator_box",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="受電箱第一階段沿用指示燈盒固定截角",
    ),
    CertifiedCornerPolicyRule(
        rule_id="RECEIVING_INDICATOR_DOOR_CROSS_RETAIN_WIDTH_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="受電箱",
        part_roles=("indicator_door",),
        corner_selections={key: _cross_retain_width_1t() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="受電箱第一階段沿用指示燈小門固定截角",
    ),
    CertifiedCornerPolicyRule(
        rule_id="RECEIVING_BASE_PLATE_CROSS_STANDARD_V1",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="受電箱",
        part_roles=("base_plate",),
        corner_selections={key: _cross_standard() for key in ("bottom_left", "bottom_right", "top_left", "top_right")},
        source_evidence="受電箱第一階段沿用底板標準截角",
    ),
)


def registered_certified_corner_policy_rules() -> tuple[CertifiedCornerPolicyRule, ...]:
    return _CORNER_POLICY_RULES


def _active_status(status: CertifiedReliefStatus) -> bool:
    return status in {CertifiedReliefStatus.CERTIFIED, CertifiedReliefStatus.CERTIFIED_FROM_3D}


def _family_key(value) -> str:
    text = str(value or "").strip()
    if text.upper() == "VAULT":
        return "金庫型"
    return text or "ANY"


def lookup_certified_corner_state(*, cabinet_family, part_keys) -> dict[str, dict[str, CornerTypeSelection]]:
    family = _family_key(cabinet_family)
    result: dict[str, dict[str, CornerTypeSelection]] = {}
    for raw_part in tuple(part_keys or ()):
        part = str(raw_part)
        matches = [
            rule for rule in _CORNER_POLICY_RULES
            if _active_status(rule.status)
            and _family_key(rule.cabinet_family) == family
            and part in rule.part_roles
        ]
        if len(matches) > 1:
            ids = ", ".join(f"{r.rule_id}@{r.revision}" for r in matches)
            raise CertifiedReliefRegistryAmbiguityError(
                f"REGISTRY_AMBIGUOUS: {family}/{part}: {ids}"
            )
        if not matches:
            continue
        result[part] = dict(matches[0].corner_selections)
    return result


def certified_corner_policy_for_part(
    cabinet_family, part_role, *, fw=0.0, bottom_fw=None, top_fw=None
):
    """Return one FourCornerTypePolicy sourced only from the certified registry."""
    from .sheetmetal_geometry import FourCornerTypePolicy

    state = lookup_certified_corner_state(
        cabinet_family=cabinet_family,
        part_keys=(part_role,),
    )
    corners = state.get(str(part_role))
    if corners is None:
        raise KeyError(f"no certified corner policy: {cabinet_family}/{part_role}")
    return FourCornerTypePolicy(
        bottom_left=corners["bottom_left"],
        bottom_right=corners["bottom_right"],
        top_left=corners["top_left"],
        top_right=corners["top_right"],
        fw=float(fw),
        bottom_fw=None if bottom_fw is None else float(bottom_fw),
        top_fw=None if top_fw is None else float(top_fw),
    )
