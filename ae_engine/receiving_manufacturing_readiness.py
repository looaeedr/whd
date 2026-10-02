# -*- coding: utf-8 -*-
"""Receiving manufacturing readiness, dependency closure, and instance export.

This is the single R-028 authority for Set/Bay/Joint READY/BLOCKED projection.
Intrinsic failures enter once. Derived NOT_EXPORTABLE state is never recycled
as a new intrinsic failure, which prevents chain propagation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import tempfile
from typing import Callable, Iterable, Mapping

from .receiving_layout import normalize_receiving_layout


READY = "READY"
BLOCKED = "BLOCKED"
JOINT_INTRINSIC = "JOINT_INTRINSIC"
BAY_INTRINSIC = "BAY_INTRINSIC"


@dataclass(frozen=True)
class ReceivingIntrinsicFailure:
    scope: str
    set_id: str
    reason: str
    bay_id: str = ""
    joint_id: str = ""
    physical_piece: str = ""
    conflicting_feature_ids: tuple[str, ...] = ()
    diagnostic_code: str = ""

    def __post_init__(self):
        scope = str(self.scope).strip().upper()
        if scope not in {JOINT_INTRINSIC, BAY_INTRINSIC}:
            raise ValueError(f"unsupported Receiving intrinsic scope: {self.scope!r}")
        object.__setattr__(self, "scope", scope)
        object.__setattr__(
            self, "conflicting_feature_ids",
            tuple(str(value) for value in tuple(self.conflicting_feature_ids or ()))
        )
        if scope == JOINT_INTRINSIC and not str(self.joint_id).strip():
            raise ValueError("Joint-intrinsic failure requires joint_id")
        if scope == BAY_INTRINSIC and not str(self.bay_id).strip():
            raise ValueError("Bay-intrinsic failure requires bay_id")


@dataclass(frozen=True)
class ReceivingReadinessRow:
    entity_type: str
    entity_id: str
    set_id: str
    status: str
    blocker_codes: tuple[str, ...] = ()
    diagnostics: tuple[ReceivingIntrinsicFailure, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == READY


@dataclass(frozen=True)
class ReceivingReadinessGraph:
    sets: Mapping[str, ReceivingReadinessRow]
    bays: Mapping[str, ReceivingReadinessRow]
    joints: Mapping[str, ReceivingReadinessRow]
    set_bay_ids: Mapping[str, tuple[str, ...]]
    set_joint_ids: Mapping[str, tuple[str, ...]]
    bay_joint_ids: Mapping[str, tuple[str, ...]]

    def row(self, entity_type: str, entity_id: str) -> ReceivingReadinessRow:
        table = {
            "SET": self.sets, "BAY": self.bays, "JOINT": self.joints
        }.get(str(entity_type).strip().upper())
        if table is None:
            raise ValueError(f"unsupported entity_type: {entity_type!r}")
        return table[str(entity_id)]


@dataclass(frozen=True)
class ReceivingExportDecision:
    status: str
    requested_bay_ids: tuple[str, ...]
    dependency_entity_ids: tuple[str, ...]
    blockers: tuple[ReceivingReadinessRow, ...]

    @property
    def ready(self) -> bool:
        return self.status == READY


def _blocked_row(entity_type, entity_id, set_id, diagnostics):
    rows = tuple(diagnostics or ())
    codes = tuple(sorted({
        str(item.diagnostic_code or item.reason or item.scope)
        for item in rows
    }))
    return ReceivingReadinessRow(
        entity_type=str(entity_type), entity_id=str(entity_id), set_id=str(set_id),
        status=BLOCKED, blocker_codes=codes, diagnostics=rows,
    )


def _ready_row(entity_type, entity_id, set_id):
    return ReceivingReadinessRow(
        entity_type=str(entity_type), entity_id=str(entity_id), set_id=str(set_id),
        status=READY,
    )


def build_receiving_readiness_graph(layout, intrinsic_failures: Iterable[ReceivingIntrinsicFailure] = ()):
    """Classify R-028 validity without propagating derived NOT_EXPORTABLE state."""
    normalized = normalize_receiving_layout(layout)
    sets_by_id = {}
    bay_owner = {}
    joint_owner = {}
    set_bay_ids = {}
    set_joint_ids = {}
    bay_joint_ids = {}

    for set_row in normalized["sets"]:
        set_id = str(set_row["stable_id"])
        sets_by_id[set_id] = set_row
        bays = tuple(str(row["stable_id"]) for row in set_row["bays"])
        joints = tuple(str(row["stable_id"]) for row in set_row["joints"])
        set_bay_ids[set_id] = bays
        set_joint_ids[set_id] = joints
        for bay_id in bays:
            bay_owner[bay_id] = set_id
            bay_joint_ids[bay_id] = []
        for joint in set_row["joints"]:
            joint_id = str(joint["stable_id"])
            joint_owner[joint_id] = (
                set_id, str(joint["left_bay_id"]), str(joint["right_bay_id"])
            )
            bay_joint_ids[str(joint["left_bay_id"])].append(joint_id)
            bay_joint_ids[str(joint["right_bay_id"])].append(joint_id)

    direct_bay_failures = {bay_id: [] for bay_id in bay_owner}
    direct_joint_failures = {joint_id: [] for joint_id in joint_owner}

    for failure in tuple(intrinsic_failures or ()):
        if not isinstance(failure, ReceivingIntrinsicFailure):
            raise TypeError("intrinsic_failures must contain ReceivingIntrinsicFailure")
        if failure.scope == BAY_INTRINSIC:
            bay_id = str(failure.bay_id)
            if bay_id not in bay_owner:
                raise ValueError(f"unknown Receiving Bay failure target: {bay_id}")
            if str(failure.set_id) != bay_owner[bay_id]:
                raise ValueError("Bay failure set_id does not own target Bay")
            direct_bay_failures[bay_id].append(failure)
        else:
            joint_id = str(failure.joint_id)
            if joint_id not in joint_owner:
                raise ValueError(f"unknown Receiving Joint failure target: {joint_id}")
            if str(failure.set_id) != joint_owner[joint_id][0]:
                raise ValueError("Joint failure set_id does not own target Joint")
            direct_joint_failures[joint_id].append(failure)

    joints = {}
    for joint_id, (set_id, _left, _right) in joint_owner.items():
        rows = tuple(direct_joint_failures[joint_id])
        joints[joint_id] = (
            _blocked_row("JOINT", joint_id, set_id, rows)
            if rows else _ready_row("JOINT", joint_id, set_id)
        )

    bays = {}
    for bay_id, set_id in bay_owner.items():
        rows = list(direct_bay_failures[bay_id])
        # Joint-intrinsic invalidity blocks each participant Bay package. This
        # is a one-hop dependency effect only; the resulting Bay BLOCKED state
        # is never fed back into other Joint validity.
        for joint_id, (_owner_set, left_id, right_id) in joint_owner.items():
            if bay_id in {left_id, right_id}:
                rows.extend(direct_joint_failures[joint_id])
        bays[bay_id] = (
            _blocked_row("BAY", bay_id, set_id, rows)
            if rows else _ready_row("BAY", bay_id, set_id)
        )

    sets = {}
    for set_id in sets_by_id:
        blockers = []
        for bay_id in set_bay_ids[set_id]:
            if not bays[bay_id].ready:
                blockers.extend(bays[bay_id].diagnostics)
        for joint_id in set_joint_ids[set_id]:
            if not joints[joint_id].ready:
                blockers.extend(joints[joint_id].diagnostics)
        # De-duplicate identical intrinsic records. A Joint failure appears on
        # its Joint row and both participant Bay package rows by design.
        unique = []
        seen = set()
        for item in blockers:
            key = (
                item.scope, item.set_id, item.bay_id, item.joint_id,
                item.physical_piece, item.conflicting_feature_ids,
                item.diagnostic_code, item.reason,
            )
            if key not in seen:
                seen.add(key)
                unique.append(item)
        sets[set_id] = (
            _blocked_row("SET", set_id, set_id, tuple(unique))
            if unique else _ready_row("SET", set_id, set_id)
        )

    return ReceivingReadinessGraph(
        sets=sets, bays=bays, joints=joints,
        set_bay_ids={key: tuple(value) for key, value in set_bay_ids.items()},
        set_joint_ids={key: tuple(value) for key, value in set_joint_ids.items()},
        bay_joint_ids={key: tuple(value) for key, value in bay_joint_ids.items()},
    )


@dataclass(frozen=True)
class ReceivingManufacturingReadinessResolution:
    graph: ReceivingReadinessGraph
    instance_geometries: Mapping[str, object]
    joint_resolutions: Mapping[str, object]


def _pairing_failure_from_geometry(*, set_id: str, bay_id: str, geometry):
    for item in tuple(getattr(geometry, "diagnostics", ()) or ()):
        code = str(getattr(item, "diagnostic_code", "") or "")
        status = str(getattr(item, "status", "") or "")
        if status != "BLOCKED":
            continue
        if code not in {
            "RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS",
            "RECEIVING_PAIRING_MARK_CONFLICT",
            "RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED",
        }:
            continue
        evidence = dict(getattr(item, "evidence", {}) or {})
        return ReceivingIntrinsicFailure(
            scope=BAY_INTRINSIC, set_id=set_id, bay_id=bay_id,
            physical_piece=str(getattr(item, "physical_piece", "") or "box_body:left_side"),
            conflicting_feature_ids=tuple(evidence.get("conflicting_feature_ids") or ()),
            reason=str(getattr(item, "diagnostic_detail", "") or code),
            diagnostic_code=code,
        )
    return None


def resolve_receiving_manufacturing_readiness(
    snapshot, *, resolve_bay: Callable[[Mapping[str, object], int, int], object],
    resolve_joint: Callable[..., object] | None = None, thickness: float = 2.0, frame_width: float = 29.0,
) -> ReceivingManufacturingReadinessResolution:
    """Resolve every Bay independently, every Joint independently, then classify R-028.

    ``resolve_bay`` is the existing single-Bay manufacturing engine boundary. It
    receives one transient per-Bay projection and must return either geometry or
    an object exposing ``geometry``. No multi-Bay geometry engine is introduced.
    """
    from .receiving_joint_locks import (
        ReceivingJointLockPatternError, resolve_receiving_joint_lock_pattern,
    )
    from .receiving_layout import (
        RECEIVING_BAY_COMMON_STATE_INVALID, ReceivingBayProjectionError,
        normalize_receiving_layout, project_receiving_bay_legacy_aliases,
    )

    source = dict(snapshot or {})
    layout = normalize_receiving_layout(source.get("receiving_layout"))
    failures = []
    instance_geometries = {}
    joint_resolutions = {}

    for set_index, set_row in enumerate(layout["sets"]):
        set_id = str(set_row["stable_id"])
        for bay_index, bay in enumerate(set_row["bays"]):
            bay_id = str(bay["stable_id"])
            try:
                projected = project_receiving_bay_legacy_aliases(
                    source, set_index=set_index, bay_index=bay_index, validate_common=True
                )
                resolved = resolve_bay(projected, set_index, bay_index)
                geometry = getattr(resolved, "geometry", resolved)
                instance_geometries[bay_id] = geometry
                pairing_failure = _pairing_failure_from_geometry(
                    set_id=set_id, bay_id=bay_id, geometry=geometry
                )
                if pairing_failure is not None:
                    failures.append(pairing_failure)
            except ReceivingBayProjectionError as exc:
                failures.append(ReceivingIntrinsicFailure(
                    scope=BAY_INTRINSIC, set_id=set_id, bay_id=bay_id,
                    reason=str(exc), diagnostic_code=RECEIVING_BAY_COMMON_STATE_INVALID,
                ))

        joint_fn = resolve_joint or resolve_receiving_joint_lock_pattern
        for joint_index, joint in enumerate(set_row["joints"]):
            joint_id = str(joint["stable_id"])
            try:
                joint_resolutions[joint_id] = joint_fn(
                    layout, set_index=set_index, joint_index=joint_index,
                    thickness=float(thickness), frame_width=float(frame_width),
                )
            except ReceivingJointLockPatternError as exc:
                failures.append(ReceivingIntrinsicFailure(
                    scope=JOINT_INTRINSIC, set_id=set_id, joint_id=joint_id,
                    physical_piece="box_body:left_side|box_body:right_side",
                    reason=str(exc), diagnostic_code=str(exc.code),
                ))

    graph = build_receiving_readiness_graph(layout, failures)
    return ReceivingManufacturingReadinessResolution(
        graph=graph, instance_geometries=dict(instance_geometries),
        joint_resolutions=dict(joint_resolutions),
    )


def receiving_readiness_projection(graph: ReceivingReadinessGraph):
    """Pure UI projection: authority stays in the graph."""
    rows = []
    for entity_type, table in (("SET", graph.sets), ("BAY", graph.bays), ("JOINT", graph.joints)):
        for entity_id, row in table.items():
            rows.append({
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "set_id": str(row.set_id),
                "status": str(row.status),
                "diagnostics": tuple({
                    "physical_piece": item.physical_piece,
                    "conflicting_feature_ids": item.conflicting_feature_ids,
                    "reason": item.reason,
                    "diagnostic_code": item.diagnostic_code,
                } for item in row.diagnostics),
            })
    return tuple(rows)


def evaluate_receiving_export(
    graph: ReceivingReadinessGraph, *,
    bay_ids: Iterable[str] = (), set_ids: Iterable[str] = (), full_project: bool = False,
) -> ReceivingExportDecision:
    """Evaluate exact requested dependency closure before any file mutation."""
    wanted_bays = set(str(value) for value in tuple(bay_ids or ()))
    wanted_sets = set(str(value) for value in tuple(set_ids or ()))
    if full_project:
        wanted_sets = set(graph.sets)
    unknown_sets = wanted_sets - set(graph.sets)
    unknown_bays = wanted_bays - set(graph.bays)
    if unknown_sets or unknown_bays:
        raise ValueError(f"unknown Receiving export target: sets={sorted(unknown_sets)}, bays={sorted(unknown_bays)}")

    for set_id in wanted_sets:
        wanted_bays.update(graph.set_bay_ids[set_id])

    dependency_rows = {}
    for set_id in wanted_sets:
        dependency_rows[("SET", set_id)] = graph.sets[set_id]
        for joint_id in graph.set_joint_ids[set_id]:
            dependency_rows[("JOINT", joint_id)] = graph.joints[joint_id]
    for bay_id in wanted_bays:
        dependency_rows[("BAY", bay_id)] = graph.bays[bay_id]
        for joint_id in graph.bay_joint_ids[bay_id]:
            dependency_rows[("JOINT", joint_id)] = graph.joints[joint_id]

    blockers = tuple(
        row for _key, row in sorted(dependency_rows.items()) if not row.ready
    )
    ids = tuple(f"{kind}:{entity_id}" for kind, entity_id in sorted(dependency_rows))
    return ReceivingExportDecision(
        status=BLOCKED if blockers else READY,
        requested_bay_ids=tuple(sorted(wanted_bays)),
        dependency_entity_ids=ids,
        blockers=blockers,
    )


def receiving_instance_key(set_id: str, bay_id: str) -> str:
    return f"{str(set_id)}::{str(bay_id)}"


def _safe_component(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Receiving instance identity component is empty")
    return re.sub(r'[<>:"/\\|?*]', "_", text)


def save_receiving_instance_batch_dxf(
    *, graph: ReceivingReadinessGraph, layout, instance_geometries: Mapping[str, object],
    output_dir, save_geometry: Callable[..., Mapping[str, str]],
    verify_geometry: Callable[..., object] | None = None,
    bay_ids: Iterable[str] = (), set_ids: Iterable[str] = (),
    full_project: bool = False, overwrite: bool = False,
):
    """Atomically publish stable Set/Bay-scoped physical DXF inventories."""
    decision = evaluate_receiving_export(
        graph, bay_ids=bay_ids, set_ids=set_ids, full_project=full_project
    )
    if not decision.ready:
        blocker_ids = ", ".join(
            f"{row.entity_type}:{row.entity_id}" for row in decision.blockers
        )
        raise ValueError(f"RECEIVING_EXPORT_BLOCKED: {blocker_ids}")

    normalized = normalize_receiving_layout(layout)
    bay_to_set = {}
    for set_row in normalized["sets"]:
        for bay in set_row["bays"]:
            bay_to_set[str(bay["stable_id"])] = str(set_row["stable_id"])

    missing = set(decision.requested_bay_ids) - set(instance_geometries)
    if missing:
        raise ValueError(f"missing resolved Receiving Bay geometry: {sorted(missing)}")

    root = Path(output_dir)
    root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{root.name}.receiving-tmp-", dir=str(root.parent)))
    inventory = {}
    try:
        for bay_id in decision.requested_bay_ids:
            set_id = bay_to_set[bay_id]
            instance_key = receiving_instance_key(set_id, bay_id)
            instance_dir = temp_root / _safe_component(set_id) / _safe_component(bay_id)
            outputs = dict(save_geometry(
                instance_geometries[bay_id], instance_dir, overwrite=True
            ))
            if callable(verify_geometry):
                verification = verify_geometry(instance_geometries[bay_id], instance_dir)
                if not bool(getattr(verification, "ok", False)):
                    raise ValueError(f"Receiving DXF reopen verification failed: {instance_key}")
            for part_id, path in outputs.items():
                inventory[f"{instance_key}::{part_id}"] = str(path)

        if root.exists():
            if not overwrite:
                raise FileExistsError(str(root))
            shutil.rmtree(root)
        os.replace(temp_root, root)
        published = {}
        for key, old_path in inventory.items():
            rel = Path(old_path).relative_to(temp_root)
            published[key] = str(root / rel)
        return published
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


__all__ = [
    "READY", "BLOCKED", "JOINT_INTRINSIC", "BAY_INTRINSIC",
    "ReceivingIntrinsicFailure", "ReceivingReadinessRow", "ReceivingReadinessGraph",
    "ReceivingManufacturingReadinessResolution",
    "ReceivingExportDecision", "build_receiving_readiness_graph",
    "resolve_receiving_manufacturing_readiness",
    "receiving_readiness_projection", "evaluate_receiving_export",
    "receiving_instance_key", "save_receiving_instance_batch_dxf",
]
