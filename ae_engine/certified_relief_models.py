# -*- coding: utf-8 -*-
"""Core certified-relief registry value types and shared normalization."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping

from .sheetmetal_geometry import CornerTypeId, CornerTypeSelection

class CertifiedReliefStatus(str, Enum):
    CERTIFIED = "CERTIFIED"
    PROVISIONAL_3D = "PROVISIONAL_3D"
    CERTIFIED_FROM_3D = "CERTIFIED_FROM_3D"
    ENGINE_CONFLICT = "ENGINE_CONFLICT"
    FAILED = "FAILED"


class CertifiedReliefRegistryError(RuntimeError):
    pass


class CertifiedReliefRegistryAmbiguityError(CertifiedReliefRegistryError):
    pass


@dataclass(frozen=True)
class CertifiedReliefRule:
    rule_id: str
    revision: int
    status: CertifiedReliefStatus
    cabinet_family: str
    part_role: str
    joint_face: str
    assembly_intent: CornerTypeId | None
    topology_levels: int
    formula_x: str
    formula_y: str
    rule_domain: str = "ENDCAP_RELIEF"
    formula_secondary: str | None = None
    joint_signature: tuple[Mapping[str, str], ...] = ()
    preconditions: tuple[str, ...] = ()
    formula_record: Mapping[str, str] | None = None
    geometry_inputs: tuple[str, ...] = ()
    symmetry_policy: str = "MIRROR_IF_GEOMETRY_SYMMETRIC"
    source_evidence: str = ""
    standard_ref: str = ""
    affected_zone: str = ""
    dimension_space: str = ""
    target_semantics: str = ""
    adjustment_type: str = ""
    adjustment_amount: object | None = None
    certification_evidence: object | None = None
    corner_type: str = ""
    cross_parameters: Mapping[str, object] | None = None
    solver_shadow_policy: str = "REQUIRED_NO_OVERRIDE"
    evaluator: Callable[..., "CertifiedReliefResult | None"] | None = None


@dataclass(frozen=True)
class CertifiedReliefResult:
    rule: CertifiedReliefRule
    cut_polygons: tuple[object, ...]
    corner_reliefs: tuple[object, ...]
    geometry_evidence: Mapping[str, object] | None = None

    @property
    def rule_id(self) -> str:
        return self.rule.rule_id

    @property
    def rule_revision(self) -> int:
        return int(self.rule.revision)

    @property
    def trust_level(self) -> CertifiedReliefStatus:
        return self.rule.status


@dataclass(frozen=True)
class CertifiedDividerCrossReliefResult:
    """Certified Divider CROSS result: primary stays fold_u/fold_v; slot is additive."""

    rule: CertifiedReliefRule
    min_y: object
    max_y: object
    geometry_evidence: Mapping[str, object] | None = None


@dataclass(frozen=True)
class CertifiedCornerPolicyRule:
    """固定板件 CornerType 資料庫項目。

    只保存「已知的選型公式/參數」，不保存某一次 W/H/D/T 算出的死尺寸。
    """

    rule_id: str
    revision: int
    status: CertifiedReliefStatus
    cabinet_family: str
    part_roles: tuple[str, ...]
    corner_selections: Mapping[str, CornerTypeSelection]
    source_evidence: str = ""


def _active_status(status: CertifiedReliefStatus) -> bool:
    return status in {CertifiedReliefStatus.CERTIFIED, CertifiedReliefStatus.CERTIFIED_FROM_3D}


def _family_key(value) -> str:
    text = str(value or "").strip()
    if text.upper() == "VAULT":
        return "金庫型"
    return text or "ANY"
