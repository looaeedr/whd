# -*- coding: utf-8 -*-
"""Receiving manufacturing readiness and export-scope authority.

This module derives READY/BLOCKED state from canonical Receiving layout plus
intrinsic manufacturing failures. Persisted topology remains owned by
``ae_engine.receiving_layout``; UI code may only project the immutable result.

Propagation contract (Receiving V1.6 R-028):
- JOINT_INTRINSIC blocks the Joint, both participant Bay packages, and its Set.
- BAY_INTRINSIC blocks only the named Bay package and its Set.
- NOT_EXPORTABLE is derived status/diagnostic evidence and never becomes a new
  intrinsic cause, so it cannot chain into adjacent Bays/Joints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .receiving_layout import normalize_receiving_layout

READY = "READY"
BLOCKED = "BLOCKED"
JOINT_INTRINSIC = "JOINT_INTRINSIC"
BAY_INTRINSIC = "BAY_INTRINSIC"
NOT_EXPORTABLE = "NOT_EXPORTABLE"
_ALLOWED_CLASSIFICATIONS = frozenset({JOINT_INTRINSIC, BAY_INTRINSIC, NOT_EXPORTABLE})


@dataclass(frozen=True)
class ReceivingManufacturingFailure:
    classification: str
    entity_id: str
    code: str
    reason: str
    physical_piece_ids: tuple[str, ...] = ()
    feature_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        classification = str(self.classification or "").strip().upper()
        if classification not in _ALLOWED_CLASSIFICATIONS:
            raise ValueError(f"unsupported Receiving failure classification: {self.classification!r}")
        entity_id = str(self.entity_id or "").strip()
        if not entity_id:
            raise ValueError("Receiving manufacturing failure entity_id must not be empty")
        code = str(self.code or "").strip()
        if not code:
            raise ValueError("Receiving manufacturing failure code must not be empty")
        reason = str(self.reason or "").strip()
        if not reason:
            raise ValueError("Receiving manufacturing failure reason must not be empty")
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self, "physical_piece_ids",
            tuple(str(value) for value in tuple(self.physical_piece_ids or ()) if str(value)),
        )
        object.__setattr__(
            self, "feature_ids",
            tuple(str(value) for value in tuple(self.feature_ids or ()) if str(value)),
        )


@dataclass(frozen=True)
class ReceivingReadinessNode:
    entity_kind: str
    stable_id: str
    state: str
    diagnostics: tuple[ReceivingManufacturingFailure, ...] = ()

    @property
    def ready(self) -> bool:
        return self.state == READY


@dataclass(frozen=True)
class ReceivingManufacturingReadiness:
    sets: Mapping[str, ReceivingReadinessNode]
    bays: Mapping[str, ReceivingReadinessNode]
    joints: Mapping[str, ReceivingReadinessNode]
    bay_to_set: Mapping[str, str]
    joint_to_set: Mapping[str, str]

    def node(self, entity_kind: str, stable_id: str) -> ReceivingReadinessNode:
        kind = str(entity_kind or "").strip().upper()
        key = str(stable_id or "").strip()
        table = {"SET": self.sets, "BAY": self.bays, "JOINT": self.joints}.get(kind)
        if table is None:
            raise ValueError(f"unsupported Receiving readiness entity kind: {entity_kind!r}")
        try:
            return table[key]
        except KeyError as exc:
            raise KeyError(f"unknown Receiving {kind} stable_id: {key}") from exc


class ReceivingExportBlocked(ValueError):
    def __init__(self, *, scope_kind: str, stable_id: str | None, blocked_nodes: Iterable[ReceivingReadinessNode]):
        self.scope_kind = str(scope_kind)
        self.stable_id = None if stable_id is None else str(stable_id)
        self.blocked_nodes = tuple(blocked_nodes)
        detail = ", ".join(f"{node.entity_kind}:{node.stable_id}" for node in self.blocked_nodes)
        super().__init__(f"Receiving export scope is BLOCKED: {self.scope_kind}:{self.stable_id or '*'} -> {detail}")


def _failure_tuple(values: Iterable[ReceivingManufacturingFailure]) -> tuple[ReceivingManufacturingFailure, ...]:
    return tuple(sorted(values, key=lambda item: (item.classification, item.entity_id, item.code, item.reason)))


def evaluate_receiving_manufacturing_readiness(
    layout: Mapping[str, object],
    failures: Iterable[ReceivingManufacturingFailure] = (),
) -> ReceivingManufacturingReadiness:
    """Derive bounded Set/Bay/Joint readiness without mutating layout authority."""
    normalized = normalize_receiving_layout(layout)
    set_rows = {str(row["stable_id"]): row for row in normalized["sets"]}
    bay_rows: dict[str, Mapping[str, object]] = {}
    joint_rows: dict[str, Mapping[str, object]] = {}
    bay_to_set: dict[str, str] = {}
    joint_to_set: dict[str, str] = {}
    for set_id, row in set_rows.items():
        for bay in row["bays"]:
            bay_id = str(bay["stable_id"])
            bay_rows[bay_id] = bay
            bay_to_set[bay_id] = set_id
        for joint in row["joints"]:
            joint_id = str(joint["stable_id"])
            joint_rows[joint_id] = joint
            joint_to_set[joint_id] = set_id

    bay_causes: dict[str, list[ReceivingManufacturingFailure]] = {key: [] for key in bay_rows}
    joint_causes: dict[str, list[ReceivingManufacturingFailure]] = {key: [] for key in joint_rows}
    set_causes: dict[str, list[ReceivingManufacturingFailure]] = {key: [] for key in set_rows}

    for failure in tuple(failures or ()):
        if not isinstance(failure, ReceivingManufacturingFailure):
            raise TypeError("failures must contain ReceivingManufacturingFailure values")
        # NOT_EXPORTABLE is a derived projection and is deliberately not an
        # intrinsic cause. Ignoring it here prevents accidental chain propagation.
        if failure.classification == NOT_EXPORTABLE:
            continue
        if failure.classification == BAY_INTRINSIC:
            if failure.entity_id not in bay_rows:
                raise KeyError(f"unknown Receiving Bay failure entity: {failure.entity_id}")
            bay_causes[failure.entity_id].append(failure)
            set_causes[bay_to_set[failure.entity_id]].append(failure)
            continue
        if failure.classification == JOINT_INTRINSIC:
            if failure.entity_id not in joint_rows:
                raise KeyError(f"unknown Receiving Joint failure entity: {failure.entity_id}")
            joint_causes[failure.entity_id].append(failure)
            set_id = joint_to_set[failure.entity_id]
            joint = joint_rows[failure.entity_id]
            left_id = str(joint["left_bay_id"])
            right_id = str(joint["right_bay_id"])
            bay_causes[left_id].append(failure)
            bay_causes[right_id].append(failure)
            set_causes[set_id].append(failure)
            continue
        raise AssertionError(f"unhandled failure classification: {failure.classification}")

    bays = {
        key: ReceivingReadinessNode("BAY", key, BLOCKED if causes else READY, _failure_tuple(causes))
        for key, causes in bay_causes.items()
    }
    joints = {
        key: ReceivingReadinessNode("JOINT", key, BLOCKED if causes else READY, _failure_tuple(causes))
        for key, causes in joint_causes.items()
    }
    sets = {
        key: ReceivingReadinessNode("SET", key, BLOCKED if causes else READY, _failure_tuple(causes))
        for key, causes in set_causes.items()
    }
    return ReceivingManufacturingReadiness(
        sets=sets,
        bays=bays,
        joints=joints,
        bay_to_set=bay_to_set,
        joint_to_set=joint_to_set,
    )


def receiving_readiness_projection(report: ReceivingManufacturingReadiness) -> tuple[dict[str, object], ...]:
    """Return UI-safe READY/BLOCKED rows; this projection never owns validity."""
    if not isinstance(report, ReceivingManufacturingReadiness):
        raise TypeError("report must be ReceivingManufacturingReadiness")
    rows: list[dict[str, object]] = []
    for kind, table in (("SET", report.sets), ("BAY", report.bays), ("JOINT", report.joints)):
        for stable_id in sorted(table):
            node = table[stable_id]
            rows.append({
                "entity_kind": kind,
                "stable_id": stable_id,
                "state": node.state,
                "diagnostics": tuple({
                    "classification": item.classification,
                    "code": item.code,
                    "reason": item.reason,
                    "physical_piece_ids": item.physical_piece_ids,
                    "feature_ids": item.feature_ids,
                } for item in node.diagnostics),
            })
    return tuple(rows)


def assert_receiving_export_scope_ready(
    report: ReceivingManufacturingReadiness,
    *,
    scope_kind: str,
    stable_id: str | None = None,
) -> None:
    """Fail closed before any DXF write if the requested dependency closure is blocked."""
    if not isinstance(report, ReceivingManufacturingReadiness):
        raise TypeError("report must be ReceivingManufacturingReadiness")
    kind = str(scope_kind or "").strip().upper()
    blocked: list[ReceivingReadinessNode] = []
    if kind == "PROJECT":
        blocked.extend(node for node in report.sets.values() if not node.ready)
    elif kind == "SET":
        if not stable_id:
            raise ValueError("SET export scope requires stable_id")
        set_node = report.node("SET", stable_id)
        if not set_node.ready:
            blocked.append(set_node)
    elif kind == "BAY":
        if not stable_id:
            raise ValueError("BAY export scope requires stable_id")
        bay_node = report.node("BAY", stable_id)
        if not bay_node.ready:
            blocked.append(bay_node)
    else:
        raise ValueError(f"unsupported Receiving export scope: {scope_kind!r}")
    if blocked:
        raise ReceivingExportBlocked(scope_kind=kind, stable_id=stable_id, blocked_nodes=blocked)
