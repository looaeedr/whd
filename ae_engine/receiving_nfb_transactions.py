# -*- coding: utf-8 -*-
"""#1500 atomic NFBConfig submit, Bay copy, restore and optimistic Undo.

This owns no NFB geometry, source catalog, legacy Hole Editor Feature or
version schema. It writes only the #1499 per-Bay submission fact and user
NFBConfig into the existing ReceivingLayout. A submission requires current
#1498 physically derived readiness; cancel/failed preflight change nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Callable, Mapping, Sequence

from .receiving_layout import normalize_receiving_layout, update_receiving_bay
from .receiving_nfb_persistence import (
    normalize_nfb_saved_fields, normalize_nfb_config, reconfirm_copied_nfb_config,
)
from .receiving_nfb_part_readiness import (
    NfbPhysicalScope, NfbPartDecision, NfbScopeReadiness,
    BLOCKED, derive_nfb_part_readiness,
)
from .receiving_nfb_dxf_source import NfbSourceInventory
from .receiving_nfb_manufacturing_release import NfbValidatedInnerDoorRender


@dataclass(frozen=True)
class NfbTransactionPreview:
    action: str
    source_bay_id: str | None
    target_bay_ids: tuple[str, ...]
    impacted_parts: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    held_parts: tuple[str, ...] = ()
    dependency_warnings: tuple[str, ...] = ()
    requires_confirmation: bool = True

    @property
    def can_commit(self) -> bool:
        return not self.blocking_reasons


@dataclass(frozen=True)
class NfbBayChange:
    set_index: int
    bay_index: int
    stable_id: str
    previous: dict
    committed: dict


@dataclass(frozen=True)
class NfbTransactionReceipt:
    action: str
    changes: tuple[NfbBayChange, ...]


@dataclass(frozen=True)
class NfbTransactionOutcome:
    layout: dict
    preview: NfbTransactionPreview
    receipt: NfbTransactionReceipt | None
    changed: bool


def _selected(layout, set_index: int, bay_indices: Sequence[int]):
    normalized = normalize_receiving_layout(layout)
    if type(set_index) is not int or not 0 <= set_index < len(normalized["sets"]):
        raise ValueError("NFB transaction requires existing Set")
    bays = normalized["sets"][set_index]["bays"]
    targets = tuple(bay_indices)
    if (not targets or len(targets) != len(set(targets))
            or any(type(i) is not int or i < 0 or i >= len(bays) for i in targets)):
        raise ValueError("NFB transaction requires distinct real highlighted Bays")
    return normalized, tuple(sorted(targets))


def _fact(bay):
    return normalize_nfb_saved_fields(bay)


def _confirmed_operator_x(config):
    for hole in config["holes"]:
        if hole["manual_x_state"] != "CONFIRMED":
            raise ValueError("NFB X requires operator confirmation for each physical hole")
        if hole["manual_x_mm"] is None:
            raise ValueError("NFB X coordinate missing")
        if not hole.get("datum_revision") or not hole.get("datum_snapshot"):
            raise ValueError("NFB physical datum/version is missing")
        snapshot = hole["datum_snapshot"]
        if not isinstance(snapshot, Mapping):
            raise ValueError("NFB physical datum must be a named source mapping")
        if ("rotation_deg" in snapshot
                and (type(snapshot["rotation_deg"]) is not int
                     or snapshot["rotation_deg"] != hole["rotation_deg"])):
            raise ValueError("NFB physical rotation datum requires operator reconfirmation")
        if ("model_filename" in snapshot
                and (not isinstance(snapshot["model_filename"], str)
                     or snapshot["model_filename"] != hole["model_filename"])):
            raise ValueError("NFB physical model datum requires operator reconfirmation")


def _verify_hole_locations(config, door: NfbValidatedInnerDoorRender):
    """Match operator values to EXACT manufactured CUTTING evidence, not IDs alone.

    Same model/physical_hole_id with changed X, Y slot or rotation MUST require
    a new #1497 verification. An old manufactured result never grants an
    unverified new displacement.
    """
    witnessed = tuple(door.verified_hole_locations)
    holes = tuple(config["holes"])
    if len(witnessed) != len(holes) or not witnessed:
        raise ValueError("NFB verified physical X/Y/rotation evidence missing")
    original = {row[0]: row for row in witnessed}
    if len(original) != len(witnessed):
        raise ValueError("NFB source proof repeats physical holes")
    for hole in holes:
        key = hole["physical_hole_id"]
        if key not in original:
            raise ValueError("NFB submitted physical-hole ID absent from machining proof")
        actual_slot = hole.get("slot_index")
        actual_count = hole.get("layer_count", config.get("layer_count"))
        if type(actual_slot) is not int or type(actual_count) is not int:
            raise ValueError("NFB slot/layer cannot be inferred for production")
        want = (key, float(hole["manual_x_mm"]), actual_count,
                actual_slot, hole["rotation_deg"])
        observed = original[key]
        if (len(observed) != 5 or abs(want[1] - observed[1]) > 1e-6
                or want[2:] != observed[2:]):
            raise ValueError("NFB configured X/Y slot/rotation differs from actual CUTTING")


def _ready(
    set_row, bay, *,
    version_id: str,
    scope: NfbPhysicalScope,
    inventory: NfbSourceInventory | None,
    verified_inner_door: NfbValidatedInnerDoorRender | None,
) -> NfbScopeReadiness:
    if not isinstance(scope, NfbPhysicalScope):
        raise TypeError("NFB manufacturing physical scope is required")
    if scope.identity != (set_row["stable_id"], bay["stable_id"], version_id):
        raise ValueError("NFB readiness scope mismatch: Set/Bay/version")
    if scope.submitted is not True:
        raise ValueError("NFB readiness must be evaluated for submitted candidate")
    # Never rely on the caller's user-facing READY flag or hand-built approval.
    return derive_nfb_part_readiness(
        scope, source_inventory=inventory, verified_inner_door=verified_inner_door,
    )


def _preview(
    action: str, target_ids, *, source_id=None, readiness=(),
    additionally_blocked=(),
):
    affected, held, reasons, pending = [], [], list(additionally_blocked), []
    for result in readiness:
        affected.extend(row.part_id for row in result.decisions)
        pending.extend(result.scope_reasons)
        held.extend(row.part_id for row in result.decisions
                    if row.status == BLOCKED and
                    row.part_id != result.scope.inner_door_part_id)
        if not result.can_submit:
            reasons.extend(result.scope_reasons)
            reasons.extend(f"{row.part_id}: {reason}"
                           for row in result.decisions if row.status == BLOCKED
                           and row.part_id == result.scope.inner_door_part_id
                           for reason in row.reasons)
    return NfbTransactionPreview(
        action=action, source_bay_id=source_id,
        target_bay_ids=tuple(target_ids),
        impacted_parts=tuple(dict.fromkeys(affected)),
        blocking_reasons=tuple(dict.fromkeys(reasons)),
        held_parts=tuple(dict.fromkeys(held)),
        dependency_warnings=tuple(dict.fromkeys(pending)),
    )


def _apply(
    original, preview: NfbTransactionPreview, plans: Sequence[tuple[int,int,dict]],
    *, confirm: Callable[[NfbTransactionPreview], bool] | None,
) -> NfbTransactionOutcome:
    if preview.blocking_reasons:
        raise ValueError("NFB transaction blocked: " + ", ".join(preview.blocking_reasons))
    if confirm is None:
        raise ValueError("NFB transaction confirmation callback required")
    decision = confirm(preview)
    if type(decision) is not bool:
        raise TypeError("NFB operator confirmation must return explicit boolean")
    if not decision:
        return NfbTransactionOutcome(
            layout=deepcopy(original), preview=preview, receipt=None, changed=False,
        )
    candidate = deepcopy(original)
    changes = []
    for si, bi, fields in plans:
        bay = candidate["sets"][si]["bays"][bi]
        before = _fact(bay)
        committed = deepcopy(fields)
        if before == committed:
            continue
        changes.append(NfbBayChange(
            set_index=si, bay_index=bi, stable_id=bay["stable_id"],
            previous=deepcopy(before), committed=deepcopy(committed),
        ))
        # Use the canonical #1499 writer; do not mutate the incoming layout.
        candidate = update_receiving_bay(
            candidate, set_index=si, bay_index=bi,
            nfb_config_submitted=bool(committed),
            nfb_config=deepcopy(committed.get("nfb_config")),
        )
    return NfbTransactionOutcome(
        layout=candidate, preview=preview,
        receipt=NfbTransactionReceipt(preview.action, tuple(changes)) if changes else None,
        changed=bool(changes),
    )


def submit_nfb_bays(
    layout, *, set_index: int, bay_indices: Sequence[int],
    version_id: str, configs: Mapping[int, Mapping],
    evidence: Mapping[int, tuple[NfbPhysicalScope, NfbSourceInventory | None,
                                 NfbValidatedInnerDoorRender | None]],
    confirm: Callable[[NfbTransactionPreview], bool] | None,
) -> NfbTransactionOutcome:
    """Explicit operator Apply of fully verified per-Bay physical NFB locations."""
    state, indices = _selected(layout, set_index, bay_indices)
    set_row = state["sets"][set_index]
    if set(configs) != set(indices) or set(evidence) != set(indices):
        raise ValueError("NFB configs/evidence must cover exactly highlighted Bays")
    plans, reports = [], []
    for bi in indices:
        config = normalize_nfb_config(configs[bi])
        _confirmed_operator_x(config)
        bay = set_row["bays"][bi]
        scope, inventory, door = evidence[bi]
        if not isinstance(door, NfbValidatedInnerDoorRender):
            raise ValueError("NFB configured model has no verified manufacturing result")
        expected_brand = set_row.get("switch_brand", "士林")
        actual_models = {hole["model_filename"] for hole in config["holes"]}
        actual_holes = {hole["physical_hole_id"] for hole in config["holes"]}
        if (len(actual_models) != 1
                or door.indexed_model_key != (expected_brand, next(iter(actual_models)))
                or actual_holes != set(door.physical_hole_ids)):
            raise ValueError("NFB configured brand/model/physical-hole IDs differ from verified CUTTING")
        _verify_hole_locations(config, door)
        reports.append(_ready(set_row, bay, version_id=version_id,
                              scope=scope, inventory=inventory,
                              verified_inner_door=door))
        plans.append((set_index,bi,{
            "nfb_config_submitted": True, "nfb_config": config,
        }))
    preview = _preview("SUBMIT", [set_row["bays"][i]["stable_id"] for i in indices],
                       readiness=reports)
    return _apply(state, preview, plans, confirm=confirm)


def copy_submitted_nfb_bay(
    layout, *, set_index: int, source_bay_index: int, target_bay_index: int,
    version_id: str, target_config: Mapping | None,
    evidence: tuple[NfbPhysicalScope, NfbSourceInventory | None,
                    NfbValidatedInnerDoorRender | None],
    confirm: Callable[[NfbTransactionPreview], bool] | None,
) -> NfbTransactionOutcome:
    """Copy configured source only; target physical hole IDs/X must be explicit.

    The #1499 reconfirm rule deliberately prevents silent reuse of source X.
    The GUI/edit layer must collect destination positions and check datum; this
    is not an overwrite override.
    """
    state, _ = _selected(layout,set_index,(source_bay_index,target_bay_index))
    if source_bay_index == target_bay_index:
        raise ValueError("NFB source and target cannot be same Bay")
    row = state["sets"][set_index]
    source, target = row["bays"][source_bay_index], row["bays"][target_bay_index]
    saved = _fact(source)
    if not saved:
        raise ValueError("NFB UNCONFIGURED Bay cannot be copied as submitted source")
    copied = reconfirm_copied_nfb_config(saved["nfb_config"])
    if target_config is None:
        raise ValueError("NFB destination positions require explicit confirmation")
    configured = normalize_nfb_config(target_config)
    if len(configured["holes"]) != len(copied["holes"]):
        raise ValueError("NFB Bay copy must preserve original number of physical holes")
    source_ids = {hole["physical_hole_id"] for hole in copied["holes"]}
    target_ids = {hole["physical_hole_id"] for hole in configured["holes"]}
    if source_ids & target_ids:
        raise ValueError("NFB copied physical holes require independent target IDs")
    if {k:v for k,v in copied.items() if k != "holes"} != {
            k:v for k,v in configured.items() if k != "holes"}:
        raise ValueError("NFB copy must preserve layer and physical-unit configuration")
    for old, new in zip(copied["holes"], configured["holes"]):
        # Each target must keep an independent physical unit identity.
        # Logical unit IDs are local to a Bay and must not be copied over.
        excluded = {"physical_hole_id", "unit_id", "manual_x_state",
                    "manual_x_mm", "datum_revision", "datum_snapshot"}
        if ({k:v for k,v in old.items() if k not in excluded}
                != {k:v for k,v in new.items() if k not in excluded}):
            raise ValueError("NFB copy must preserve model/rotation/offset identity")
    _confirmed_operator_x(configured)
    scope, inv, door = evidence
    brand = row.get("switch_brand", "士林")
    actual_models = {hole["model_filename"] for hole in configured["holes"]}
    actual_holes = {hole["physical_hole_id"] for hole in configured["holes"]}
    if (not isinstance(door, NfbValidatedInnerDoorRender)
            or len(actual_models) != 1
            or door.indexed_model_key != (brand, next(iter(actual_models)))
            or actual_holes != set(door.physical_hole_ids)):
        raise ValueError("NFB copied source/model/physical-hole IDs not verified for target")
    _verify_hole_locations(configured, door)
    readiness = _ready(row,target,version_id=version_id,scope=scope,
                       inventory=inv,verified_inner_door=door)
    preview = _preview(
        "COPY_OVERWRITE" if _fact(target) else "COPY_SUBMIT",
        (target["stable_id"],),source_id=source["stable_id"],readiness=(readiness,),
    )
    return _apply(state,preview,((set_index,target_bay_index,{
        "nfb_config_submitted":True,"nfb_config":configured,
    }),),confirm=confirm)


def restore_nfb_bays_unconfigured(
    layout, *, set_index:int, bay_indices:Sequence[int],
    confirm: Callable[[NfbTransactionPreview],bool] | None,
) -> NfbTransactionOutcome:
    """Reset only submitted NFB values, never delete legacy Hole Editor."""
    state,indices=_selected(layout,set_index,bay_indices)
    row=state["sets"][set_index]
    preview=_preview("RESTORE_UNCONFIGURED",
                     (row["bays"][i]["stable_id"] for i in indices))
    return _apply(state,preview,tuple((set_index,i,{}) for i in indices),
                  confirm=confirm)


def undo_nfb_transaction(layout, receipt:NfbTransactionReceipt):
    """Optimistic per-Bay undo; refuse if a later edit changed an NFB target."""
    state=normalize_receiving_layout(layout)
    if not isinstance(receipt,NfbTransactionReceipt) or not receipt.changes:
        raise ValueError("NFB Undo requires real previous transaction receipt")
    candidate=state
    for change in receipt.changes:
        try:
            bay=candidate["sets"][change.set_index]["bays"][change.bay_index]
        except (IndexError,KeyError) as exc:
            raise ValueError("NFB Undo target Bay was removed") from exc
        if bay["stable_id"]!=change.stable_id or _fact(bay)!=change.committed:
            raise ValueError("NFB Undo conflict: target NFB has changed since commit")
    for change in reversed(receipt.changes):
        candidate=update_receiving_bay(
            candidate,set_index=change.set_index,bay_index=change.bay_index,
            nfb_config_submitted=bool(change.previous),
            nfb_config=deepcopy(change.previous.get("nfb_config")),
        )
    return candidate
