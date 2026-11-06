"""#1959 CADCraft isolated DXF -> WHD existing Session (moves and new holes).

One specific WHD-created isolated drawing, exact original feature order and
unchanged original shapes/dimensions. New geometry is admitted only after strict
unit/shape/physical boundary/collision checks and explicit WHD confirmation.
CADCraft is never the manufacturing source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


from ae_engine import manufacturing_api
from gui_modules.editors.cadcraft_command_session_bridge import (
    CadcraftSessionStage, _MAX_EXCHANGE_BYTES,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError


@dataclass(frozen=True)
class ManualReturnTicket:
    """Live, editor-owned provenance. Never loaded from the untrusted DXF."""
    session: Phase6HoleEditorSession
    output: Path
    original_sha256: str
    context_key: str
    original: tuple
    surface: object
    width: float
    height: float


@dataclass
class ManualReturnPreview:
    stage: CadcraftSessionStage
    moves: tuple[tuple[int, float, float], ...]
    additions: tuple[object, ...] = ()

    def confirm(self):
        return self.stage.confirm()

    def cancel(self):
        return self.stage.cancel()


def _read_limited(path: Path) -> bytes:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= _MAX_EXCHANGE_BYTES:
            raise CadcraftCommandProofError("INVALID_EXCHANGE_FILE_SIZE")
        data = path.read_bytes()
    except OSError as exc:
        raise CadcraftCommandProofError("CADCRAFT_EXCHANGE_NOT_READABLE") from exc
    if not 0 < len(data) <= _MAX_EXCHANGE_BYTES:
        raise CadcraftCommandProofError("INVALID_EXCHANGE_FILE_SIZE")
    return data


def create_manual_return_ticket(*, output: Path, features, session,
                                surface, width: float, height: float):
    """Issue provenance only for the exact freshly proven WHD->CADCraft DXF."""
    if not isinstance(session, Phase6HoleEditorSession):
        raise CadcraftCommandProofError("WHD_PHASE6_SESSION_REQUIRED")
    snapshot = session.snapshot()
    originals = tuple(features)
    if (session.has_active_edit or len(originals) > 100
            or snapshot.features != originals or not all(map(manufacturing_api.cadcraft_manual_feature_eligible, originals))):
        raise CadcraftCommandProofError("UNSUPPORTED_OR_DIRTY_WHD_SOURCE")
    w, h = float(width), float(height)
    if not all(manufacturing_api.cadcraft_manual_finite_positive(v) for v in (w, h)):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    path = Path(output).resolve(strict=True)
    data = _read_limited(path)
    manufacturing_api.verify_cadcraft_manual_ticket_seed(
        path, originals, surface, w, h,
    )
    if sha256(_read_limited(path)).digest() != sha256(data).digest():
        raise CadcraftCommandProofError("CADCRAFT_FILE_CHANGED_DURING_TICKET")
    return ManualReturnTicket(
        session, path, sha256(data).hexdigest(), snapshot.context_key,
        originals, surface, w, h,
    )


def _dxf_moves(output: Path, original: tuple, surface, width, height):
    """Compatibility: the Engine alone validates CADCraft DXF return geometry."""
    return manufacturing_api.project_cadcraft_manual_return_changes(
        output, original, surface, width, height,
    )


def stage_manual_cadcraft_return(ticket: ManualReturnTicket) -> ManualReturnPreview:
    """Fail closed before preview_all, then verify unchanged DXF at Confirm."""
    session = ticket.session
    snapshot = session.snapshot()
    if (session.has_active_edit or snapshot.context_key != ticket.context_key
            or snapshot.features != ticket.original):
        raise CadcraftCommandProofError("STALE_OR_MODIFIED_WHD_SESSION")
    data = _read_limited(ticket.output)
    digest = sha256(data).hexdigest()
    if digest == ticket.original_sha256:
        raise CadcraftCommandProofError("CADCRAFT_DRAWING_NOT_EDITED")
    updated, moves, additions = _dxf_moves(
        ticket.output, ticket.original, ticket.surface, ticket.width, ticket.height
    )
    if sha256(_read_limited(ticket.output)).hexdigest() != digest:
        raise CadcraftCommandProofError("CADCRAFT_OUTPUT_CHANGED_DURING_VALIDATION")
    if session.snapshot() != snapshot:
        raise CadcraftCommandProofError("WHD_SESSION_CHANGED_DURING_VALIDATION")
    session.execute(HoleEditorAction.preview_all(updated))
    stage = CadcraftSessionStage(
        session=session, output=ticket.output, output_sha256=digest,
        context_key=ticket.context_key, preview_features=updated,
    )
    return ManualReturnPreview(stage=stage, moves=moves, additions=additions)
