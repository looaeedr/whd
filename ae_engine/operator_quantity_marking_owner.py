"""Quantity-version identity for an ordinary physical marking owner."""
from collections.abc import Mapping
from dataclasses import dataclass

from .receiving_quantity_versions import QuantityModel
from .workspace_state import resolve_workspace_physical_root_owner


@dataclass(frozen=True)
class QuantityPhysicalMarkingOwner:
    """Identity only: stock validation and export permission stay separate."""
    version_id: str
    physical_id: str
    root_owner_id: str | None


def resolve_quantity_physical_marking_owner(snapshot, part_key, *, version_id=None):
    return _resolve_quantity_source(snapshot, part_key, version_id=version_id, require_root=True)


def _resolve_quantity_source(snapshot, part_key, *, version_id=None, require_root=False):
    """Resolve from a validated quantity model and a current physical root.

    No legacy root marks are inferred or assigned to a version by this query.
    Quantity and selected UI tab are not part of a board's identity.
    """
    from .cabinet_types.policy import canonical_family_name

    if (not isinstance(snapshot, Mapping) or snapshot.get("active_mode") != "quantity"
            or canonical_family_name(snapshot) != "\u91d1\u5eab\u578b"
            or snapshot.get("receiving_quantity_box")):
        raise ValueError("OWNER_MARKING_QUANTITY_ORDINARY_SCOPE_REQUIRED")
    try:
        model = QuantityModel.from_payload(snapshot.get("quantity"))
    except ValueError as exc:
        raise ValueError("OWNER_MARKING_QUANTITY_SOURCE_INVALID") from exc
    identity = model.selected_version_id if version_id is None else version_id
    if not isinstance(identity, str) or not any(
        row["version_id"] == identity for row in model.snapshot()["versions"]
    ):
        raise ValueError("OWNER_MARKING_QUANTITY_VERSION_SOURCE_MISMATCH")
    from .workspace_state import _ordinary_explicit_root_key
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    parts = snapshot.get("existing_parts", nested.get("existing_parts", ())) or ()
    if part_key not in parts or not _ordinary_explicit_root_key(part_key, snapshot):
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    root = resolve_workspace_physical_root_owner(snapshot, part_key)
    if require_root and root is None:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    return QuantityPhysicalMarkingOwner(identity, part_key, root)


def _record_key(owner):
    return f"quantity-owner:{owner.version_id}:{owner.root_owner_id}"


def read_quantity_physical_marking(snapshot, part_key, *, version_id=None):
    """Never inherit unscoped or other-version ink."""
    from .operator_root_marking_store import _root_store
    owner = _resolve_quantity_source(snapshot, part_key, version_id=version_id)
    return None if owner.root_owner_id is None else _root_store(snapshot)["records"].get(_record_key(owner))


@dataclass(frozen=True)
class _QuantityPhysicalMarkingReceipt:
    owner: QuantityPhysicalMarkingOwner
    stock: object
    saved_record: object


def open_quantity_physical_marking(snapshot, geometry, part_key):
    """Validate the live selected version's unmarked stock through the existing sink gate."""
    from .operator_selected_marking_receipt import open_selected_ordinary_marking_modal_source
    owner = _resolve_quantity_source(snapshot, part_key)
    quantity = QuantityModel.from_payload(snapshot["quantity"]).snapshot()
    quantity["versions"] = [row for row in quantity["versions"] if row["version_id"] == owner.version_id]
    stock = open_selected_ordinary_marking_modal_source({**snapshot, "quantity": quantity}, geometry, part_key)
    if stock.owner_id != owner.root_owner_id:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    record = read_quantity_physical_marking(snapshot, part_key, version_id=owner.version_id)
    if record is not None and record["source_sha256"] != stock.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    return _QuantityPhysicalMarkingReceipt(owner, stock, record)


def with_confirmed_quantity_physical_marking(snapshot, receipt, marks, *, version_id, geometry):
    """Return a detached ledger update for the currently selected version.

    This storage operation never grants export permission. A receipt from
    another version cannot be reused even when both have identical geometry.
    """
    owner, stock, accepted = _validate_quantity_marking_update(
        snapshot, receipt, marks, version_id=version_id, geometry=geometry,
    )
    if owner.root_owner_id is None:
        raise ValueError("ROOT_MARKING_DURABLE_OWNER_REQUIRED")
    return _update_quantity_marking_ledger(snapshot, owner, stock, accepted)


def _validate_quantity_marking_update(snapshot, receipt, marks, *, version_id, geometry):
    if not isinstance(receipt, _QuantityPhysicalMarkingReceipt):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    owner = _resolve_quantity_source(snapshot, receipt.owner.physical_id)
    if owner.version_id != version_id or owner != receipt.owner:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    current = open_quantity_physical_marking(snapshot, geometry, owner.physical_id)
    stock = current.stock
    if current.saved_record != receipt.saved_record:
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    if stock.source_sha256 != receipt.stock.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    return owner, stock, tuple(stock.validate(marks))


def _update_quantity_marking_ledger(snapshot, owner, stock, accepted):
    from .operator_root_marking_store import _root_store, normalize_workspace_root_marking_store
    ledger = _root_store(snapshot)
    key = _record_key(owner)
    if accepted:
        ledger["records"][key] = {"features": accepted, "source_sha256": stock.source_sha256}
    else:
        ledger["records"].pop(key, None)
    ledger["schema_version"] = 2 if any(k.startswith("quantity-owner:") for k in ledger["records"]) else 1
    return normalize_workspace_root_marking_store(ledger)


def workspace_contains_quantity_physical_markings(snapshot):
    """Whether a validated saved workspace carries any version-bound ink."""
    from .operator_root_marking_store import _root_store
    return any(key.startswith("quantity-owner:") for key in _root_store(snapshot)["records"])


def _selected_version_root_records(snapshot, owner_keys):
    from .operator_root_marking_store import _root_store
    ledger = _root_store(snapshot)
    if ledger["schema_version"] != 2:
        return {}
    live = {row["version_id"] for row in QuantityModel.from_payload(snapshot.get("quantity")).snapshot()["versions"]}
    roots = {resolve_workspace_physical_root_owner(snapshot, key): key for key in owner_keys}
    records = {}
    for key, record in ledger["records"].items():
        if key.startswith("quantity-owner:"):
            _, version, root = key.split(":", 2)
            if version in live and root in roots and root is not None:
                records[(version, roots[root])] = record
    return records


def uses_quantity_physical_marking_editor(snapshot, part_key):
    """Admission of the already owned Vault sheet, never a legacy reassignment."""
    from .operator_root_marking_store import read_workspace_marking_owner_record, _root_store
    try:
        owner = _resolve_quantity_source(snapshot, part_key)
    except ValueError:
        return False
    if owner.root_owner_id is not None and read_workspace_marking_owner_record(snapshot, owner.root_owner_id) is not None:
        return False
    quantity = QuantityModel.from_payload(snapshot["quantity"])
    return quantity.version_count > 1 or (owner.root_owner_id is not None and any(
        k.endswith(":" + owner.root_owner_id) for k in _root_store(snapshot)["records"]
        if k.startswith("quantity-owner:")
    ))


def open_unassigned_quantity_marking_transfer(snapshot, geometry, part_key):
    """Offer a move only on an exact live physical source, never autoassign it."""
    from .operator_root_marking_store import _root_store
    source = _resolve_quantity_source(snapshot, part_key)
    if QuantityModel.from_payload(snapshot["quantity"]).version_count < 2:
        return None
    if _root_store(snapshot)["records"].get(source.root_owner_id) is None:
        return None
    receipt = open_quantity_physical_marking(snapshot, geometry, part_key)
    legacy = _root_store(snapshot)["records"][source.root_owner_id]
    if receipt.saved_record is not None:
        raise ValueError("OWNER_MARKING_QUANTITY_TARGET_ALREADY_MARKED")
    if legacy["source_sha256"] != receipt.stock.source_sha256:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    receipt.stock.validate(legacy["features"])
    return receipt, legacy


def with_transferred_quantity_marking(snapshot, geometry, part_key, opened, *, version_id):
    """Move the unchanged legacy ink atomically to the explicitly confirmed version."""
    from .operator_root_marking_store import _root_store, normalize_workspace_root_marking_store
    fresh = open_unassigned_quantity_marking_transfer(snapshot, geometry, part_key)
    if fresh is None or opened is None:
        raise ValueError("OWNER_MARKING_QUANTITY_LEGACY_OWNER_UNBOUND")
    receipt, legacy = fresh
    before, old_record = opened
    if (receipt.owner != before.owner or receipt.owner.version_id != version_id
            or legacy != old_record or receipt.stock.source_sha256 != before.stock.source_sha256):
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    ledger = _root_store(snapshot)
    ledger["records"][_record_key(receipt.owner)] = ledger["records"].pop(receipt.owner.root_owner_id)
    ledger["schema_version"] = 2
    return normalize_workspace_root_marking_store(ledger)


def quantity_marking_can_offer_legacy_transfer(snapshot, part_key):
    from .operator_root_marking_store import _root_store
    try:
        source = resolve_quantity_physical_marking_owner(snapshot, part_key)
    except ValueError:
        return False
    return (QuantityModel.from_payload(snapshot["quantity"]).version_count > 1
            and source.root_owner_id in _root_store(snapshot)["records"])


def validate_unmarked_quantity_sheet_hole_edit(snapshot, geometry, opened, editing_context, holes):
    """Preserve the old hole-only flow when no active version of the sheet has ink."""
    from . import manufacturing_api as api
    from .operator_manual_marking import is_manual_mark
    from .operator_root_marking_store import _root_store
    current = open_quantity_physical_marking(snapshot, geometry, opened.owner.physical_id)
    if (current.owner != opened.owner or current.saved_record != opened.saved_record
            or current.stock.source_sha256 != opened.stock.source_sha256):
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    key = current.owner.physical_id
    if (_root_store(snapshot)["records"].get(current.owner.root_owner_id) is not None
            or _selected_version_root_records(snapshot, (key,))):
        raise ValueError("OWNER_MARKING_QUANTITY_HOLE_EDIT_REQUIRES_MARK_REVALIDATION")
    accepted = tuple(api.propose_operator_physical_sheet_hole_features(key, editing_context, holes))
    if any(is_manual_mark(row) for row in accepted):
        raise ValueError("ROOT_MARKING_STORE_MARKS_ONLY")
    return accepted


def propose_quantity_marking_and_common_holes(snapshot, opened, editing_context, holes, marks, *, build_batch):
    """Validate all live versions before changing common holes or any marking seal."""
    from copy import deepcopy
    from . import manufacturing_api as api
    from .operator_manual_marking import is_manual_mark
    from .operator_root_marking_store import ROOT_MARKING_STORE_KEY, _root_store, normalize_workspace_root_marking_store

    if not isinstance(opened, _QuantityPhysicalMarkingReceipt) or not callable(build_batch):
        raise ValueError("ROOT_MARKING_STOCK_RECEIPT_REQUIRED")
    key = opened.owner.physical_id
    owner = resolve_quantity_physical_marking_owner(snapshot, key)
    if owner != opened.owner or key not in {"door", "base_plate"}:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    ledger = _root_store(snapshot)
    if owner.root_owner_id in ledger["records"]:
        raise ValueError("OWNER_MARKING_QUANTITY_LEGACY_OWNER_UNBOUND")
    holes = tuple(api.propose_operator_physical_sheet_hole_features(key, editing_context, holes))
    if any(is_manual_mark(row) for row in holes):
        raise ValueError("ROOT_MARKING_STORE_MARKS_ONLY")
    quantity = QuantityModel.from_payload(snapshot["quantity"]).snapshot()
    expected = {row["version_id"]: row["piece_count"] for row in quantity["versions"]}

    def receipts(state):
        result = {}
        for row in build_batch(state).demands:
            if row.physical_id != key:
                continue
            vid = row.version_id
            if (vid in result or vid not in expected or row.piece_count != expected[vid]
                    or row.per_box_count != 1 or row.source_part_id != key):
                raise ValueError("OWNER_MARKING_QUANTITY_SINGLE_OWNER_COUNT_REQUIRED")
            versioned = {**state, "quantity": {**quantity, "selected_version_id": vid}}
            result[vid] = open_quantity_physical_marking(
                versioned, api.selected_normal_marking_inventory(key, row.render_data), key,
            )
        if result.keys() != expected.keys():
            raise ValueError("OWNER_MARKING_QUANTITY_VERSION_SOURCE_MISMATCH")
        return result

    before = receipts(snapshot)
    selected = before[owner.version_id]
    if (selected.owner != opened.owner or selected.saved_record != opened.saved_record
            or selected.stock.source_sha256 != opened.stock.source_sha256):
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    proposed = deepcopy(snapshot)
    proposed["part_features"] = {**(proposed.get("part_features") or {}), key: holes}
    # Each old seal was verified above. Remove the old ledger only from this
    # proposal, so new stock can be opened without treating it as an edit.
    proposed[ROOT_MARKING_STORE_KEY] = {"schema_version": 1, "records": {}}
    after = receipts(proposed)
    for version, receipt in after.items():
        if receipt.owner != before[version].owner:
            raise ValueError("ROOT_MARKING_OWNER_STALE")
        prior = before[version].saved_record
        intent = marks if version == owner.version_id else (() if prior is None else prior["features"])
        ink = tuple(receipt.stock.validate(intent))
        record_key = _record_key(receipt.owner)
        if ink:
            ledger["records"][record_key] = {"source_sha256": receipt.stock.source_sha256, "features": ink}
        else:
            ledger["records"].pop(record_key, None)
    ledger["schema_version"] = 2 if any(k.startswith("quantity-owner:") for k in ledger["records"]) else 1
    return holes, normalize_workspace_root_marking_store(ledger)
