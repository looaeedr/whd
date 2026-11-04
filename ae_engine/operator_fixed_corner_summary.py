# -*- coding: utf-8 -*-
"""Engine-owned read-only EndCap fixed-corner/operator Joint presentation.

Family resolution and the resolved BOTTOM AssemblyJoint relation must agree
with the physical Engine family. This produces only human-readable labels:
no corner geometry, PartSpec, export authorization, or GUI dependencies.
"""
from __future__ import annotations

from collections.abc import Mapping

from .assembly_joint import AssemblyJointRelation, edge_relation_for_part
from .cabinet_types.policy import canonical_family_name


def project_operator_fixed_corner_summary(
    model_name: object, part_key: object, joint_state: Mapping[str, object] | None,
) -> str | None:
    """Return Receiving EndCap summary, otherwise defer legacy fixed labels.

    Resolve all registered Receiving aliases with the same Family registry as
    manufacture. A display-only label must never silently reinterpret a
    Receiving family as a Vault-family fixed corner simply because the UI
    loaded a lowercase/legacy cabinet type string.
    """
    if canonical_family_name(model_name) != "受電箱" or part_key not in {"head", "tail"}:
        return None
    relation = edge_relation_for_part(dict(joint_state or {}), str(part_key), "BOTTOM")
    if relation is AssemblyJointRelation.WRAP:
        lower = "下方：包覆貼外（BOTTOM＝WRAP；FW 基準＝側板後折＋1T）"
    elif relation is AssemblyJointRelation.INSERT:
        lower = "下方：標準截角（BOTTOM＝嵌入；WRAP 關閉）"
    elif relation is None:
        lower = "下方：標準截角（BOTTOM Joint 未定義）"
    else:
        lower = f"下方：標準截角（BOTTOM＝{relation.value}）"
    return "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n" + lower
