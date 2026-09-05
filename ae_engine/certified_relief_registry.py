# -*- coding: utf-8 -*-
"""已認證截角公式資料庫（Certified Relief Registry）。

安全契約：
1. 已知組合命中 CERTIFIED / CERTIFIED_FROM_3D 規則時，資料庫公式是製造真值。
2. 3D solver 對已知公式只能做 shadow validation，不得覆蓋 canonical relief。
3. 查不到規則時才允許 3D discovery/fallback。
4. 規則必須版本化；存檔保存 rule_id/revision/trust_level。
5. 多筆同等規則同時命中屬 REGISTRY_AMBIGUOUS，禁止偷偷 fallback。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, Mapping
from pathlib import Path
import ast
import json
import math

from shapely.geometry import box

RELIEF_CONTRACT_VERSION = 3

_ALLOWED_GEOMETRY_INPUTS = frozenset({
    "BOX_BODY_FORMED_FW", "ENDCAP_SIDE_FOLD", "ENDCAP_FW",
    "ENDCAP_YTOP1", "ENDCAP_YBOTTOM1", "BOX_SIDE_REAR_BEND", "SHEET_THICKNESS",
    "BOTTOM_RELIEF_RESERVE_U", "BOTTOM_RELIEF_RESERVE_V",
})

from .sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    resolve_corner_relief,
)


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



_ALLOWED_FORMULA_NAMES = frozenset({
    "T", "FW", "side_fold", "ytop1", "ybottom1", "rear_bend",
    "mating_width", "effective_mating_width", "fold_u", "fold_v", "clearance",
    "reserve_u", "reserve_v",
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
        if not isinstance(raw.get("joint_signature"), list) or not raw.get("joint_signature"):
            raise CertifiedReliefRegistryError(f"missing joint_signature: {rid}@{rev}")
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
        evaluator=evaluator,
    )


def _rule_from_external(rule_id: str, evaluator) -> CertifiedReliefRule:
    raw = _external_record_map().get(str(rule_id))
    if raw is None:
        raise CertifiedReliefRegistryError(f"missing external certified rule: {rule_id}")
    return _rule_from_record(raw, evaluator)



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


def _profile_segment_length(profile, key: str, default: float | None = None) -> float | None:
    for segment in tuple(profile or ()):
        value = None
        if isinstance(segment, dict):
            if segment.get("phase6_key") == key:
                value = segment.get("len", segment.get("length"))
        else:
            if getattr(segment, "phase6_key", None) == key:
                value = getattr(segment, "length", None)
        if value is not None:
            return float(value)
    return None if default is None else float(default)


def _profile_has_key(profile, key: str) -> bool:
    return _profile_segment_length(profile, key, None) is not None


def _assembly_joint_corner_names(endcap_y_profile, joint_face: str = "TOP"):
    """Map semantic EndCap TOP/BOTTOM to physical canonical 2D corners.

    Head scenes are Y-normalized once after manufacturing, while Tail scenes
    stay native.  Therefore semantic TOP/BOTTOM swap physical top/bottom for
    Head, but remain native for Tail.
    """
    keys = []
    for segment in tuple(endcap_y_profile or ()):
        key = segment.get("phase6_key") if isinstance(segment, dict) else getattr(segment, "phase6_key", None)
        if key:
            keys.append(str(key))
    is_tail_native = bool(keys) and keys[0] == "ybottom1"
    semantic = str(joint_face or "TOP").upper().split("_", 1)[0]
    if semantic == "BOTTOM":
        return (("bottom_left", "bottom_right") if is_tail_native else ("top_left", "top_right"))
    return (("top_left", "top_right") if is_tail_native else ("bottom_left", "bottom_right"))


def _side_rear_bend_from_structure_state(structure_state) -> float | None:
    if not structure_state:
        return None
    try:
        from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
        state = normalize_box_body_structure_state(structure_state)
        cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
        value = cfg.get("side_rear_bend")
        return None if value is None else abs(float(value))
    except Exception:
        return None


def _physical_cut_from_relief(corner_name, relief, blank_bounds):
    from .assembly_collision import _physical_corner_geometry
    from .sheetmetal_geometry import _placed_corner_cut_polygons

    minx, miny, maxx, maxy = map(float, blank_bounds)
    width = maxx - minx
    height = maxy - miny
    pieces = _placed_corner_cut_polygons(
        corner_name=corner_name,
        relief=relief,
        width=width,
        height=height,
    )
    # _placed_corner_cut_polygons is expressed in a zero-based blank. Shift if
    # a future material bounds origin differs from (0,0).
    from shapely.affinity import translate
    shifted = [translate(piece, xoff=minx, yoff=miny) for piece in pieces]
    from shapely.ops import unary_union
    return unary_union(shifted)


def _formed_box_body_fw_from_profile(profile, side_key: str, sheet_thickness: float) -> float | None:
    # One Source of Truth with the Fold Editor / main GUI.  Do not reimplement
    # outside-dimension bend counting inside the 3D Registry.
    from phase6_fold_profiles import formed_box_body_fw_widths

    rows = [dict(seg) if isinstance(seg, dict) else {
        "len": getattr(seg, "length", 0.0),
        "angle": getattr(seg, "angle", None),
        "phase6_key": getattr(seg, "phase6_key", None),
        "core": getattr(seg, "core", None),
    } for seg in tuple(profile or ())]
    left, right = formed_box_body_fw_widths(rows, sheet_thickness)
    return left if side_key == "yl1" else right


def _build_formula_result(*, rule, endcap_render_data, box_body_x_profile, endcap_x_profile, endcap_y_profile, sheet_thickness, selection):
    from .assembly_collision import BackprojectedCornerRelief, _measure_canonical_corner_cut
    from .assembly_geometry import restore_unrelieved_endcap_material

    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return None
    bounds = tuple(map(float, restored.bounds))
    t = max(0.0, float(sheet_thickness or 0.0))
    fw = _profile_segment_length(endcap_y_profile, "fw", None)
    if fw is None:
        return None
    top_fold = _profile_segment_length(endcap_y_profile, "ytop1", None)
    if top_fold is None:
        return None
    flat_x = _profile_has_key(endcap_x_profile, "endcap_w_flat")
    if selection.type_id is CornerTypeId.OVERLAY:
        if not flat_x:
            return None
    else:
        if flat_x:
            return None
    cuts = []
    reliefs = []
    joint_corners = _assembly_joint_corner_names(endcap_y_profile, str(rule.joint_face or "TOP"))
    face = str(rule.joint_face or "TOP").upper()
    requested_pairs = tuple(zip(joint_corners, ("yl1", "yr1")))
    if face.endswith("_LEFT"):
        requested_pairs = requested_pairs[:1]
    elif face.endswith("_RIGHT"):
        requested_pairs = requested_pairs[1:2]
    metadata = dict(getattr(endcap_render_data, "metadata", {}) or {})
    for corner_name, side_key in requested_pairs:
        if flat_x:
            formed_fw = _formed_box_body_fw_from_profile(box_body_x_profile, side_key, t)
            side_fold = 0.0 if formed_fw is None else max(0.0, float(formed_fw) - float(fw))
        else:
            side_fold = _profile_segment_length(endcap_x_profile, side_key, None)
        if side_fold is None:
            return None
        resolved = resolve_corner_relief(
            selection,
            fold_u=float(side_fold),
            fold_v=float(top_fold),
            thickness=t,
            fw=float(fw),
        )
        cut = _physical_cut_from_relief(corner_name, resolved, bounds)
        if cut.is_empty:
            return None
        measurement = _measure_canonical_corner_cut(cut, corner_name, bounds, 0.0)
        cuts.append(cut)
        reliefs.append(BackprojectedCornerRelief(corner_name, cut, measurement))
    return CertifiedReliefResult(rule=rule, cut_polygons=tuple(cuts), corner_reliefs=tuple(reliefs))


def _standard_intent_evaluator(selection: CornerTypeSelection):
    def evaluator(*, endcap_render_data, box_body_x_profile, endcap_x_profile, endcap_y_profile, sheet_thickness, rule):
        return _build_formula_result(
            rule=rule,
            endcap_render_data=endcap_render_data,
            box_body_x_profile=box_body_x_profile,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            sheet_thickness=sheet_thickness,
            selection=selection,
        )
    return evaluator


def _structural_contact_width(*, corner_name, blank_bounds, box_body_x_profile, endcap_x_profile, endcap_y_profile, sheet_thickness, tolerance=1e-6):
    """linked-FW INSERT 已認證結構接合寬度公式。"""
    is_left = str(corner_name).endswith("left")
    side_key = "yl1" if is_left else "yr1"
    side_fold = _profile_segment_length(endcap_x_profile, side_key, None)
    fw = _profile_segment_length(endcap_y_profile, "fw", None)
    if side_fold is None or fw is None:
        return None
    width = float(side_fold) + max(0.0, float(fw) - float(sheet_thickness or 0.0))
    minx, _miny, maxx, _maxy = map(float, blank_bounds)
    max_width = (maxx - minx) / 2.0
    if width <= tolerance or width >= max_width:
        return None
    return width


def _top_insert_structural_contact_v1(
    *, endcap_render_data, box_body_x_profile, endcap_x_profile, endcap_y_profile,
    sheet_thickness, rule: CertifiedReliefRule,
):
    from .assembly_collision import (
        BackprojectedCornerRelief,
        _measure_canonical_corner_cut,
        _physical_corner_geometry,
    )
    from .assembly_geometry import restore_unrelieved_endcap_material

    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return None
    blank_bounds = tuple(map(float, restored.bounds))
    t = max(0.0, float(sheet_thickness or 0.0))
    # 只認證「ytop1 已結構性移除、FW 成為上方接合折」的拓撲。
    if _profile_segment_length(endcap_y_profile, "ytop1", None) is not None:
        return None
    fw = _profile_segment_length(endcap_y_profile, "fw", None)
    if fw is None:
        return None
    height = float(fw) + 1.0 * t
    cuts = []
    reliefs = []
    for corner_name in _assembly_joint_corner_names(endcap_y_profile):
        width = _structural_contact_width(
            corner_name=corner_name,
            blank_bounds=blank_bounds,
            box_body_x_profile=box_body_x_profile,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            sheet_thickness=t,
        )
        if width is None:
            return None
        canonical = box(0.0, 0.0, float(width), float(height))
        cut = _physical_corner_geometry(canonical, blank_bounds, corner_name)
        measurement = _measure_canonical_corner_cut(cut, corner_name, blank_bounds, 0.0)
        cuts.append(cut)
        reliefs.append(BackprojectedCornerRelief(corner_name, cut, measurement))
    return CertifiedReliefResult(rule=rule, cut_polygons=tuple(cuts), corner_reliefs=tuple(reliefs))



def _linked_fw_insert_overlay_v1(
    *, endcap_render_data, box_body_x_profile, endcap_x_profile, endcap_y_profile,
    sheet_thickness, rule: CertifiedReliefRule,
):
    """Linked-FW INSERT_OVERLAY formula using the existing certified C04 geometry.

    Preconditions: no independent ``ytop1`` row; X remains folded.  The first
    stage keeps the C04 primary width ``side_fold + FW``.  The second CUTTING
    coordinate is the long-standing manufacturing contract
    ``side_fold + secondary_retain_t*T``; it is not ``side_fold - retain``.
    """
    from .assembly_collision import BackprojectedCornerRelief, _measure_canonical_corner_cut
    from .assembly_geometry import restore_unrelieved_endcap_material
    from .sheetmetal_geometry import ResolvedCornerRelief

    if _profile_segment_length(endcap_y_profile, "ytop1", None) is not None:
        return None
    if _profile_has_key(endcap_x_profile, "endcap_w_flat"):
        return None
    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return None
    bounds = tuple(map(float, restored.bounds))
    t = max(0.0, float(sheet_thickness or 0.0))
    fw = _profile_segment_length(endcap_y_profile, "fw", None)
    if fw is None or t <= 0.0:
        return None

    amount_t = 1.0
    secondary_retain_t = 0.5
    secondary_depth_t = 2.0
    primary_v = float(fw) - amount_t * t
    secondary_depth = secondary_depth_t * t
    if primary_v <= 0.0:
        return None

    cuts = []
    reliefs = []
    for corner_name, side_key in zip(_assembly_joint_corner_names(endcap_y_profile), ("yl1", "yr1")):
        side_fold = _profile_segment_length(endcap_x_profile, side_key, None)
        if side_fold is None:
            return None
        side = abs(float(side_fold))
        primary_u = side + float(fw)
        secondary_u = side + secondary_retain_t * t
        resolved = ResolvedCornerRelief(
            primary_u=primary_u,
            primary_v=primary_v,
            secondary_u=secondary_u,
            secondary_depth=secondary_depth,
        )
        cut = _physical_cut_from_relief(corner_name, resolved, bounds)
        if cut.is_empty:
            return None
        measurement = _measure_canonical_corner_cut(cut, corner_name, bounds, 0.0)
        cuts.append(cut)
        reliefs.append(BackprojectedCornerRelief(corner_name, cut, measurement))
    return CertifiedReliefResult(rule=rule, cut_polygons=tuple(cuts), corner_reliefs=tuple(reliefs))


def _rule_preconditions_match(rule: CertifiedReliefRule, *, endcap_x_profile, endcap_y_profile, metadata) -> bool:
    flat_x = _profile_has_key(endcap_x_profile, "endcap_w_flat")
    ytop = _profile_segment_length(endcap_y_profile, "ytop1", None)
    ybottom = _profile_segment_length(endcap_y_profile, "ybottom1", None)
    for condition in tuple(rule.preconditions or ()):
        key = str(condition).strip().lower()
        if key == "ytop1_present" and ytop is None:
            return False
        if key == "ytop1_absent" and ytop is not None:
            return False
        if key == "ybottom1_present" and ybottom is None:
            return False
        if key == "ybottom1_absent" and ybottom is not None:
            return False
        if key == "x_flat" and not flat_x:
            return False
        if key == "x_folded" and flat_x:
            return False
        if key == "nominal_side_fold_present":
            if metadata.get("nominal_fold_left") is None or metadata.get("nominal_fold_right") is None:
                return False
    return True


def _data_formula_evaluator(
    *, endcap_render_data, box_body_x_profile, endcap_x_profile, endcap_y_profile,
    sheet_thickness, rule: CertifiedReliefRule, box_body_structure_state=None,
):
    """Evaluate a v2 external formula record without arbitrary Python execution."""
    from .assembly_collision import BackprojectedCornerRelief, _measure_canonical_corner_cut
    from .assembly_geometry import restore_unrelieved_endcap_material
    from .sheetmetal_geometry import ResolvedCornerRelief

    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return None
    metadata = dict(getattr(endcap_render_data, "metadata", {}) or {})
    if not _rule_preconditions_match(
        rule, endcap_x_profile=endcap_x_profile, endcap_y_profile=endcap_y_profile, metadata=metadata
    ):
        return None
    bounds = tuple(map(float, restored.bounds))
    t = max(0.0, float(sheet_thickness or 0.0))
    fw = _profile_segment_length(endcap_y_profile, "fw", None)
    if fw is None or t <= 0.0:
        return None
    ytop = _profile_segment_length(endcap_y_profile, "ytop1", None)
    ybottom = _profile_segment_length(endcap_y_profile, "ybottom1", None)
    rear_bend = _side_rear_bend_from_structure_state(box_body_structure_state)
    flat_x = _profile_has_key(endcap_x_profile, "endcap_w_flat")
    face = str(rule.joint_face or "TOP").upper()
    semantic_corners = _assembly_joint_corner_names(endcap_y_profile, face)
    if face.endswith("_LEFT"):
        requested = ((semantic_corners[0], "yl1"),)
    elif face.endswith("_RIGHT"):
        requested = ((semantic_corners[1], "yr1"),)
    else:
        requested = tuple(zip(semantic_corners, ("yl1", "yr1")))
    cuts = []
    reliefs = []
    formed_fw_by_corner = {}
    projection_by_corner = {}
    geometry_projection = None
    if face.startswith("BOTTOM"):
        if rear_bend is None or ybottom is None or flat_x:
            return None
        left_fold = _profile_segment_length(endcap_x_profile, "yl1", None)
        right_fold = _profile_segment_length(endcap_x_profile, "yr1", None)
        core_width = _profile_segment_length(endcap_x_profile, "endcap_w_core", None)
        if left_fold is None or right_fold is None or core_width is None:
            return None
        from .assembly_geometry import derive_side_back_split_endcap_bottom_relief
        geometry_projection = derive_side_back_split_endcap_bottom_relief(
            width=float(core_width) + 4.0 * t, height=0.0, thickness=t,
            side_fold_left=abs(float(left_fold)), side_fold_right=abs(float(right_fold)),
            side_rear_bend=abs(float(rear_bend)), bottom_fold=abs(float(ybottom)),
        )
    formula_record = {"topology_levels": rule.topology_levels, "formula": dict(rule.formula_record or {})}
    for corner_name, side_key in requested:
        if flat_x:
            # OVERLAY removes live X bends, but STANDARD relief still derives
            # from the nominal material side fold (15 in the certified fixture).
            formed_fw = _formed_box_body_fw_from_profile(box_body_x_profile, side_key, t)
            nominal_key = "nominal_fold_left" if side_key == "yl1" else "nominal_fold_right"
            nominal = metadata.get(nominal_key)
            side_fold = None if nominal is None else abs(float(nominal))
            if formed_fw is not None:
                formed_fw_by_corner[str(corner_name)] = float(formed_fw)
        else:
            side_fold = _profile_segment_length(endcap_x_profile, side_key, None)
        if side_fold is None:
            return None
        reserve_u, reserve_v = (t, 0.5 * t)
        if face.startswith("BOTTOM") and box_body_structure_state is not None:
            try:
                from .cabinet_types import receiving as _receiving
                reserve_u, reserve_v = _receiving.bottom_relief_reserves(box_body_structure_state)
            except Exception:
                pass
        variables = {
            "T": t,
            "FW": float(fw),
            "side_fold": abs(float(side_fold)),
            "ytop1": 0.0 if ytop is None else abs(float(ytop)),
            "ybottom1": 0.0 if ybottom is None else abs(float(ybottom)),
            "rear_bend": 0.0 if rear_bend is None else abs(float(rear_bend)),
            "mating_width": float((formed_fw if flat_x and formed_fw is not None else metadata.get("effective_mating_width", fw)) or fw),
            "effective_mating_width": float((formed_fw if flat_x and formed_fw is not None else metadata.get("effective_mating_width", fw)) or fw),
            "fold_u": abs(float(side_fold)),
            "fold_v": 0.0 if ytop is None else abs(float(ytop)),
            "clearance": 0.0,
            "reserve_u": float(reserve_u),
            "reserve_v": float(reserve_v),
        }
        values = evaluate_relief_formula_record(formula_record, variables)
        resolved = ResolvedCornerRelief(
            primary_u=float(values["primary_u"]),
            primary_v=float(values["primary_v"]),
            secondary_u=None if values["secondary_u"] is None else float(values["secondary_u"]),
            secondary_depth=None if values["secondary_depth"] is None else float(values["secondary_depth"]),
        )
        if geometry_projection is not None:
            side_name = "left" if side_key == "yl1" else "right"
            projected = geometry_projection[side_name]
            geometric = projected["relief"]
            rule_relations = {str(item.get("relation", "")) for item in tuple(rule.joint_signature or ())}
            has_adjustable_wrap_reserve = (
                "WRAP" in rule_relations
                and "BOTTOM_RELIEF_RESERVE_U" in tuple(rule.geometry_inputs or ())
                and "BOTTOM_RELIEF_RESERVE_V" in tuple(rule.geometry_inputs or ())
            )
            if not has_adjustable_wrap_reserve:
                formula_tuple = (resolved.primary_u, resolved.primary_v, resolved.secondary_u, resolved.secondary_depth)
                geometry_tuple = (geometric.primary_u, geometric.primary_v, geometric.secondary_u, geometric.secondary_depth)
                for formula_value, geometry_value in zip(formula_tuple, geometry_tuple):
                    if formula_value is None or geometry_value is None or abs(float(formula_value) - float(geometry_value)) > 1e-6:
                        raise CertifiedReliefRegistryError(
                            f"ENGINE_CONFLICT: {rule.rule_id} formula does not match 3D face projection"
                        )
            evidence = dict(projected["world_evidence"])
            evidence["certified_geometric_relief"] = {
                "primary_u": float(geometric.primary_u),
                "primary_v": float(geometric.primary_v),
                "secondary_u": None if geometric.secondary_u is None else float(geometric.secondary_u),
                "secondary_depth": None if geometric.secondary_depth is None else float(geometric.secondary_depth),
            }
            projection_by_corner[str(corner_name)] = evidence
        cut = _physical_cut_from_relief(corner_name, resolved, bounds)
        if cut.is_empty:
            return None
        measurement = _measure_canonical_corner_cut(cut, corner_name, bounds, 0.0)
        cuts.append(cut)
        reliefs.append(BackprojectedCornerRelief(corner_name, cut, measurement))
    result = CertifiedReliefResult(
        rule=rule, cut_polygons=tuple(cuts), corner_reliefs=tuple(reliefs),
        geometry_evidence={
            "geometry_inputs": tuple(rule.geometry_inputs or ()),
            "formed_fw_by_corner": dict(formed_fw_by_corner),
            "side_rear_bend": rear_bend,
            "projection_by_corner": dict(projection_by_corner),
            "source": ("SIDE_BACK_SPLIT_3D_FACE_PROJECTION" if str(rule.joint_face).upper().startswith("BOTTOM") else "BOX_BODY_FOLD_PROFILE"),
        },
    )
    _validate_certified_relief_result_topology(result)
    return result


def evaluate_editable_endcap_rule_record(
    record: Mapping[str, object],
    *,
    endcap_render_data,
    box_body_x_profile,
    endcap_x_profile,
    endcap_y_profile,
    sheet_thickness,
) -> CertifiedReliefResult | None:
    """Evaluate one editable rule without inserting it into the runtime registry.

    This is the only supported path for candidate-specific 3D shadow preview:
    the form record is validated, wrapped in an ephemeral revision-0 CERTIFIED
    rule, evaluated with the production formula evaluator, and then discarded.
    No registry file or global runtime rule list is mutated.
    """
    raw = _validate_editable_rule_record(record)
    ephemeral = dict(raw)
    ephemeral.update({
        "revision": 0,
        "trust_level": CertifiedReliefStatus.CERTIFIED.value,
        "active": False,
    })
    rule = _rule_from_record(ephemeral, _data_formula_evaluator)
    return _data_formula_evaluator(
        endcap_render_data=endcap_render_data,
        box_body_x_profile=box_body_x_profile,
        endcap_x_profile=endcap_x_profile,
        endcap_y_profile=endcap_y_profile,
        sheet_thickness=sheet_thickness,
        rule=rule,
    )


def build_runtime_relief_rules_from_external(path: str | Path | None = None) -> tuple[CertifiedReliefRule, ...]:
    rows = [row for row in load_external_relief_rule_records(path) if bool(row.get("active", True))]
    return tuple(_rule_from_record(row, _data_formula_evaluator) for row in rows)


def reload_runtime_relief_rules(path: str | Path | None = None) -> tuple[CertifiedReliefRule, ...]:
    global _RULES
    _RULES = build_runtime_relief_rules_from_external(path)
    return _RULES


_SPECIAL_RULE_EVALUATORS = {
    "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1": _top_insert_structural_contact_v1,
    "ENDCAP_TOP_INSERT_STANDARD_V1": _standard_intent_evaluator(
        CornerTypeSelection(CornerTypeId.INSERT, amount_t=1.0)
    ),
    "ENDCAP_TOP_OVERLAY_STANDARD_V1": _data_formula_evaluator,
    "ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1": _linked_fw_insert_overlay_v1,
    "ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1": _standard_intent_evaluator(_insert_overlay_vault_top()),
}


def _build_initial_runtime_rules() -> tuple[CertifiedReliefRule, ...]:
    rows = [row for row in load_external_relief_rule_records() if bool(row.get("active", True))]
    return tuple(
        _rule_from_record(row, _SPECIAL_RULE_EVALUATORS.get(str(row.get("rule_id")), _data_formula_evaluator))
        for row in rows
    )


_RULES: tuple[CertifiedReliefRule, ...] = _build_initial_runtime_rules()


def registered_certified_relief_rules() -> tuple[CertifiedReliefRule, ...]:
    return _RULES


def certified_rule_revision_exists(rule_id: str, revision: int) -> bool:
    rid = str(rule_id or "")
    rev = int(revision)
    for rule in (*_RULES, *_CORNER_POLICY_RULES):
        if rule.rule_id == rid and int(rule.revision) == rev and _active_status(rule.status):
            return True
    return False


def _validate_certified_relief_result_topology(result: CertifiedReliefResult) -> None:
    """Reject any certified result whose physical stage count violates its rule.

    This is a registry boundary invariant, not a UI convention: INSERT and
    OVERLAY are one-stage intents; INSERT_OVERLAY is two-stage.  A stale raw
    state or a future evaluator bug must never be able to smuggle a secondary
    stage into a one-stage certified result.
    """
    rule = result.rule
    expected = int(rule.topology_levels)
    for relief in tuple(result.corner_reliefs or ()):
        measurement = getattr(relief, "measurement", None)
        secondary_u = getattr(measurement, "secondary_u", None)
        secondary_depth = getattr(measurement, "secondary_depth", None)
        has_u = secondary_u is not None
        has_depth = secondary_depth is not None
        if has_u != has_depth:
            raise CertifiedReliefRegistryError(
                f"topology malformed: {rule.rule_id}/{getattr(relief, 'corner_name', '?')} "
                "has an incomplete secondary stage"
            )
        actual = 2 if has_u else 1
        if actual != expected:
            raise CertifiedReliefRegistryError(
                f"topology mismatch: {rule.rule_id}/{getattr(relief, 'corner_name', '?')} "
                f"returned {actual} stage(s), expected {expected}"
            )


def lookup_certified_endcap_relief(
    *, assembly_intent, endcap_render_data, box_body_x_profile, endcap_x_profile,
    endcap_y_profile, sheet_thickness, cabinet_family="ANY",
    joint_signature_relations=None, joint_face="TOP", box_body_structure_state=None,
) -> CertifiedReliefResult | None:
    try:
        intent = CornerTypeId(assembly_intent)
    except Exception:
        return None
    family = _family_key(cabinet_family)
    matches: list[CertifiedReliefResult] = []
    requested_relations = None
    if joint_signature_relations is not None:
        requested_relations = tuple(sorted(str(getattr(v, "value", v)) for v in joint_signature_relations))
    requested_face = str(joint_face or "TOP").upper()
    for rule in _RULES:
        if rule.assembly_intent not in (None, intent) or not _active_status(rule.status) or rule.evaluator is None:
            continue
        rule_face = str(rule.joint_face or "TOP").upper()
        base_requested_face = requested_face.split("_")[0]
        if rule_face != requested_face and not (rule_face == base_requested_face and requested_face in {"TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"}):
            continue
        if requested_relations is not None:
            rule_relations = tuple(sorted(str(item.get("relation", "")) for item in tuple(rule.joint_signature or ())))
            if len(requested_relations) == 1:
                # Legacy caller compatibility: a single relation is a minimum
                # required relation, not a claim that the corner has one edge.
                if requested_relations[0] not in rule_relations:
                    continue
            elif rule_relations != requested_relations:
                continue
        rule_family = _family_key(rule.cabinet_family)
        if rule_family not in {"ANY", family}:
            continue
        evaluator_rule = rule if requested_face == rule_face else replace(rule, joint_face=requested_face)
        evaluator_kwargs = dict(
            endcap_render_data=endcap_render_data,
            box_body_x_profile=box_body_x_profile,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            sheet_thickness=sheet_thickness,
            rule=evaluator_rule,
        )
        if rule.evaluator is _data_formula_evaluator:
            evaluator_kwargs["box_body_structure_state"] = box_body_structure_state
        result = rule.evaluator(**evaluator_kwargs)
        if result is not None:
            _validate_certified_relief_result_topology(result)
            matches.append(result)
    if not matches:
        return None
    # Family-specific beats ANY.  Within one specificity, preconditions must
    # resolve to a single rule; otherwise refuse automatic geometry choice.
    specific = [r for r in matches if _family_key(r.rule.cabinet_family) == family and family != "ANY"]
    candidates = specific or matches
    if len(candidates) > 1:
        ids = ", ".join(f"{item.rule_id}@{item.rule_revision}" for item in candidates)
        raise CertifiedReliefRegistryAmbiguityError(
            f"REGISTRY_AMBIGUOUS: {family}/{intent.value}: {ids}"
        )
    return candidates[0]


def lookup_certified_endcap_relief_from_graph(
    *, graph, endcap_part, endcap_render_data, box_body_x_profile, endcap_x_profile,
    endcap_y_profile, sheet_thickness, cabinet_family="ANY", box_body_structure_state=None,
):
    """Resolve Head/Tail TOP corners from explicit local Joint patterns.

    Both top corners must resolve to a certified rule before returning a combined
    manufacturing result.  A mixed HIT/MISS remains provisional rather than
    silently borrowing the high-level preset formula for the missing side.
    """
    from .corner_resolver import registry_intent_for_corner
    results = []
    for corner_name in ("top_left", "top_right"):
        intent = registry_intent_for_corner(graph, endcap_part, corner_name)
        if intent is None:
            return None
        local = lookup_certified_endcap_relief(
            assembly_intent=intent,
            endcap_render_data=endcap_render_data,
            box_body_x_profile=box_body_x_profile,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            sheet_thickness=sheet_thickness,
            cabinet_family=cabinet_family,
            joint_face="TOP_LEFT" if corner_name.endswith("left") else "TOP_RIGHT",
            box_body_structure_state=box_body_structure_state,
        )
        if local is None:
            return None
        results.append(local)
    first = results[0]
    if any(item.rule_id != first.rule_id or item.rule_revision != first.rule_revision for item in results[1:]):
        return None
    return CertifiedReliefResult(
        rule=first.rule,
        cut_polygons=tuple(poly for item in results for poly in tuple(item.cut_polygons or ())),
        corner_reliefs=tuple(rel for item in results for rel in tuple(item.corner_reliefs or ())),
        geometry_evidence={
            "owner": "RESOLVED_ASSEMBLY_GRAPH",
            "corners": {name: {"rule_id": item.rule_id, "revision": item.rule_revision} for name, item in zip(("top_left", "top_right"), results)},
        },
    )


def _serialize_measurement(item):
    m = getattr(item, "measurement", None)
    if m is None:
        return None
    return {
        "corner_name": str(getattr(m, "corner_name", getattr(item, "corner_name", ""))),
        "primary_u": float(m.primary_u),
        "primary_v": float(m.primary_v),
        "secondary_u": None if m.secondary_u is None else float(m.secondary_u),
        "secondary_depth": None if m.secondary_depth is None else float(m.secondary_depth),
    }


def build_relief_promotion_candidate(
    solution, *, cabinet_family, part_role, joint_face, assembly_intent, source_signature,
):
    """建立 promotion manifest；此 API 永遠不修改 registry。"""
    if not bool(getattr(solution, "verified", False)):
        raise ValueError("未通過 3D 驗證的結果不可建立認證候選")
    if str(getattr(solution, "trust_level", "")) != CertifiedReliefStatus.PROVISIONAL_3D.value:
        raise ValueError("只有 PROVISIONAL_3D 結果可建立認證候選")
    try:
        intent = CornerTypeId(assembly_intent)
    except Exception as exc:
        raise ValueError("未知 Assembly Intent") from exc
    measurements = [
        value for value in (_serialize_measurement(item) for item in tuple(getattr(solution, "corner_reliefs", ()) or ()))
        if value is not None
    ]
    return {
        "status": "PROMOTION_CANDIDATE",
        "mutates_registry": False,
        "cabinet_family": str(cabinet_family or ""),
        "part_role": str(part_role or ""),
        "joint_face": str(joint_face or ""),
        "assembly_intent": intent.value,
        "source_signature": dict(source_signature or {}),
        "measurements": measurements,
    }


def _default_candidate_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "基準檔" / "截角資料庫" / "relief_rule_candidates.json"


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_relief_rule_candidates(path: str | Path | None = None) -> tuple[dict[str, object], ...]:
    target = Path(path) if path is not None else _default_candidate_registry_path()
    if not target.exists():
        return ()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CertifiedReliefRegistryError(f"cannot load relief candidates: {target}: {exc}") from exc
    if int(payload.get("schema_version", 0) or 0) != 1:
        raise CertifiedReliefRegistryError("unsupported relief candidate schema_version")
    rows = payload.get("candidates", ())
    if not isinstance(rows, list):
        raise CertifiedReliefRegistryError("relief candidates must be an array")
    return tuple(dict(row) for row in rows)


def _validate_editable_rule_record(record: Mapping[str, object]) -> dict[str, object]:
    raw = dict(record or {})
    rid = str(raw.get("rule_id") or "").strip()
    if not rid:
        raise CertifiedReliefRegistryError("candidate requires rule_id")
    raw_intent = str(raw.get("assembly_intent") or "").strip().upper()
    try:
        intent = None if raw_intent == "ANY" else CornerTypeId(raw_intent)
    except Exception as exc:
        raise CertifiedReliefRegistryError("candidate has unknown assembly_intent") from exc
    if intent is CornerTypeId.CROSS:
        raise CertifiedReliefRegistryError("candidate assembly_intent must be an assembly type")
    topology = int(raw.get("topology_levels", 0) or 0)
    if topology not in (1, 2):
        raise CertifiedReliefRegistryError("candidate topology_levels must be 1 or 2")
    if intent is not None:
        semantic_topology = 2 if intent is CornerTypeId.INSERT_OVERLAY else 1
        if topology != semantic_topology:
            raise CertifiedReliefRegistryError(
                f"candidate topology mismatch: {intent.value} requires {semantic_topology} stage(s)"
            )
    signature = raw.get("joint_signature")
    if not isinstance(signature, list) or not signature:
        raise CertifiedReliefRegistryError("candidate requires joint_signature")
    signature_relations = set()
    for entry in signature:
        if not isinstance(entry, dict) or not str(entry.get("relation") or "").strip():
            raise CertifiedReliefRegistryError("candidate joint_signature entry requires relation")
        try:
            from .assembly_joint import AssemblyJointRelation
            relation = AssemblyJointRelation(str(entry["relation"]))
            signature_relations.add(relation.value)
        except Exception as exc:
            raise CertifiedReliefRegistryError(f"unknown joint relation: {entry.get('relation')}") from exc
    if intent is None and "WRAP" not in signature_relations:
        raise CertifiedReliefRegistryError("assembly_intent ANY is only valid for Joint-specific WRAP rules")
    formula = raw.get("formula")
    if not isinstance(formula, dict) or not formula:
        raise CertifiedReliefRegistryError("candidate requires formula")
    # Syntax/whitelist check without claiming a particular dimensional fixture.
    probe = {name: 1.0 for name in _ALLOWED_FORMULA_NAMES}
    evaluate_relief_formula_record({"topology_levels": topology, "formula": formula}, probe)
    if not str(raw.get("source") or "").strip():
        raise CertifiedReliefRegistryError("candidate requires source evidence")
    raw["rule_id"] = rid
    raw["assembly_intent"] = "ANY" if intent is None else intent.value
    raw["topology_levels"] = topology
    raw.setdefault("cabinet_family", "ANY")
    raw.setdefault("part_role", "HEAD_OR_TAIL")
    raw.setdefault("joint_face", "TOP")
    raw.setdefault("preconditions", [])
    return raw


def save_relief_rule_candidate(record: Mapping[str, object], *, path: str | Path | None = None) -> dict[str, object]:
    import uuid
    target = Path(path) if path is not None else _default_candidate_registry_path()
    raw = _validate_editable_rule_record(record)
    rows = list(load_relief_rule_candidates(target)) if target.exists() else []
    candidate_id = str(raw.get("candidate_id") or uuid.uuid4().hex)
    if any(str(row.get("candidate_id")) == candidate_id for row in rows):
        raise CertifiedReliefRegistryError(f"candidate_id already exists: {candidate_id}")
    item = dict(raw)
    item.update({
        "candidate_id": candidate_id,
        "status": "CANDIDATE",
        "mutates_registry": False,
    })
    rows.append(item)
    _write_json_atomic(target, {"schema_version": 1, "candidates": rows})
    return dict(item)


def promote_relief_rule_candidate(
    candidate_id: str,
    *,
    regression_evidence: Mapping[str, object],
    candidates_path: str | Path | None = None,
    certified_path: str | Path | None = None,
) -> dict[str, object]:
    evidence = dict(regression_evidence or {})
    if not bool(evidence.get("matrix_passed")) or int(evidence.get("cases", 0) or 0) < 1 or not bool(evidence.get("zero_penetration")):
        raise CertifiedReliefRegistryError("promotion requires regression evidence with matrix_passed/cases/zero_penetration")
    if evidence.get("candidate_specific") is not True:
        raise CertifiedReliefRegistryError("promotion requires candidate-specific 3D validation evidence")
    if str(evidence.get("candidate_id") or "") != str(candidate_id):
        raise CertifiedReliefRegistryError("promotion candidate_id does not match regression evidence")
    cpath = Path(candidates_path) if candidates_path is not None else _default_candidate_registry_path()
    rows = list(load_relief_rule_candidates(cpath))
    index = next((i for i, row in enumerate(rows) if str(row.get("candidate_id")) == str(candidate_id)), None)
    if index is None:
        raise CertifiedReliefRegistryError(f"candidate not found: {candidate_id}")
    candidate = dict(rows[index])
    if candidate.get("status") != "CANDIDATE":
        raise CertifiedReliefRegistryError("candidate is not promotable")
    clean = _validate_editable_rule_record(candidate)
    rpath = Path(certified_path) if certified_path is not None else _default_external_registry_path()
    if rpath.exists():
        payload = json.loads(rpath.read_text(encoding="utf-8"))
        if int(payload.get("schema_version", 0) or 0) != 2:
            raise CertifiedReliefRegistryError("unsupported certified registry schema_version")
        certified_rows = list(payload.get("rules", ()) or ())
    else:
        certified_rows = []
    prior_revisions = [int(row.get("revision", 0) or 0) for row in certified_rows if str(row.get("rule_id")) == clean["rule_id"]]
    new_revision = max(prior_revisions, default=0) + 1
    promoted = {k: v for k, v in clean.items() if k not in {"candidate_id", "status", "mutates_registry"}}
    promoted.update({
        "revision": new_revision,
        "trust_level": "CERTIFIED",
        "active": True,
        "regression_evidence": evidence,
    })
    # Older revisions remain immutable history but become inactive when a new
    # revision of the same rule_id is promoted.
    for row in certified_rows:
        if str(row.get("rule_id")) == clean["rule_id"] and bool(row.get("active", True)):
            row["active"] = False
    certified_rows.append(promoted)
    _write_json_atomic(rpath, {"schema_version": 2, "rules": certified_rows})
    rows[index] = dict(candidate, status="PROMOTED", promoted_revision=new_revision)
    _write_json_atomic(cpath, {"schema_version": 1, "candidates": rows})
    if certified_path is None:
        reload_runtime_relief_rules()
    return dict(promoted)
