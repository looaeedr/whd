# -*- coding: utf-8 -*-
"""Canonical high-level Assembly Intent registry.

Assembly Intents are operator presets only.  They expand to four explicit
AssemblyJoint edge defaults; the resolved graph remains the mechanical truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .assembly_joint import AssemblyJointRelation


@dataclass(frozen=True)
class AssemblyIntentEdgePolicy:
    """Canonical policy for one physical Head/Tail edge."""

    default_relation: AssemblyJointRelation
    allowed_relations: tuple[AssemblyJointRelation, ...]
    editable: bool

    def __post_init__(self):
        default = AssemblyJointRelation(self.default_relation)
        allowed = tuple(AssemblyJointRelation(item) for item in self.allowed_relations)
        if not allowed:
            raise ValueError("assembly intent edge policy must allow at least one relation")
        if len(set(allowed)) != len(allowed):
            raise ValueError("assembly intent edge policy must not contain duplicate relations")
        if default not in allowed:
            raise ValueError("assembly intent edge default must be present in allowed relations")
        editable = bool(self.editable)
        if not editable and allowed != (default,):
            raise ValueError("fixed assembly intent edge must allow only its default relation")
        object.__setattr__(self, "default_relation", default)
        object.__setattr__(self, "allowed_relations", allowed)
        object.__setattr__(self, "editable", editable)

    def to_dict(self) -> dict[str, object]:
        return {
            "default_relation": self.default_relation.value,
            "allowed_relations": tuple(item.value for item in self.allowed_relations),
            "editable": self.editable,
        }


@dataclass(frozen=True)
class AssemblyIntentRecord:
    stable_id: str
    display_name: str
    revision: int
    edge_policy_map: Mapping[str, AssemblyIntentEdgePolicy]

    def __post_init__(self):
        object.__setattr__(self, "stable_id", str(self.stable_id).strip())
        object.__setattr__(self, "display_name", str(self.display_name).strip())
        object.__setattr__(self, "revision", int(self.revision))
        normalized = {
            str(k).upper(): (v if isinstance(v, AssemblyIntentEdgePolicy) else AssemblyIntentEdgePolicy(**v))
            for k, v in dict(self.edge_policy_map).items()
        }
        required = {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        if set(normalized) != required:
            raise ValueError(f"assembly intent {self.stable_id} must define exactly {sorted(required)}")
        object.__setattr__(self, "edge_policy_map", MappingProxyType(normalized))

    @property
    def default_joint_map(self) -> Mapping[str, AssemblyJointRelation]:
        """Compatibility projection derived from the canonical edge policies."""
        return MappingProxyType({
            edge: policy.default_relation
            for edge, policy in self.edge_policy_map.items()
        })

    def edge_policy(self, edge: str) -> AssemblyIntentEdgePolicy:
        return self.edge_policy_map[str(edge).strip().upper()]

    def to_dict(self) -> dict[str, object]:
        return {
            "stable_id": self.stable_id,
            "display_name": self.display_name,
            "revision": self.revision,
            "default_joint_map": {k: v.value for k, v in self.default_joint_map.items()},
            "edge_policy_map": {k: v.to_dict() for k, v in self.edge_policy_map.items()},
        }


def _fixed(relation) -> AssemblyIntentEdgePolicy:
    relation = AssemblyJointRelation(relation)
    return AssemblyIntentEdgePolicy(relation, (relation,), False)


def _editable(default, *allowed) -> AssemblyIntentEdgePolicy:
    return AssemblyIntentEdgePolicy(
        AssemblyJointRelation(default),
        tuple(AssemblyJointRelation(item) for item in allowed),
        True,
    )


def _record(stable_id, display_name, **edge_policies):
    return AssemblyIntentRecord(stable_id, display_name, 2, edge_policies)


_INTENTS = (
    _record(
        "INSERT", "嵌入",
        TOP=_fixed("INSERT"), BOTTOM=_fixed("INSERT"),
        LEFT=_fixed("INSERT"), RIGHT=_fixed("INSERT"),
    ),
    _record(
        "OVERLAY", "貼外",
        TOP=_fixed("OVERLAY"),
        BOTTOM=_editable("INSERT", "INSERT", "OVERLAY"),
        LEFT=_fixed("OVERLAY"), RIGHT=_fixed("OVERLAY"),
    ),
    _record(
        "INSERT_OVERLAY", "嵌入貼外",
        TOP=_fixed("OVERLAY"), BOTTOM=_fixed("INSERT"),
        LEFT=_fixed("INSERT"), RIGHT=_fixed("INSERT"),
    ),
    _record(
        "WRAP_OVERLAY", "包覆貼外",
        TOP=_fixed("OVERLAY"), BOTTOM=_fixed("WRAP"),
        LEFT=_editable("INSERT", "INSERT", "OVERLAY", "WRAP"),
        RIGHT=_editable("INSERT", "INSERT", "OVERLAY", "WRAP"),
    ),
)
_BY_ID = {row.stable_id: row for row in _INTENTS}
_ALIASES = {
    "包覆貼外": "WRAP_OVERLAY",
    "外側包覆": "WRAP_OVERLAY",  # legacy import only; never display this label.
}


def registered_assembly_intents() -> tuple[AssemblyIntentRecord, ...]:
    return _INTENTS


def normalize_assembly_intent_id(value) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "").strip()
    text = _ALIASES.get(text, text)
    if text not in _BY_ID:
        raise ValueError(f"unsupported Assembly Intent: {text}")
    return text


def get_assembly_intent(value) -> AssemblyIntentRecord:
    return _BY_ID[normalize_assembly_intent_id(value)]


def assembly_intent_primitive_records() -> tuple[dict[str, object], ...]:
    return tuple(row.to_dict() for row in _INTENTS)
