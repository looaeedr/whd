# -*- coding: utf-8 -*-
"""Global AssemblyJoint contracts and semantics.

Assembly Intent is a high-level operator choice.  ``AssemblyJoint`` is the
resolved entity-to-entity mechanical relation consumed by geometry, registry,
solver, diagnostics and serialization.  WRAP direction is encoded by the
ordered pair ``subject_part -> target_part``: the subject is the outer wrapper.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class AssemblyJointRelation(str, Enum):
    INSERT = "INSERT"
    OVERLAY = "OVERLAY"
    INSERT_OVERLAY = "INSERT_OVERLAY"
    WRAP = "WRAP"


class AssemblyJointSource(str, Enum):
    INTENT_DERIVED = "INTENT_DERIVED"
    USER_ADDED = "USER_ADDED"
    FAMILY_GEOMETRY = "FAMILY_GEOMETRY"
    LEGACY_MIGRATED = "LEGACY_MIGRATED"
    SOLVER_CONFIRMED = "SOLVER_CONFIRMED"


@dataclass(frozen=True)
class JointSemantics:
    relation: AssemblyJointRelation
    has_outer_contact: bool
    has_inner_insertion: bool
    preserve_side: str
    mating_relation: str
    legal_contact_mode: str
    illegal_penetration_mode: str = "NO_SOLID_PENETRATION"
    family_override_allowed: bool = False


_JOINT_SEMANTICS: Mapping[AssemblyJointRelation, JointSemantics] = {
    AssemblyJointRelation.INSERT: JointSemantics(
        AssemblyJointRelation.INSERT,
        has_outer_contact=False,
        has_inner_insertion=True,
        preserve_side="TARGET",
        mating_relation="INNER_INSERT",
        legal_contact_mode="INSERTION_MATING_CONTACT",
    ),
    AssemblyJointRelation.OVERLAY: JointSemantics(
        AssemblyJointRelation.OVERLAY,
        has_outer_contact=True,
        has_inner_insertion=False,
        preserve_side="SUBJECT",
        mating_relation="OUTER_OVERLAY",
        legal_contact_mode="OUTER_FACE_CONTACT",
    ),
    AssemblyJointRelation.INSERT_OVERLAY: JointSemantics(
        AssemblyJointRelation.INSERT_OVERLAY,
        has_outer_contact=True,
        has_inner_insertion=True,
        preserve_side="SUBJECT_OUTER_CONTACT",
        mating_relation="OUTER_OVERLAY_AND_INNER_INSERT",
        legal_contact_mode="OUTER_FACE_AND_INSERTION_CONTACT",
    ),
    AssemblyJointRelation.WRAP: JointSemantics(
        AssemblyJointRelation.WRAP,
        has_outer_contact=True,
        has_inner_insertion=False,
        preserve_side="SUBJECT",
        mating_relation="OUTER_WRAP",
        legal_contact_mode="WRAP_CONTACT",
    ),
}


def _relation(value) -> AssemblyJointRelation:
    if isinstance(value, AssemblyJointRelation):
        return value
    raw = getattr(value, "value", value)
    return AssemblyJointRelation(str(raw))


def joint_semantics(relation) -> JointSemantics:
    return _JOINT_SEMANTICS[_relation(relation)]


@dataclass(frozen=True)
class AssemblyJoint:
    joint_id: str
    subject_part: str
    target_part: str
    subject_region: str = ""
    target_region: str = ""
    relation: AssemblyJointRelation = AssemblyJointRelation.INSERT
    contact_mode: str = "AUTO"
    preserve_side: str = "AUTO"
    relief_intent: str = "AUTO"
    clearance_policy: str = "ZERO"
    solver_constraints: Mapping[str, object] = field(default_factory=dict)
    source: AssemblyJointSource = AssemblyJointSource.INTENT_DERIVED
    edge: str = ""
    direction: str = "AUTO"
    clearance_intent: str = "ZERO"
    revision: int = 1
    migration_origin: str = ""

    def __post_init__(self):
        object.__setattr__(self, "joint_id", str(self.joint_id or "").strip())
        object.__setattr__(self, "subject_part", str(self.subject_part or "").strip())
        object.__setattr__(self, "target_part", str(self.target_part or "").strip())
        object.__setattr__(self, "subject_region", str(self.subject_region or "").strip())
        object.__setattr__(self, "target_region", str(self.target_region or "").strip())
        object.__setattr__(self, "relation", _relation(self.relation))
        if not isinstance(self.source, AssemblyJointSource):
            object.__setattr__(self, "source", AssemblyJointSource(str(self.source)))
        object.__setattr__(self, "edge", str(self.edge or "").strip().upper())
        object.__setattr__(self, "direction", str(self.direction or "AUTO").strip())
        object.__setattr__(self, "clearance_intent", str(self.clearance_intent or "ZERO").strip())
        object.__setattr__(self, "revision", int(self.revision or 1))
        object.__setattr__(self, "migration_origin", str(self.migration_origin or "").strip())
        if not self.joint_id:
            raise ValueError("joint_id must not be empty")
        if not self.subject_part or not self.target_part:
            raise ValueError("subject_part and target_part must not be empty")
        if self.subject_part == self.target_part:
            raise ValueError("subject_part and target_part must be different")

    @property
    def semantics(self) -> JointSemantics:
        return joint_semantics(self.relation)

    def to_dict(self) -> dict[str, object]:
        return {
            "joint_id": self.joint_id,
            "subject_part": self.subject_part,
            "target_part": self.target_part,
            "subject_region": self.subject_region,
            "target_region": self.target_region,
            "relation": self.relation.value,
            "contact_mode": self.contact_mode,
            "preserve_side": self.preserve_side,
            "relief_intent": self.relief_intent,
            "clearance_policy": self.clearance_policy,
            "solver_constraints": dict(self.solver_constraints),
            "source": self.source.value,
            "edge": self.edge,
            "direction": self.direction,
            "clearance_intent": self.clearance_intent,
            "revision": self.revision,
            "migration_origin": self.migration_origin,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "AssemblyJoint":
        return cls(
            joint_id=raw.get("joint_id", ""),
            subject_part=raw.get("subject_part", ""),
            target_part=raw.get("target_part", ""),
            subject_region=raw.get("subject_region", ""),
            target_region=raw.get("target_region", ""),
            relation=raw.get("relation", AssemblyJointRelation.INSERT.value),
            contact_mode=str(raw.get("contact_mode", "AUTO") or "AUTO"),
            preserve_side=str(raw.get("preserve_side", "AUTO") or "AUTO"),
            relief_intent=str(raw.get("relief_intent", "AUTO") or "AUTO"),
            clearance_policy=str(raw.get("clearance_policy", "ZERO") or "ZERO"),
            solver_constraints=dict(raw.get("solver_constraints", {}) or {}),
            source=raw.get("source", AssemblyJointSource.INTENT_DERIVED.value),
            edge=str(raw.get("edge", "") or ""),
            direction=str(raw.get("direction", "AUTO") or "AUTO"),
            clearance_intent=str(raw.get("clearance_intent", raw.get("clearance_policy", "ZERO")) or "ZERO"),
            revision=int(raw.get("revision", 1) or 1),
            migration_origin=str(raw.get("migration_origin", "") or ""),
        )


def resolve_endcap_intent_joints(
    intent,
    *,
    endcap_part: str,
    target_parts: Iterable[str],
    existing_joints: Iterable[AssemblyJoint] = (),
) -> tuple[AssemblyJoint, ...]:
    """Resolve one high-level EndCap intent to side joints.

    Only prior ``INTENT_DERIVED`` joints for this EndCap are replaced.  User
    added WRAP (or any other explicit relation) survives intent switching.
    """
    relation = _relation(intent)
    if relation is AssemblyJointRelation.WRAP:
        raise ValueError("WRAP is an AssemblyJoint relation, not an EndCap Assembly Intent")
    subject = str(endcap_part)
    kept = [
        j for j in tuple(existing_joints or ())
        if not (j.subject_part == subject and j.source is AssemblyJointSource.INTENT_DERIVED)
    ]
    derived = []
    for target in tuple(target_parts or ()):
        target = str(target)
        derived.append(AssemblyJoint(
            joint_id=f"{subject}:{target}:{relation.value}:intent",
            subject_part=subject,
            target_part=target,
            subject_region=f"side:{target}",
            target_region="mating_zone",
            relation=relation,
            contact_mode="AUTO",
            preserve_side="AUTO",
            relief_intent="AUTO",
            source=AssemblyJointSource.INTENT_DERIVED,
        ))
    return tuple(kept + derived)


@dataclass(frozen=True)
class CornerJointSignature:
    """Canonical, order-independent joint signature for one physical corner."""

    part: str
    region: str
    entries: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.part}@{self.region}|" + "||".join(self.entries)

    def to_dict(self) -> dict[str, object]:
        return {"part": self.part, "region": self.region, "entries": list(self.entries), "key": self.key}


def corner_joint_signature(graph: "ResolvedAssemblyGraph", part: str, region: str) -> CornerJointSignature:
    part = str(part)
    region = str(region)
    entries = []
    for joint in graph.nearby_joints(part, region):
        entries.append(
            f"{joint.relation.value}:{joint.subject_part}>{joint.target_part}:"
            f"{joint.subject_region}>{joint.target_region}"
        )
    return CornerJointSignature(part=part, region=region, entries=tuple(sorted(entries)))


def _joint_region_matches_corner(joint_region: str, corner_region: str) -> bool:
    """Return whether a Joint region participates in a physical corner.

    Intent-derived and migrated joints historically describe a whole side
    (``left_side``, ``side:left_side`` or ``left_mating_zone``), while corner
    rules query concrete regions such as ``top_left``.  A whole-side relation
    therefore participates in both corners on that side.  Explicit corner
    regions remain exact and never leak across the opposite top/bottom corner.
    """
    stored = str(joint_region or "").strip().lower()
    corner = str(corner_region or "").strip().lower()
    if not stored:
        return True
    if stored == corner:
        return True

    def side_token(value: str) -> str | None:
        if "left" in value:
            return "left"
        if "right" in value:
            return "right"
        return None

    stored_side = side_token(stored)
    corner_side = side_token(corner)
    if stored_side is None or corner_side is None or stored_side != corner_side:
        return False

    # Explicit physical corner names are exact: top_left must not match
    # bottom_left.  Generic side/mating labels intentionally cover both.
    explicit_corner = ("top" in stored or "bottom" in stored) and not (
        "mating_zone" in stored or stored.endswith("_side") or stored.startswith("side:")
    )
    if explicit_corner:
        return ("top" in stored) == ("top" in corner) and ("bottom" in stored) == ("bottom" in corner)
    return True


def _joint_edge_matches_corner(edge: str, corner_region: str) -> bool:
    edge = str(edge or "").upper()
    corner = str(corner_region or "").lower()
    if not edge:
        return False
    if edge == "TOP":
        return "top" in corner
    if edge == "BOTTOM":
        return "bottom" in corner
    if edge == "LEFT":
        return "left" in corner
    if edge == "RIGHT":
        return "right" in corner
    return False


@dataclass(frozen=True)
class ResolvedAssemblyGraph:
    parts: tuple[str, ...]
    joints: tuple[AssemblyJoint, ...]

    def __post_init__(self):
        parts = tuple(str(p) for p in self.parts)
        joints = tuple(self.joints)
        object.__setattr__(self, "parts", parts)
        object.__setattr__(self, "joints", joints)
        part_set = set(parts)
        ids: set[str] = set()
        pair_regions: dict[tuple[str, str, str, str], AssemblyJointRelation] = {}
        for joint in joints:
            if joint.joint_id in ids:
                raise ValueError(f"duplicate joint_id: {joint.joint_id}")
            ids.add(joint.joint_id)
            if joint.subject_part not in part_set or joint.target_part not in part_set:
                raise ValueError(f"joint targets missing part: {joint.joint_id}")
            key = (joint.subject_part, joint.target_part, joint.subject_region, joint.target_region)
            prior = pair_regions.get(key)
            if prior is not None and prior is not joint.relation:
                raise ValueError(
                    f"conflicting joint for {joint.subject_part}->{joint.target_part} "
                    f"{joint.subject_region}/{joint.target_region}: {prior.value} vs {joint.relation.value}"
                )
            pair_regions[key] = joint.relation

    def nearby_joints(self, part: str, region: str | None = None) -> tuple[AssemblyJoint, ...]:
        part = str(part)
        region = None if region is None else str(region)
        result = []
        for joint in self.joints:
            if joint.subject_part != part and joint.target_part != part:
                continue
            if region is not None:
                if joint.edge:
                    if not _joint_edge_matches_corner(joint.edge, region):
                        continue
                else:
                    if joint.subject_part == part and not _joint_region_matches_corner(joint.subject_region, region):
                        continue
                    if joint.target_part == part and not _joint_region_matches_corner(joint.target_region, region):
                        continue
            result.append(joint)
        return tuple(result)

    def to_dict(self) -> dict[str, object]:
        return {
            "parts": list(self.parts),
            "joints": [joint.to_dict() for joint in self.joints],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ResolvedAssemblyGraph":
        return cls(
            parts=tuple(raw.get("parts", ()) or ()),
            joints=tuple(AssemblyJoint.from_dict(j) for j in tuple(raw.get("joints", ()) or ())),
        )

ASSEMBLY_JOINT_SCHEMA_VERSION = 2


def serialize_joint_graph(parts, joints) -> dict[str, object]:
    graph = ResolvedAssemblyGraph(tuple(parts or ()), tuple(joints or ()))
    return {
        "assembly_joint_schema_version": ASSEMBLY_JOINT_SCHEMA_VERSION,
        "parts": list(graph.parts),
        "joints": [joint.to_dict() for joint in graph.joints],
    }


def deserialize_joint_graph(payload: Mapping[str, object]) -> ResolvedAssemblyGraph:
    version = int(payload.get("assembly_joint_schema_version", 0) or 0)
    if version not in (1, ASSEMBLY_JOINT_SCHEMA_VERSION):
        raise ValueError(f"unsupported assembly joint schema version: {version}")
    return ResolvedAssemblyGraph(
        parts=tuple(payload.get("parts", ()) or ()),
        joints=tuple(AssemblyJoint.from_dict(j) for j in tuple(payload.get("joints", ()) or ())),
    )


def _legacy_intent_id(snapshot: Mapping[str, object]) -> str:
    from .assembly_intent import normalize_assembly_intent_id
    raw = snapshot.get("assembly_type") or "INSERT_OVERLAY"
    return normalize_assembly_intent_id(raw)


def _edge_from_regions(joint: AssemblyJoint) -> str:
    if joint.edge:
        return joint.edge
    text = f"{joint.subject_region} {joint.target_region}".lower()
    if "top" in text:
        return "TOP"
    if "bottom" in text:
        return "BOTTOM"
    if "left" in text:
        return "LEFT"
    if "right" in text:
        return "RIGHT"
    return ""


def _edge_regions(edge: str) -> tuple[str, str]:
    e = str(edge).upper()
    token = e.lower()
    return f"{token}_edge", f"{token}_mating_zone"


def _default_joint(*, endcap: str, edge: str, relation, source: AssemblyJointSource, origin: str) -> AssemblyJoint:
    subject_region, target_region = _edge_regions(edge)
    relation = _relation(relation)
    return AssemblyJoint(
        joint_id=f"{endcap}:box_body:{edge.lower()}:{relation.value}:{source.value.lower()}",
        subject_part=endcap,
        target_part="box_body",
        subject_region=subject_region,
        target_region=target_region,
        relation=relation,
        source=source,
        edge=edge,
        revision=1,
        migration_origin=origin,
    )


def _preset_map(intent):
    from .assembly_intent import get_assembly_intent
    return get_assembly_intent(intent).default_joint_map


def _canonical_endcap_edge(joint: AssemblyJoint) -> tuple[str, str] | None:
    edge = str(joint.edge or _edge_from_regions(joint) or "").upper()
    if (
        joint.subject_part in {"head", "tail"}
        and joint.target_part == "box_body"
        and edge in {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    ):
        return joint.subject_part, edge
    return None


def _sanitize_intent_edge_joints(intent, *, parts, existing_joints, reset=False):
    """Canonicalize Head/Tail four-edge rows against the Assembly Intent registry.

    Active preset selection resets all four canonical edges.  During reload, legal
    editable overrides survive, while illegal v2 payloads are replaced by registry
    defaults.  Explicit legacy lower-WRAP migration is grandfathered because it is
    authoritative mechanical state from older projects and is handled again by T10.
    """
    from .assembly_intent import get_assembly_intent
    record = get_assembly_intent(intent)
    parts = tuple(str(p) for p in parts)
    passthrough: list[AssemblyJoint] = []
    selected: dict[tuple[str, str], AssemblyJoint] = {}

    def priority(joint: AssemblyJoint) -> int:
        if joint.source is AssemblyJointSource.USER_ADDED:
            return 30
        if joint.source is AssemblyJointSource.SOLVER_CONFIRMED:
            return 25
        if joint.source is AssemblyJointSource.FAMILY_GEOMETRY:
            return 20
        if joint.source is AssemblyJointSource.LEGACY_MIGRATED:
            return 15
        return 10

    for joint in tuple(existing_joints or ()):
        canonical = _canonical_endcap_edge(joint)
        if canonical is None:
            passthrough.append(joint)
            continue
        if reset:
            continue
        part, edge = canonical
        policy = record.edge_policy(edge)
        origin = str(joint.migration_origin or "").upper()
        grandfathered_legacy_wrap = (
            joint.relation is AssemblyJointRelation.WRAP
            and (
                (
                    joint.source is AssemblyJointSource.LEGACY_MIGRATED
                    and origin == "ENDCAP_BOTTOM_WRAP"
                    and edge == "BOTTOM"
                )
                or origin == "EXPLICIT_LEGACY_EDGE"
            )
        )
        if joint.relation not in policy.allowed_relations and not grandfathered_legacy_wrap:
            continue
        normalized = joint if joint.edge == edge else AssemblyJoint.from_dict({**joint.to_dict(), "edge": edge})
        key = (part, edge)
        current = selected.get(key)
        if current is None or priority(normalized) > priority(current):
            selected[key] = normalized

    if reset:
        # A user-selected preset is authoritative: discard every canonical edge
        # override and regenerate the four registry defaults.  Non-EndCap joints
        # remain untouched.
        return apply_preset_defaults(record.stable_id, parts=parts, existing_joints=passthrough)

    # Reload/migration must be idempotent.  Keep the exact provenance/revision of
    # every legal canonical row and synthesize only edges that are genuinely
    # missing.  Calling apply_preset_defaults here would deliberately discard
    # LEGACY_MIGRATED / INTENT_DERIVED defaults and recreate them with different
    # metadata, making a second load mutate an otherwise identical project.
    kept = list(passthrough)
    kept.extend(selected.values())
    occupied = set(selected)
    for endcap in ("head", "tail"):
        if endcap not in parts or "box_body" not in parts:
            continue
        for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            if (endcap, edge) in occupied:
                continue
            kept.append(_default_joint(
                endcap=endcap,
                edge=edge,
                relation=record.edge_policy(edge).default_relation,
                source=AssemblyJointSource.INTENT_DERIVED,
                origin="ASSEMBLY_INTENT",
            ))
    return tuple(kept)


def _parts_from_snapshot(snapshot: Mapping[str, object]) -> tuple[str, ...]:
    parts = tuple(str(v) for v in tuple(snapshot.get("existing_parts", ()) or ()))
    if not parts:
        parts = ("box_body", "head", "tail")
    return parts


def apply_preset_defaults(
    intent,
    *,
    parts: Iterable[str],
    existing_joints: Iterable[AssemblyJoint] = (),
) -> tuple[AssemblyJoint, ...]:
    """Apply only intent-derived defaults; explicit/family/solver joints win per edge."""
    defaults = _preset_map(intent)
    parts = tuple(str(p) for p in parts)
    current = tuple(existing_joints or ())
    kept: list[AssemblyJoint] = []
    occupied: set[tuple[str, str]] = set()
    for joint in current:
        edge = _edge_from_regions(joint)
        inferred_legacy = (
            joint.source is AssemblyJointSource.LEGACY_MIGRATED
            and str(joint.migration_origin or "").upper() == "ASSEMBLY_TYPE"
        )
        if joint.source is AssemblyJointSource.INTENT_DERIVED or inferred_legacy:
            continue
        normalized = joint if joint.edge == edge else AssemblyJoint.from_dict({**joint.to_dict(), "edge": edge})
        kept.append(normalized)
        if normalized.subject_part in {"head", "tail"} and edge:
            occupied.add((normalized.subject_part, edge))
    for endcap in ("head", "tail"):
        if endcap not in parts or "box_body" not in parts:
            continue
        for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            if (endcap, edge) in occupied:
                continue
            kept.append(_default_joint(
                endcap=endcap, edge=edge, relation=defaults[edge],
                source=AssemblyJointSource.INTENT_DERIVED, origin="ASSEMBLY_INTENT",
            ))
    return tuple(kept)


def resolve_actual_graph(parts: Iterable[str], joints: Iterable[AssemblyJoint]) -> ResolvedAssemblyGraph:
    return ResolvedAssemblyGraph(tuple(parts or ()), tuple(joints or ()))


def _upgrade_existing_rows(result: Mapping[str, object], version: int) -> tuple[AssemblyJoint, ...]:
    rows = tuple(result.get("assembly_joints", ()) or result.get("joints", ()) or ())
    parsed = [raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw) for raw in rows]
    upgraded: list[AssemblyJoint] = []
    for joint in parsed:
        edge = _edge_from_regions(joint)
        raw = joint.to_dict()
        raw["edge"] = edge
        # Schema-1 intent/legacy side rows encoded the *whole preset relation*.
        # They are inferred defaults, so drop them and re-expand from the registry.
        if version <= 1 and joint.source in {AssemblyJointSource.INTENT_DERIVED, AssemblyJointSource.LEGACY_MIGRATED}:
            continue
        if version <= 1 and joint.source is AssemblyJointSource.USER_ADDED:
            raw["migration_origin"] = raw.get("migration_origin") or "EXPLICIT_LEGACY_EDGE"
        upgraded.append(AssemblyJoint.from_dict(raw))
    return tuple(upgraded)


def migrate_legacy_snapshot_joints(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Migrate missing/incomplete legacy graph exactly once to schema v2.

    Explicit old/user joints survive.  Missing defaults are expanded from the
    persisted Assembly Intent.  No WRAP is invented unless the persisted intent
    explicitly identifies the global 包覆貼外 preset or an explicit joint says so.
    """
    result = dict(snapshot or {})
    version = int(result.get("assembly_joint_schema_version", 0) or 0)
    if version == ASSEMBLY_JOINT_SCHEMA_VERSION:
        declared = tuple(str(v) for v in tuple(result.get("existing_parts", ()) or ()))
        if not declared:
            workspace = result.get("workspace")
            if isinstance(workspace, Mapping):
                declared = tuple(str(v) for v in tuple(workspace.get("existing_parts", ()) or ()))
        parts = declared or _parts_from_snapshot(result)
        part_set = set(parts)
        parsed = []
        for raw in tuple(result.get("assembly_joints", ()) or ()):
            joint = raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
            if part_set and (joint.subject_part not in part_set or joint.target_part not in part_set):
                continue
            parsed.append(joint)
        sanitized = _sanitize_intent_edge_joints(
            _legacy_intent_id(result), parts=parts, existing_joints=parsed, reset=False
        )
        result["assembly_joints"] = [joint.to_dict() for joint in sanitized]
        return result
    if version > ASSEMBLY_JOINT_SCHEMA_VERSION:
        raise ValueError(f"unsupported assembly joint schema version: {version}")
    parts = _parts_from_snapshot(result)
    current = _upgrade_existing_rows(result, version)
    intent = _legacy_intent_id(result)
    completed = apply_preset_defaults(intent, parts=parts, existing_joints=current)
    # migration defaults are provenance, not live intent-derived state
    migrated = []
    for joint in completed:
        if joint.source is AssemblyJointSource.INTENT_DERIVED:
            raw = joint.to_dict()
            raw["source"] = AssemblyJointSource.LEGACY_MIGRATED.value
            raw["migration_origin"] = "ASSEMBLY_TYPE"
            migrated.append(AssemblyJoint.from_dict(raw))
        else:
            migrated.append(joint)
    # Explicit legacy Receiving lower-WRAP persistence is migrated once into
    # the canonical BOTTOM Joint.  Absence of this field must never invent a
    # WRAP relation for old files.
    legacy_wrap = result.get("endcap_bottom_wrap")
    if isinstance(legacy_wrap, Mapping):
        rewritten = []
        for joint in migrated:
            edge = str(joint.edge or _edge_from_regions(joint) or "").upper()
            item = legacy_wrap.get(joint.subject_part) if joint.subject_part in {"head", "tail"} else None
            if edge == "BOTTOM" and isinstance(item, Mapping) and bool(item.get("enabled", False)):
                raw = joint.to_dict()
                raw.update({
                    "relation": AssemblyJointRelation.WRAP.value,
                    "source": AssemblyJointSource.LEGACY_MIGRATED.value,
                    "migration_origin": "ENDCAP_BOTTOM_WRAP",
                    "edge": "BOTTOM",
                })
                rewritten.append(AssemblyJoint.from_dict(raw))
            else:
                rewritten.append(joint)
        migrated = rewritten
    result["assembly_joint_schema_version"] = ASSEMBLY_JOINT_SCHEMA_VERSION
    result["assembly_joints"] = [joint.to_dict() for joint in migrated]
    return result


def sync_snapshot_intent_joints(snapshot: Mapping[str, object], intent) -> dict[str, object]:
    """Update intent mirror and only intent-derived/default joints."""
    from .assembly_intent import normalize_assembly_intent_id
    result = migrate_legacy_snapshot_joints(snapshot)
    parts = _parts_from_snapshot(result)
    current = tuple(AssemblyJoint.from_dict(raw) for raw in tuple(result.get("assembly_joints", ()) or ()))
    updated = _sanitize_intent_edge_joints(
        intent, parts=parts, existing_joints=current, reset=True
    )
    intent_id = normalize_assembly_intent_id(intent)
    result["assembly_joint_schema_version"] = ASSEMBLY_JOINT_SCHEMA_VERSION
    result["assembly_joints"] = [j.to_dict() for j in updated]
    result["assembly_type"] = intent_id
    return result


def edge_relation_for_part(snapshot: Mapping[str, object], part: str, edge: str):
    """Project one explicit EndCap edge relation from the resolved graph."""
    state = migrate_legacy_snapshot_joints(snapshot)
    part = str(part)
    edge = str(edge).upper()
    for raw in tuple(state.get("assembly_joints", ()) or ()):
        joint = raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        if joint.subject_part == part and str(joint.edge or _edge_from_regions(joint) or "").upper() == edge:
            return joint.relation
    return None


def set_part_edge_relation(
    snapshot: Mapping[str, object],
    part: str,
    edge: str,
    relation,
    *,
    source: AssemblyJointSource = AssemblyJointSource.USER_ADDED,
) -> dict[str, object]:
    """Edit exactly one resolved EndCap edge without reapplying the preset.

    This is the graph editor seam used by Receiving BOTTOM WRAP controls and
    future arbitrary edge UI.  Other edges and the opposite EndCap are copied
    byte-for-byte at the joint-record level.
    """
    state = migrate_legacy_snapshot_joints(snapshot)
    part = str(part)
    edge = str(edge).upper()
    relation = _relation(relation)
    if part not in {"head", "tail"}:
        raise ValueError(f"unsupported EndCap part: {part}")
    from .assembly_intent import get_assembly_intent
    intent = get_assembly_intent(_legacy_intent_id(state))
    try:
        policy = intent.edge_policy(edge)
    except KeyError as exc:
        raise ValueError(f"unsupported EndCap edge: {edge}") from exc
    if relation not in policy.allowed_relations:
        allowed = ", ".join(item.value for item in policy.allowed_relations)
        raise ValueError(
            f"relation {relation.value} not allowed for {intent.stable_id} {edge}; allowed: {allowed}"
        )
    rows = []
    replaced = False
    for raw in tuple(state.get("assembly_joints", ()) or ()):
        joint = raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        joint_edge = str(joint.edge or _edge_from_regions(joint) or "").upper()
        if joint.subject_part == part and joint_edge == edge:
            data = joint.to_dict()
            data.update({
                "relation": relation.value,
                "source": source.value,
                "edge": edge,
                "revision": max(1, int(getattr(joint, "revision", 1) or 1) + 1),
                "migration_origin": "USER_EDGE_OVERRIDE",
            })
            rows.append(AssemblyJoint.from_dict(data).to_dict())
            replaced = True
        else:
            rows.append(joint.to_dict())
    if not replaced:
        rows.append(_default_joint(
            endcap=part,
            edge=edge,
            relation=relation,
            source=source,
            origin="USER_EDGE_OVERRIDE",
        ).to_dict())
    result = dict(state)
    result["assembly_joint_schema_version"] = ASSEMBLY_JOINT_SCHEMA_VERSION
    result["assembly_joints"] = rows
    return result


def _mechanical_region_name(value: object) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "left_side": "left_edge", "left_edge": "left_edge",
        "right_side": "right_edge", "right_edge": "right_edge",
        "top_side": "top_edge", "top_edge": "top_edge",
        "bottom_side": "bottom_edge", "bottom_edge": "bottom_edge",
    }
    return aliases.get(raw, raw)


def _stable_mechanical_value(value):
    if isinstance(value, Mapping):
        return {str(k): _stable_mechanical_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_stable_mechanical_value(v) for v in value]
    return getattr(value, "value", value)


def resolved_joint_graph_fingerprint(graph_or_snapshot, *, relevant_parts=("box_body", "head", "tail")) -> str:
    """Hash only Joint semantics that can change BoxBody/EndCap mechanics.

    Provenance (joint_id/source/revision/migration_origin) is deliberately
    excluded: loading the same mechanical graph through a legacy migration or
    intent projection must not invalidate a verified relief replay.  Known
    schema-1 region aliases are canonicalized as well.
    """
    import hashlib
    import json

    if isinstance(graph_or_snapshot, ResolvedAssemblyGraph):
        graph = graph_or_snapshot
    elif isinstance(graph_or_snapshot, Mapping):
        state = migrate_legacy_snapshot_joints(graph_or_snapshot)
        parts = _parts_from_snapshot(state)
        graph = ResolvedAssemblyGraph(parts, tuple(AssemblyJoint.from_dict(r) for r in tuple(state.get("assembly_joints", ()) or ())))
    else:
        raise TypeError("graph_or_snapshot must be ResolvedAssemblyGraph or snapshot mapping")

    relevant = {str(v) for v in tuple(relevant_parts or ())}
    rows = []
    for joint in graph.joints:
        if relevant and not (joint.subject_part in relevant and joint.target_part in relevant):
            continue
        rows.append({
            "subject_part": str(joint.subject_part),
            "target_part": str(joint.target_part),
            "subject_region": _mechanical_region_name(joint.subject_region),
            "target_region": _mechanical_region_name(joint.target_region),
            "edge": str(joint.edge or _edge_from_regions(joint) or "").upper(),
            "direction": str(getattr(joint, "direction", "") or "").upper(),
            "relation": joint.relation.value,
            "contact_mode": getattr(joint.contact_mode, "value", joint.contact_mode),
            "preserve_side": getattr(joint.preserve_side, "value", joint.preserve_side),
            "clearance_intent": str(getattr(joint, "clearance_intent", "") or ""),
            "clearance_policy": getattr(joint.clearance_policy, "value", joint.clearance_policy),
            "relief_intent": getattr(joint.relief_intent, "value", joint.relief_intent),
            "solver_constraints": _stable_mechanical_value(dict(joint.solver_constraints or {})),
        })
    rows.sort(key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
