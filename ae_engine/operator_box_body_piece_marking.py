"""Ordinary first-mark confirmation for a Receiving structural sheet.

Use the existing stock proof and workspace marking ledger. This is not an
export route: ordinary batch integration must witness those same saved marks.
"""
from dataclasses import dataclass

from .box_body_structure_state import (
    _SIDE_BACK_PIECES,
    propose_box_body_piece_marking_occupancy,
    read_box_body_piece_marking_owner,
)
from .cabinet_types.policy import canonical_family_name
from .operator_persisted_marking_candidate import (
    _verify_original,
    require_ordinary_selected_marking_stock,
)
from .operator_physical_sheet_marking_preview import _validate_selected_marks
from .operator_root_marking_store import (
    _root_store,
    normalize_workspace_root_marking_store,
)
from .operator_selected_marking_receipt import _source_sha256
from .physical_sheet_editor_context import resolve_box_body_piece_manufacturing_witness
from .workspace_state import resolve_workspace_physical_root_owner


@dataclass(frozen=True)
class BoxBodyPieceMarkingDraft:
    part_key: str
    owner_id: str | None
    physical_key: str
    source_sha256: str
    saved_marks: tuple


def supports_box_body_piece_marking_editor(snapshot, part_key):
    return (canonical_family_name(snapshot) == "受電箱"
            and snapshot.get("active_mode", "set_bay") == "set_bay"
            and not snapshot.get("receiving_quantity_box")
            and part_key in _SIDE_BACK_PIECES)


def _scope(snapshot, part_key):
    if not supports_box_body_piece_marking_editor(snapshot, part_key):
        raise ValueError("BOX_BODY_PIECE_MARKING_SCOPE_UNSUPPORTED")


def _read(snapshot, geometry, part_key):
    _scope(snapshot, part_key)
    owner = read_box_body_piece_marking_owner(snapshot["box_body_structure"], part_key)
    if owner and any(resolve_workspace_physical_root_owner(snapshot, key) == owner
                     for key in snapshot.get("existing_parts", ())):
        raise ValueError("BOX_BODY_PIECE_MARKING_DUPLICATE_OWNER")
    physical_key, render = resolve_box_body_piece_manufacturing_witness(geometry, part_key)
    selected = require_ordinary_selected_marking_stock(snapshot, geometry, physical_key)
    if selected._render is not render:
        raise ValueError("BOX_BODY_MARKING_PHYSICAL_IDENTITY_UNPROVEN")
    seal = _source_sha256(snapshot, selected)
    record = _root_store(snapshot)["records"].get(owner)
    if record is not None and record["source_sha256"] != seal:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    marks = () if record is None else _validate_selected_marks(
        selected, record["features"], allow_shapes=True,
    )
    return BoxBodyPieceMarkingDraft(part_key, owner, physical_key, seal, marks), selected


def open_box_body_piece_marking_draft(snapshot, geometry, part_key):
    draft, selected = _read(snapshot, geometry, part_key)
    _verify_original(selected._render)
    return draft


def open_box_body_piece_marking_modal_source(snapshot, geometry, part_key):
    """Use the existing verified tools on one proven structural child."""
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    from .physical_sheet_editor_context import resolve_physical_sheet_editor_context

    draft, selected = _read(snapshot, geometry, part_key)
    _verify_original(selected._render)
    body, = (part.render_data for part in geometry.parts if part.part_key == "box_body")
    context = resolve_physical_sheet_editor_context(part_key, body)
    if context.render_data is not selected._render:
        raise ValueError("BOX_BODY_MARKING_PHYSICAL_IDENTITY_UNPROVEN")
    return draft, SelectedPhysicalMarkingReceipt(
        part_key, draft.owner_id, selected, "verified_normal", draft.source_sha256,
        _editor_context=context,
    )


def prepare_box_body_piece_marking_commit(snapshot, geometry, opened, marks):
    """Return verified structure and ledger together, without mutating either."""
    if not isinstance(opened, BoxBodyPieceMarkingDraft):
        raise ValueError("BOX_BODY_PIECE_MARKING_DRAFT_REQUIRED")
    _scope(snapshot, opened.part_key)
    structure = snapshot["box_body_structure"]
    if read_box_body_piece_marking_owner(structure, opened.part_key) != opened.owner_id:
        raise ValueError("ROOT_MARKING_OWNER_STALE")
    current, selected = _read(snapshot, geometry, opened.part_key)
    if current != opened:
        raise ValueError("ROOT_MARKING_DRAFT_STALE")
    ink = _validate_selected_marks(selected, marks, allow_shapes=True)
    _verify_original(selected._render)
    ledger = _root_store(snapshot)
    owner = current.owner_id
    if ink:
        if owner is None:
            structure = propose_box_body_piece_marking_occupancy(
                structure, opened.part_key, geometry,
            )
            owner = read_box_body_piece_marking_owner(structure, opened.part_key)
            if owner in ledger["records"] or any(
                resolve_workspace_physical_root_owner(snapshot, key) == owner
                for key in snapshot.get("existing_parts", ())
            ):
                raise ValueError("BOX_BODY_PIECE_MARKING_DUPLICATE_OWNER")
        ledger["records"][owner] = {"source_sha256": opened.source_sha256, "features": ink}
    elif owner is not None:
        ledger["records"].pop(owner, None)
    if ledger["schema_version"] == 2 and not any(
        key.startswith("quantity-owner:") for key in ledger["records"]
    ):
        ledger["schema_version"] = 1
    return structure, normalize_workspace_root_marking_store(ledger)


def box_body_piece_marking_owner(snapshot, part_key):
    """A recorded derived owner is not an ordinary root or a release grant."""
    if part_key not in _SIDE_BACK_PIECES or canonical_family_name(snapshot) != "受電箱":
        return None
    nested = snapshot.get("workspace") or {}
    return read_box_body_piece_marking_owner(
        snapshot.get("box_body_structure", nested.get("box_body_structure")), part_key,
    )


def read_persisted_box_body_piece_evidence(snapshot, geometry, part_key):
    """Adapt the existing verified writer witness to an exact physical row."""
    from .operator_persisted_marking_candidate import VerifiedOwnerMarkingCandidate
    from .operator_physical_sheet_marking_preview import project_selected_physical_marking_features
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt

    draft, selected = _read(snapshot, geometry, part_key)
    if not draft.owner_id or not draft.saved_marks:
        raise ValueError("OWNER_MARKING_PERSISTED_RECORD_REQUIRED")
    receipt = SelectedPhysicalMarkingReceipt(
        draft.physical_key, draft.owner_id, selected, "verified_normal", draft.source_sha256,
    )
    ink = project_selected_physical_marking_features(
        selected, draft.saved_marks, _allow_shapes=True,
    )
    return receipt, draft, VerifiedOwnerMarkingCandidate(
        part_key, draft.owner_id, draft.source_sha256, ink, False,
    )
