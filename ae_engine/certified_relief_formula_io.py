# -*- coding: utf-8 -*-
"""External certified-relief rule loading and safe formula evaluation."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from typing import Mapping

from .sheetmetal_geometry import CornerTypeId
from .certified_relief_models import (
    CertifiedReliefStatus,
    CertifiedReliefRegistryError,
    CertifiedReliefRule,
)

_ALLOWED_GEOMETRY_INPUTS = frozenset({
    "BOX_BODY_FORMED_FW", "ENDCAP_SIDE_FOLD", "ENDCAP_FW",
    "ENDCAP_YTOP1", "ENDCAP_YBOTTOM1", "BOX_SIDE_REAR_BEND", "SHEET_THICKNESS",
    "BOTTOM_RELIEF_RESERVE_U", "BOTTOM_RELIEF_RESERVE_V",
    "DIVIDER_CORE_START", "DIVIDER_FIRST_OUTSIDE", "DIVIDER_FW_OUTSIDE",
    "DIVIDER_FW_MATERIAL", "DIVIDER_LAST_OUTSIDE", "BOX_ZL1_FORMED",
})

_ALLOWED_FORMULA_NAMES = frozenset({
    "T", "FW", "side_fold", "ytop1", "ybottom1", "rear_bend",
    "mating_width", "effective_mating_width", "fold_u", "fold_v", "clearance",
    "reserve_u", "reserve_v",
    "core_start", "divider_first_outside", "divider_fw_outside",
    "divider_fw_material", "divider_last_outside", "box_zl1_formed",
})
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def _default_external_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "基準檔" / "截角資料庫" / "certified_relief_rules.json"


def load_external_relief_rule_records(path: str | Path | None = None) -> tuple[dict[str, object], ...]:
    target = Path(path) if path is not None else _default_external_registry_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CertifiedReliefRegistryError(f"cannot load certified relief registry: {target}: {exc}") from exc
    if int(payload.get("schema_version", 0) or 0) != 2:
        raise CertifiedReliefRegistryError("unsupported certified relief registry schema_version")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise CertifiedReliefRegistryError("certified relief registry rules must be an array")
    seen = set()
    result = []
    for raw in rules:
        if not isinstance(raw, dict):
            raise CertifiedReliefRegistryError("registry rule must be an object")
        rid = str(raw.get("rule_id") or "").strip()
        rev = int(raw.get("revision", 0) or 0)
        if not rid or rev < 1:
            raise CertifiedReliefRegistryError("registry rule requires rule_id and revision>=1")
        key = (rid, rev)
        if key in seen:
            raise CertifiedReliefRegistryError(f"duplicate registry revision: {rid}@{rev}")
        seen.add(key)
        topology = int(raw.get("topology_levels", 0) or 0)
        if topology not in (1, 2):
            raise CertifiedReliefRegistryError(f"invalid topology_levels: {rid}@{rev}")
        rule_domain = str(raw.get("rule_domain") or "ENDCAP_RELIEF").strip().upper()
        if rule_domain not in {"ENDCAP_RELIEF", "DIVIDER_CROSS"}:
            raise CertifiedReliefRegistryError(f"unsupported rule_domain: {rid}@{rev}: {rule_domain}")
        joint_signature = raw.get("joint_signature")
        if rule_domain == "ENDCAP_RELIEF":
            if not isinstance(joint_signature, list) or not joint_signature:
                raise CertifiedReliefRegistryError(f"missing joint_signature: {rid}@{rev}")
        else:
            if str(raw.get("part_role") or "").strip().upper() != "DIVIDER":
                raise CertifiedReliefRegistryError(f"DIVIDER_CROSS requires part_role=DIVIDER: {rid}@{rev}")
            if str(raw.get("corner_type") or "").strip().upper() != CornerTypeId.CROSS.value:
                raise CertifiedReliefRegistryError(f"DIVIDER_CROSS requires corner_type=CROSS: {rid}@{rev}")
            if joint_signature not in (None, []):
                raise CertifiedReliefRegistryError(
                    f"DIVIDER_CROSS must not declare AssemblyJoint relations: {rid}@{rev}"
                )
        geometry_inputs = raw.get("geometry_inputs")
        if geometry_inputs is not None:
            if not isinstance(geometry_inputs, list) or not geometry_inputs:
                raise CertifiedReliefRegistryError(f"invalid geometry_inputs: {rid}@{rev}")
            unknown_inputs = [str(v) for v in geometry_inputs if str(v) not in _ALLOWED_GEOMETRY_INPUTS]
            if unknown_inputs:
                raise CertifiedReliefRegistryError(f"unknown geometry_inputs for {rid}@{rev}: {unknown_inputs}")
            if len({str(v) for v in geometry_inputs}) != len(geometry_inputs):
                raise CertifiedReliefRegistryError(f"duplicate geometry_inputs: {rid}@{rev}")
        if not isinstance(raw.get("formula"), dict) or not raw.get("formula"):
            raise CertifiedReliefRegistryError(f"missing formula: {rid}@{rev}")
        result.append(dict(raw))
    return tuple(result)


def _formula_ast_value(node, variables):
    if isinstance(node, ast.Expression):
        return _formula_ast_value(node.body, variables)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in _ALLOWED_FORMULA_NAMES or node.id not in variables:
            raise CertifiedReliefRegistryError(f"formula variable not allowed or unresolved: {node.id}")
        value = float(variables[node.id])
        if not math.isfinite(value):
            raise CertifiedReliefRegistryError(f"formula variable is not finite: {node.id}")
        return value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        value = _formula_ast_value(node.operand, variables)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _formula_ast_value(node.left, variables)
        right = _formula_ast_value(node.right, variables)
        try:
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        except ZeroDivisionError as exc:
            raise CertifiedReliefRegistryError("formula division by zero") from exc
    raise CertifiedReliefRegistryError(f"formula syntax not allowed: {type(node).__name__}")


def evaluate_relief_formula_expression(expression: str, variables: Mapping[str, float]) -> float:
    try:
        tree = ast.parse(str(expression), mode="eval")
    except SyntaxError as exc:
        raise CertifiedReliefRegistryError(f"invalid formula syntax: {expression}") from exc
    value = float(_formula_ast_value(tree, variables))
    if not math.isfinite(value):
        raise CertifiedReliefRegistryError("formula result is NaN/Inf")
    return value


def evaluate_relief_formula_record(record: Mapping[str, object], variables: Mapping[str, float]) -> dict[str, float | None]:
    topology = int(record.get("topology_levels", 0) or 0)
    formula = dict(record.get("formula", {}) or {})
    required = ("primary_u", "primary_v")
    if any(name not in formula for name in required):
        raise CertifiedReliefRegistryError("formula requires primary_u and primary_v")
    has_secondary = "secondary_u" in formula or "secondary_depth" in formula
    if topology == 1 and has_secondary:
        raise CertifiedReliefRegistryError("one-stage formula must not define secondary geometry")
    if topology == 2 and not ("secondary_u" in formula and "secondary_depth" in formula):
        raise CertifiedReliefRegistryError("two-stage formula requires complete secondary geometry")
    result = {
        "primary_u": evaluate_relief_formula_expression(formula["primary_u"], variables),
        "primary_v": evaluate_relief_formula_expression(formula["primary_v"], variables),
        "secondary_u": None,
        "secondary_depth": None,
    }
    if topology == 2:
        result["secondary_u"] = evaluate_relief_formula_expression(formula["secondary_u"], variables)
        result["secondary_depth"] = evaluate_relief_formula_expression(formula["secondary_depth"], variables)
    for key, value in result.items():
        if value is not None and value < 0:
            raise CertifiedReliefRegistryError(f"formula result negative: {key}={value}")
    return result


def evaluate_divider_cross_formula_record(
    record: Mapping[str, object],
    variables: Mapping[str, float],
) -> dict[str, float]:
    """Evaluate the Divider CROSS A-model without replacing fold_u/fold_v ownership."""
    formula = dict(record.get("formula", {}) or {})
    required = (
        "slotted_fold_u", "plain_fold_u", "fold_v",
        "slot_width", "slot_straight_depth", "slot_radius",
    )
    missing = [name for name in required if name not in formula]
    if missing:
        raise CertifiedReliefRegistryError(
            "Divider CROSS formula missing: " + ", ".join(missing)
        )
    result = {
        name: evaluate_relief_formula_expression(str(formula[name]), variables)
        for name in required
    }
    for key, value in result.items():
        if value <= 0:
            raise CertifiedReliefRegistryError(
                f"Divider CROSS formula result must be > 0: {key}={value}"
            )
    if 2.0 * result["slot_radius"] > result["slot_width"] + 1e-9:
        raise CertifiedReliefRegistryError(
            "Divider CROSS slot_radius cannot exceed half slot_width"
        )
    return result


def _external_record_map() -> dict[str, dict[str, object]]:
    records = [r for r in load_external_relief_rule_records() if bool(r.get("active", True))]
    return {str(r["rule_id"]): r for r in records}


def _rule_from_record(raw: Mapping[str, object], evaluator) -> CertifiedReliefRule:
    try:
        status = CertifiedReliefStatus(str(raw.get("trust_level")))
        raw_intent = str(raw.get("assembly_intent") or "").strip().upper()
        intent = None if raw_intent == "ANY" else CornerTypeId(raw_intent)
    except Exception as exc:
        raise CertifiedReliefRegistryError(f"invalid external certified rule enum: {raw.get('rule_id')}") from exc
    formula = dict(raw.get("formula", {}) or {})
    return CertifiedReliefRule(
        rule_id=str(raw["rule_id"]),
        revision=int(raw["revision"]),
        status=status,
        cabinet_family=str(raw.get("cabinet_family", "ANY") or "ANY"),
        part_role=str(raw.get("part_role", "HEAD_OR_TAIL") or "HEAD_OR_TAIL"),
        joint_face=str(raw.get("joint_face", "TOP") or "TOP"),
        assembly_intent=intent,
        topology_levels=int(raw["topology_levels"]),
        formula_x=str(raw.get("display_formula_x") or formula.get("primary_u") or ""),
        formula_y=str(raw.get("display_formula_y") or formula.get("primary_v") or ""),
        rule_domain=str(raw.get("rule_domain") or "ENDCAP_RELIEF").strip().upper(),
        formula_secondary=(None if not raw.get("display_formula_secondary") else str(raw.get("display_formula_secondary"))),
        joint_signature=tuple(dict(v) for v in raw.get("joint_signature", ()) or ()),
        preconditions=tuple(str(v) for v in raw.get("preconditions", ()) or ()),
        formula_record=formula,
        geometry_inputs=tuple(str(v) for v in raw.get("geometry_inputs", ()) or ()),
        source_evidence=str(raw.get("source", "") or ""),
        standard_ref=str(raw.get("standard_ref", "") or ""),
        affected_zone=str(raw.get("affected_zone", "") or ""),
        dimension_space=str(raw.get("dimension_space", "") or ""),
        target_semantics=str(raw.get("target_semantics", "") or ""),
        adjustment_type=str(raw.get("adjustment_type", "") or ""),
        adjustment_amount=raw.get("adjustment_amount"),
        certification_evidence=raw.get("certification_evidence"),
        corner_type=str(raw.get("corner_type", "") or ""),
        cross_parameters=dict(raw.get("cross_parameters", {}) or {}),
        evaluator=evaluator,
    )


def _rule_from_external(rule_id: str, evaluator) -> CertifiedReliefRule:
    raw = _external_record_map().get(str(rule_id))
    if raw is None:
        raise CertifiedReliefRegistryError(f"missing external certified rule: {rule_id}")
    return _rule_from_record(raw, evaluator)
