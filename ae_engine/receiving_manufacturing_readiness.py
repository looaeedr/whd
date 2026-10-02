# -*- coding: utf-8 -*-
"""Receiving V1.6 manufacturing readiness and multi-instance export.

This module is the single Receiving-only projection between intrinsic
manufacturing failures and export/UI behavior. It never makes NOT_EXPORTABLE
an intrinsic cause and never changes generic single-cabinet DXF semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Mapping
from urllib.parse import quote

from .receiving_layout import normalize_receiving_layout

READY = "READY"
BLOCKED = "BLOCKED"
JOINT_INTRINSIC = "JOINT_INTRINSIC"
BAY_INTRINSIC = "BAY_INTRINSIC"
NOT_EXPORTABLE = "NOT_EXPORTABLE"

RECEIVING_JOINT_FEATURE_CONFLICT = "RECEIVING_JOINT_FEATURE_CONFLICT"

_JOINT_INTRINSIC_CODES = frozenset({
    "RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION",
    "RECEIVING_LOCK_PATTERN_OUT_OF_BOUNDS",
    "RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION",
    RECEIVING_JOINT_FEATURE_CONFLICT,
})
_BAY_INTRINSIC_CODES = frozenset({
    "RECEIVING_BAY_COMMON_STATE_INVALID",
    "RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS",
    "RECEIVING_PAIRING_MARK_CONFLICT",
})


@dataclass(frozen=True)
class ReceivingIntrinsicFailure:
    kind: str
    set_id: str
    entity_id: str
    code: str
    reason: str
    physical_piece: str = ""
    feature_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip().upper()
        code = str(self.code or "").strip()
        if kind not in {JOINT_INTRINSIC, BAY_INTRINSIC}:
            raise ValueError(f"unsupported Receiving intrinsic failure kind: {self.kind!r}")
        if code == NOT_EXPORTABLE:
            raise ValueError("NOT_EXPORTABLE is a derived result, never an intrinsic failure")
        if not str(self.set_id or "").strip():
            raise ValueError("Receiving intrinsic failure requires set_id")
        if not str(self.entity_id or "").strip():
            raise ValueError("Receiving intrinsic failure requires entity_id")
        if not code:
            raise ValueError("Receiving intrinsic failure requires code")
        if not str(self.reason or "").strip():
            raise ValueError("Receiving intrinsic failure requires reason")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "set_id", str(self.set_id))
        object.__setattr__(self, "entity_id", str(self.entity_id))
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "physical_piece", str(self.physical_piece or ""))
        object.__setattr__(
            self,
            "feature_ids",
            tuple(str(value) for value in tuple(self.feature_ids or ()) if str(value)),
        )


def classify_receiving_intrinsic_code(code: object) -> str:
    value = str(code or "").strip()
    if value in _JOINT_INTRINSIC_CODES:
        return JOINT_INTRINSIC
    if value in _BAY_INTRINSIC_CODES:
        return BAY_INTRINSIC
    if value == NOT_EXPORTABLE:
        raise ValueError("NOT_EXPORTABLE cannot be reclassified as an intrinsic failure")
    raise ValueError(f"unclassified Receiving intrinsic failure code: {value!r}")


def intrinsic_failure(
    *,
    set_id: object,
    entity_id: object,
    code: object,
    reason: object,
    physical_piece: object = "",
    feature_ids: Iterable[object] = (),
) -> ReceivingIntrinsicFailure:
    value = str(code or "").strip()
    return ReceivingIntrinsicFailure(
        kind=classify_receiving_intrinsic_code(value),
        set_id=str(set_id or ""),
        entity_id=str(entity_id or ""),
        code=value,
        reason=str(reason or ""),
        physical_piece=str(physical_piece or ""),
        feature_ids=tuple(str(item) for item in tuple(feature_ids or ())),
    )


@dataclass(frozen=True)
class ReceivingEntityReadiness:
    entity_type: str
    stable_id: str
    status: str
    blockers: tuple[ReceivingIntrinsicFailure, ...] = ()
    bay_ids: tuple[str, ...] = ()
    joint_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReceivingReadiness:
    sets: tuple[ReceivingEntityReadiness, ...]
    bays: tuple[ReceivingEntityReadiness, ...]
    joints: tuple[ReceivingEntityReadiness, ...]

    def _row(self, rows, stable_id: object) -> ReceivingEntityReadiness:
        key = str(stable_id or "")
        for row in rows:
            if row.stable_id == key:
                return row
        raise KeyError(key)

    def set(self, stable_id: object) -> ReceivingEntityReadiness:
        return self._row(self.sets, stable_id)

    def bay(self, stable_id: object) -> ReceivingEntityReadiness:
        return self._row(self.bays, stable_id)

    def joint(self, stable_id: object) -> ReceivingEntityReadiness:
        return self._row(self.joints, stable_id)


def _dedupe_failures(rows) -> tuple[ReceivingIntrinsicFailure, ...]:
    result = []
    seen = set()
    for row in rows:
        key = (
            row.kind, row.set_id, row.entity_id, row.code, row.reason,
            row.physical_piece, row.feature_ids,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return tuple(result)


def resolve_receiving_readiness(
    layout: Mapping[str, object],
    intrinsic_failures: Iterable[ReceivingIntrinsicFailure] = (),
) -> ReceivingReadiness:
    """Project intrinsic failures to Set/Bay/Joint READY/BLOCKED state.

    R-028 propagation is intentionally one-way:
    * Joint intrinsic -> that Joint + its two participant Bays.
    * Bay intrinsic -> that Bay only.
    * Set status is an aggregate projection only.
    * NOT_EXPORTABLE is never accepted as new input.
    """
    normalized = normalize_receiving_layout(layout)
    set_index = {}
    bay_index = {}
    joint_index = {}
    for set_row in normalized["sets"]:
        set_id = str(set_row["stable_id"])
        set_index[set_id] = set_row
        for bay in set_row["bays"]:
            bay_index[str(bay["stable_id"])] = (set_id, bay)
        for joint in set_row["joints"]:
            joint_index[str(joint["stable_id"])] = (set_id, joint)

    bay_blockers = {key: [] for key in bay_index}
    joint_blockers = {key: [] for key in joint_index}

    for failure in tuple(intrinsic_failures or ()):
        if not isinstance(failure, ReceivingIntrinsicFailure):
            raise TypeError("intrinsic_failures must contain ReceivingIntrinsicFailure")
        if failure.set_id not in set_index:
            raise ValueError(f"unknown Receiving set_id in failure: {failure.set_id}")
        if failure.kind == BAY_INTRINSIC:
            row = bay_index.get(failure.entity_id)
            if row is None or row[0] != failure.set_id:
                raise ValueError(
                    f"Bay-intrinsic failure does not identify a Bay in {failure.set_id}: "
                    f"{failure.entity_id}"
                )
            bay_blockers[failure.entity_id].append(failure)
            continue

        row = joint_index.get(failure.entity_id)
        if row is None or row[0] != failure.set_id:
            raise ValueError(
                f"Joint-intrinsic failure does not identify a Joint in {failure.set_id}: "
                f"{failure.entity_id}"
            )
        _set_id, joint = row
        joint_blockers[failure.entity_id].append(failure)
        # This is the only allowed cross-entity propagation in R-028.
        bay_blockers[str(joint["left_bay_id"])].append(failure)
        bay_blockers[str(joint["right_bay_id"])].append(failure)

    bay_rows = tuple(
        ReceivingEntityReadiness(
            entity_type="BAY",
            stable_id=bay_id,
            status=BLOCKED if bay_blockers[bay_id] else READY,
            blockers=_dedupe_failures(bay_blockers[bay_id]),
        )
        for bay_id in bay_index
    )
    joint_rows = tuple(
        ReceivingEntityReadiness(
            entity_type="JOINT",
            stable_id=joint_id,
            status=BLOCKED if joint_blockers[joint_id] else READY,
            blockers=_dedupe_failures(joint_blockers[joint_id]),
        )
        for joint_id in joint_index
    )
    bay_by_id = {row.stable_id: row for row in bay_rows}
    joint_by_id = {row.stable_id: row for row in joint_rows}

    set_rows = []
    for set_row in normalized["sets"]:
        set_id = str(set_row["stable_id"])
        bay_ids = tuple(str(row["stable_id"]) for row in set_row["bays"])
        joint_ids = tuple(str(row["stable_id"]) for row in set_row["joints"])
        blockers = _dedupe_failures(
            failure
            for entity_id in (*bay_ids, *joint_ids)
            for failure in (
                bay_by_id[entity_id].blockers
                if entity_id in bay_by_id
                else joint_by_id[entity_id].blockers
            )
        )
        set_rows.append(
            ReceivingEntityReadiness(
                entity_type="SET",
                stable_id=set_id,
                status=BLOCKED if blockers else READY,
                blockers=blockers,
                bay_ids=bay_ids,
                joint_ids=joint_ids,
            )
        )
    return ReceivingReadiness(
        sets=tuple(set_rows),
        bays=bay_rows,
        joints=joint_rows,
    )


def _diagnostic_payload(failure: ReceivingIntrinsicFailure) -> dict[str, object]:
    return {
        "kind": failure.kind,
        "set_id": failure.set_id,
        "entity_id": failure.entity_id,
        "code": failure.code,
        "reason": failure.reason,
        "physical_piece": failure.physical_piece,
        "feature_ids": tuple(failure.feature_ids),
    }


def project_receiving_readiness(
    layout: Mapping[str, object],
    readiness: ReceivingReadiness,
) -> dict[str, object]:
    """Return read-only UI rows; this projection never mutates manufacturing state."""
    normalized = normalize_receiving_layout(layout)
    rows = []
    for set_row in normalized["sets"]:
        set_id = str(set_row["stable_id"])
        set_state = readiness.set(set_id)
        rows.append({
            "entity_type": "SET",
            "stable_id": set_id,
            "status": set_state.status,
            "diagnostics": tuple(_diagnostic_payload(row) for row in set_state.blockers),
            "bays": tuple({
                "entity_type": "BAY",
                "stable_id": str(bay["stable_id"]),
                "status": readiness.bay(bay["stable_id"]).status,
                "diagnostics": tuple(
                    _diagnostic_payload(row)
                    for row in readiness.bay(bay["stable_id"]).blockers
                ),
            } for bay in set_row["bays"]),
            "joints": tuple({
                "entity_type": "JOINT",
                "stable_id": str(joint["stable_id"]),
                "status": readiness.joint(joint["stable_id"]).status,
                "diagnostics": tuple(
                    _diagnostic_payload(row)
                    for row in readiness.joint(joint["stable_id"]).blockers
                ),
            } for joint in set_row["joints"]),
        })
    return {"sets": tuple(rows)}


def receiving_export_blockers(
    readiness: ReceivingReadiness,
    *,
    scope: str,
    set_id: object | None = None,
    bay_id: object | None = None,
    requested_bay_ids: Iterable[object] = (),
) -> tuple[ReceivingIntrinsicFailure, ...]:
    scope_value = str(scope or "").strip().upper()
    rows = []
    if scope_value == "BAY":
        if bay_id is None:
            raise ValueError("BAY export requires bay_id")
        rows.extend(readiness.bay(bay_id).blockers)
    elif scope_value == "SET":
        if set_id is None:
            raise ValueError("SET export requires set_id")
        rows.extend(readiness.set(set_id).blockers)
    elif scope_value == "PROJECT":
        requested = tuple(str(value) for value in tuple(requested_bay_ids or ()))
        if requested:
            for value in requested:
                rows.extend(readiness.bay(value).blockers)
        else:
            for set_row in readiness.sets:
                rows.extend(set_row.blockers)
    else:
        raise ValueError(f"unsupported Receiving export scope: {scope!r}")
    return _dedupe_failures(rows)


class ReceivingExportBlocked(RuntimeError):
    def __init__(self, blockers: Iterable[ReceivingIntrinsicFailure]):
        self.blockers = tuple(blockers or ())
        detail = "; ".join(
            f"{row.entity_id}:{row.code}:{row.reason}" for row in self.blockers
        )
        super().__init__(f"Receiving export BLOCKED: {detail}")


def assert_receiving_exportable(readiness: ReceivingReadiness, **request) -> None:
    blockers = receiving_export_blockers(readiness, **request)
    if blockers:
        raise ReceivingExportBlocked(blockers)


@dataclass(frozen=True)
class ReceivingManufacturingInstance:
    set_id: str
    bay_id: str
    geometry: object

    def __post_init__(self) -> None:
        if not str(self.set_id or "").strip() or not str(self.bay_id or "").strip():
            raise ValueError("Receiving manufacturing instance requires stable Set/Bay IDs")


@dataclass(frozen=True)
class ReceivingExportInventoryRow:
    set_id: str
    bay_id: str
    part_id: str
    relative_path: str


def _identity_segment(prefix: str, stable_id: object) -> str:
    value = str(stable_id or "").strip()
    if not value:
        raise ValueError("Receiving stable instance ID is empty")
    return f"{prefix}={quote(value, safe='')}"


def receiving_instance_directory(root: Path, *, set_id: object, bay_id: object) -> Path:
    return root / _identity_segment("set", set_id) / _identity_segment("bay", bay_id)


def _preflight_instances(
    instances: Iterable[ReceivingManufacturingInstance],
    readiness: ReceivingReadiness,
) -> tuple[ReceivingManufacturingInstance, ...]:
    rows = tuple(instances or ())
    if not rows:
        raise ValueError("Receiving export requires at least one Bay instance")
    seen = set()
    for row in rows:
        if not isinstance(row, ReceivingManufacturingInstance):
            raise TypeError("instances must contain ReceivingManufacturingInstance")
        key = (row.set_id, row.bay_id)
        if key in seen:
            raise ValueError(f"duplicate Receiving manufacturing instance: {key}")
        seen.add(key)
        state = readiness.bay(row.bay_id)
        # Binding Set identity is part of export inventory authority.
        matching_set = next(
            (item for item in readiness.sets if row.bay_id in item.bay_ids),
            None,
        )
        if matching_set is None or matching_set.stable_id != row.set_id:
            raise ValueError(
                f"Receiving instance Set/Bay identity mismatch: {row.set_id}/{row.bay_id}"
            )
        if state.status != READY:
            raise ReceivingExportBlocked(state.blockers)
    return rows


def verify_receiving_manufacturing_instances_dxf(
    instances: Iterable[ReceivingManufacturingInstance],
    output_dir,
) -> dict[tuple[str, str], object]:
    """Reopen each Bay package using the existing generic physical-piece verifier."""
    from ae_engine import manufacturing_api as api

    root = Path(output_dir)
    results = {}
    for row in tuple(instances or ()):
        directory = receiving_instance_directory(
            root, set_id=row.set_id, bay_id=row.bay_id
        )
        result = api.verify_saved_resolved_manufacturing_geometry_dxf(
            row.geometry, directory
        )
        results[(row.set_id, row.bay_id)] = result
    return results


def save_receiving_manufacturing_instances_dxf(
    instances: Iterable[ReceivingManufacturingInstance],
    output_dir,
    *,
    readiness: ReceivingReadiness,
    overwrite: bool = False,
) -> tuple[ReceivingExportInventoryRow, ...]:
    """Atomically export one requested multi-Bay batch after readiness preflight.

    Stable Set/Bay IDs live in directory identity only. Existing physical-piece
    DXF filenames are preserved and no ID is engraved into sheet geometry.
    """
    from ae_engine import manufacturing_api as api

    rows = _preflight_instances(instances, readiness)
    root = Path(output_dir)
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists() and not overwrite:
        raise FileExistsError(str(root))

    stage = Path(tempfile.mkdtemp(prefix=f".{root.name}.tmp-", dir=str(root.parent)))
    backup = None
    try:
        inventory = []
        for row in rows:
            directory = receiving_instance_directory(
                stage, set_id=row.set_id, bay_id=row.bay_id
            )
            outputs = api.save_resolved_manufacturing_geometry_dxf(
                row.geometry, directory, overwrite=True
            )
            check = api.verify_saved_resolved_manufacturing_geometry_dxf(
                row.geometry, directory
            )
            if not bool(getattr(check, "ok", False)):
                raise RuntimeError(
                    f"Receiving DXF reopen verification failed for "
                    f"{row.set_id}/{row.bay_id}: {getattr(check, 'issues', ())}"
                )
            for part_id, path in outputs.items():
                inventory.append(
                    ReceivingExportInventoryRow(
                        set_id=row.set_id,
                        bay_id=row.bay_id,
                        part_id=str(part_id),
                        relative_path=str(Path(path).relative_to(stage)),
                    )
                )

        if root.exists():
            backup = root.with_name(root.name + ".previous")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(root, backup)
        try:
            os.replace(stage, root)
        except Exception:
            if backup is not None and backup.exists() and not root.exists():
                os.replace(backup, root)
            raise
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
        stage = None
        return tuple(inventory)
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


__all__ = [
    "BAY_INTRINSIC",
    "BLOCKED",
    "JOINT_INTRINSIC",
    "NOT_EXPORTABLE",
    "READY",
    "RECEIVING_JOINT_FEATURE_CONFLICT",
    "ReceivingEntityReadiness",
    "ReceivingExportBlocked",
    "ReceivingExportInventoryRow",
    "ReceivingIntrinsicFailure",
    "ReceivingManufacturingInstance",
    "ReceivingReadiness",
    "assert_receiving_exportable",
    "classify_receiving_intrinsic_code",
    "intrinsic_failure",
    "project_receiving_readiness",
    "receiving_export_blockers",
    "receiving_instance_directory",
    "resolve_receiving_readiness",
    "save_receiving_manufacturing_instances_dxf",
    "verify_receiving_manufacturing_instances_dxf",
]
