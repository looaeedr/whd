"""Versioned owner/source-bound manual marks. No geometry or export permission."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from re import fullmatch

from .operator_manual_marking import is_manual_mark
from .workspace_state import resolve_workspace_physical_root_owner

ROOT_MARKING_STORE_KEY = "physical_root_manual_markings"
_SCHEMA = 1
_QUANTITY_SCHEMA = 2
_QUANTITY_OWNER_PATTERN = r"quantity-owner:quantity-v[1-9][0-9]*:root-owner:[a-f0-9]{32}"


def normalize_workspace_root_marking_store(raw):
    if raw is None:
        return {"schema_version": _SCHEMA, "records": {}}
    if (not isinstance(raw, Mapping) or set(raw) != {"schema_version", "records"}
            or type(raw["schema_version"]) is not int or raw["schema_version"] not in {_SCHEMA, _QUANTITY_SCHEMA}
            or not isinstance(raw["records"], Mapping)):
        raise ValueError("ROOT_MARKING_STORE_SCHEMA_INVALID")
    records = {}
    for owner, record in raw["records"].items():
        if (not isinstance(owner, str) or not (fullmatch(r"root-owner:[a-f0-9]{32}", owner)
                    or (raw["schema_version"] == _QUANTITY_SCHEMA and fullmatch(_QUANTITY_OWNER_PATTERN, owner)))
                or not isinstance(record, Mapping) or set(record) != {"source_sha256", "features"}):
            raise ValueError("ROOT_MARKING_STORE_RECORD_INVALID")
        seal, features = record["source_sha256"], record["features"]
        if (not isinstance(seal, str) or not fullmatch(r"[a-f0-9]{64}", seal)
                or not isinstance(features, (tuple, list)) or not features
                or not all(is_manual_mark(row) and not isinstance(row, Mapping) for row in features)):
            raise ValueError("ROOT_MARKING_STORE_RECORD_INVALID")
        records[owner] = {"source_sha256": seal, "features": deepcopy(tuple(features))}
    if raw["schema_version"] == _QUANTITY_SCHEMA and not any(
        fullmatch(_QUANTITY_OWNER_PATTERN, owner) for owner in records
    ):
        raise ValueError("ROOT_MARKING_STORE_SCHEMA_INVALID")
    return {"schema_version": raw["schema_version"], "records": records}


def _root_store(snapshot):
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    return normalize_workspace_root_marking_store(
        snapshot.get(ROOT_MARKING_STORE_KEY, nested.get(ROOT_MARKING_STORE_KEY)),
    )


def project_operator_detached_root_marking_count(snapshot):
    """Count saved marks' former owners, not guessed part names or ink."""
    records = _root_store(snapshot)["records"]
    if not records:
        return 0
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    present = snapshot.get("existing_parts", nested.get("existing_parts", ())) or ()
    bound = {resolve_workspace_physical_root_owner(snapshot, key) for key in present}
    return len(records.keys() - bound)


def read_workspace_marking_owner_record(snapshot, owner_id):
    """Read prior records without reattaching legacy role features or migrating scoped marks."""
    if isinstance(owner_id, str) and owner_id.startswith("root-owner:"):
        return _root_store(snapshot)["records"].get(owner_id)
    from .operator_scoped_base_plate_marks import normalize_scoped_base_plate_marks
    return deepcopy(normalize_scoped_base_plate_marks(snapshot).get(owner_id))


@dataclass(frozen=True)
class WorkspaceOwnerMarkingDraft:
    part_key: str
    owner_id: str
    source_sha256: str
    saved_marks: tuple
    _saved_record: object


@dataclass(frozen=True)
class WorkspaceOwnerMarkingUpdate:
    part_key: str
    owner_id: str
    source_sha256: str
    _previous: dict
    _accepted_marks: tuple
    _target_source_sha256: str


def open_workspace_owner_marking_draft(snapshot, receipt):
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if not isinstance(receipt, SelectedPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    if (receipt.owner_id is None
            or resolve_workspace_physical_root_owner(snapshot, receipt.part_key) != receipt.owner_id):
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    seal = receipt.source_sha256
    if not isinstance(seal, str) or not fullmatch(r"[a-f0-9]{64}", seal):
        raise ValueError("ROOT_MARKING_SOURCE_INVALID")
    record = read_workspace_marking_owner_record(snapshot, receipt.owner_id)
    if record is not None and record["source_sha256"] != seal:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    marks = () if record is None else receipt.validate(record["features"])
    return WorkspaceOwnerMarkingDraft(receipt.part_key, receipt.owner_id, seal, marks, record)


def _target_receipt(current, prospective, expected_seal=None):
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    target = current if prospective is None else prospective
    if not isinstance(target, SelectedPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    if (target.part_key != current.part_key or target.owner_id != current.owner_id
            or target.output_capability != current.output_capability):
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    if expected_seal is not None and target.source_sha256 != expected_seal:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    return target


def prepare_workspace_owner_marking_commit(snapshot, opened, current_receipt, marks, *, proposed_receipt=None):
    """Validate whole draft against fresh stock and return detached compare-and-swap."""
    if not isinstance(opened, WorkspaceOwnerMarkingDraft):
        raise ValueError("ROOT_MARKING_DRAFT_REQUIRED")
    # Owner drift takes precedence over a replaced board's unreadable stock.
    if resolve_workspace_physical_root_owner(snapshot, opened.part_key) != opened.owner_id:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if not isinstance(current_receipt, SelectedPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    if (current_receipt.owner_id != opened.owner_id
            or current_receipt.part_key != opened.part_key):
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    current = open_workspace_owner_marking_draft(snapshot, current_receipt)
    if current.source_sha256 != opened.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    if current._saved_record != opened._saved_record:
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    target = _target_receipt(current_receipt, proposed_receipt)
    accepted = tuple(target.validate(marks))
    previous = _root_store(snapshot)
    return WorkspaceOwnerMarkingUpdate(
        opened.part_key, opened.owner_id, opened.source_sha256, previous, accepted, target.source_sha256,
    )


def apply_workspace_owner_marking_commit(snapshot, update, current_receipt, proposed_receipt=None):
    """Recompare authoritative owner and full ledger before one owner-state assignment."""
    if not isinstance(update, WorkspaceOwnerMarkingUpdate):
        raise ValueError("ROOT_MARKING_UPDATE_REQUIRED")
    if resolve_workspace_physical_root_owner(snapshot, update.part_key) != update.owner_id:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    current = open_workspace_owner_marking_draft(snapshot, current_receipt)
    if current.owner_id != update.owner_id or current.part_key != update.part_key:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    if current.source_sha256 != update.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    previous = _root_store(snapshot)
    if previous != update._previous:
        raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
    # Apply only the one validated owner's record, never a caller-provided
    # replacement ledger that could alter other physical parts.
    target = _target_receipt(current_receipt, proposed_receipt, update._target_source_sha256)
    accepted = tuple(target.validate(update._accepted_marks))
    if accepted:
        previous["records"][update.owner_id] = {
            "source_sha256": target.source_sha256, "features": accepted,
        }
    else:
        previous["records"].pop(update.owner_id, None)
    return normalize_workspace_root_marking_store(previous)


@dataclass(frozen=True)
class WorkspaceInitialOwnerMarkingUpdate:
    part_key: str
    source_sha256: str
    _previous: dict
    _marks: tuple
    _target_source_sha256: str


def prepare_workspace_initial_owner_marking_commit(snapshot, opened, current, marks, *, proposed_receipt=None):
    """Validate initial legacy Confirm without allocating any persistent owner."""
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if not isinstance(opened, SelectedPhysicalMarkingReceipt) or not isinstance(current, SelectedPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    if (opened.owner_id is not None or current.owner_id is not None
            or current.part_key != opened.part_key
            or resolve_workspace_physical_root_owner(snapshot, opened.part_key) is not None):
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    if (opened.output_capability not in {"existing_normal", "verified_normal"}
            or current.output_capability != opened.output_capability):
        raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
    if current.source_sha256 != opened.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    target = _target_receipt(current, proposed_receipt)
    accepted = tuple(target.validate(marks))
    if not accepted:
        return None  # Confirm of an untouched legacy modal must not mint.
    return WorkspaceInitialOwnerMarkingUpdate(
        current.part_key, current.source_sha256, _root_store(snapshot), accepted, target.source_sha256,
    )


def apply_initial_workspace_owner_marking_commit(workspace, snapshot, update, current, proposed_receipt=None):
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if not isinstance(current, SelectedPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    # Retest before assigning the two stores as a single workspace mutation.
    if current.owner_id is not None or resolve_workspace_physical_root_owner(snapshot, update.part_key) is not None:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    if current.part_key != update.part_key or current.source_sha256 != update.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    if current.output_capability not in {"existing_normal", "verified_normal"}:
        raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
    previous = _root_store(snapshot)
    if previous != update._previous:
        raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
    target = _target_receipt(current, proposed_receipt, update._target_source_sha256)
    accepted = tuple(target.validate(update._marks))
    if not accepted:
        raise ValueError("PHYSICAL_ROOT_FIRST_MARK_REQUIRED")
    occupancy = workspace._propose_marked_legacy_root(current.part_key, snapshot["model"])
    owner = occupancy[update.part_key]["owner_id"]
    previous["records"][owner] = {"source_sha256": target.source_sha256, "features": accepted}
    return occupancy, normalize_workspace_root_marking_store(previous)


def selected_workspace_owner_marking_keys(snapshot, flags):
    """Only active current-owner records for the original selected intents."""
    from .manufacturing_export_selection import (
        normalize_operator_selected_export_flags, receiving_export_part_selected,
    )

    store = _root_store(snapshot)["records"]
    if not store:
        return ()
    flags = normalize_operator_selected_export_flags(flags)
    # Version-bound ink is handled only by the canonical quantity stage.
    # Other output routes must not silently emit the same stock unmarked.
    scoped_roots = {owner.split(":", 2)[2] for owner in store if owner.startswith("quantity-owner:")}
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    parts = snapshot.get("existing_parts", nested.get("existing_parts", ()))
    if snapshot.get("active_mode") != "quantity" and any(
            receiving_export_part_selected(key, flags)
            and resolve_workspace_physical_root_owner(snapshot, key) in scoped_roots for key in (parts or ())):
        raise ValueError("OWNER_MARKING_QUANTITY_VERSION_EXPORT_REQUIRES_QUANTITY_MODE")
    return tuple(key for key in (parts or ()) if receiving_export_part_selected(key, flags)
                 and (resolve_workspace_physical_root_owner(snapshot, key) in store
                      or resolve_workspace_physical_root_owner(snapshot, key) in scoped_roots))


def require_existing_normal_owner_marking_route(snapshot, flags, *, ordinary):
    keys = selected_workspace_owner_marking_keys(snapshot, flags)
    if keys and ordinary is not True:
        raise ValueError("ROOT_MARKING_EXISTING_NORMAL_ROUTE_REQUIRED: " + ", ".join(keys))
    return keys


def with_selected_workspace_owner_markings(snapshot, geometry, keys):
    """Overlay confirmed ink in Engine, not the GUI, before original verified DXF."""
    from dataclasses import replace
    from .operator_selected_marking_receipt import open_selected_owner_receipt, prepare_confirmed_selected_marking

    changes = {}
    for key in keys:
        # A selected active record must never be silently dropped because
        # the requested canonical inventory no longer contains the part.
        receipt = open_selected_owner_receipt(snapshot, geometry, key)
        if receipt.output_capability != "existing_normal":
            raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
        draft = open_workspace_owner_marking_draft(snapshot, receipt)
        if not draft.saved_marks:
            raise ValueError("PHYSICAL_MARKING_CONFIRMED_MARKS_REQUIRED")
        changes[key], _ = prepare_confirmed_selected_marking(
            receipt, draft.saved_marks, lambda: (snapshot, geometry),
        )
    if not changes:
        return geometry
    return replace(geometry, parts=tuple(
        replace(part, render_data=changes[part.part_key]) if part.part_key in changes else part
        for part in geometry.parts
    ))
