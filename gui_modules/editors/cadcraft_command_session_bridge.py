"""#1959: verify fresh CADCraft drawing, stage only in original WHD Hole Editor.

CADCraft's DXF is NOT a manufacturing file or source of truth. Before
staging, it must match WHD's original resolved Feature geometry exactly.
The existing Phase6HoleEditorSession owns preview, cancel, confirm, undo.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from ae_engine import manufacturing_api

from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError

_MAX_EXCHANGE_BYTES = manufacturing_api.CADCRAFT_MAX_EXCHANGE_BYTES


def _polygon(feature, width: float, height: float):
    """Legacy bridge forwards canonical WHD feature footprints to Engine."""
    return manufacturing_api.cadcraft_feature_footprint_polygon(feature, width, height)


@dataclass
class CadcraftSessionStage:
    """Transient preview of *WHD* source features, not DXF-derived authority."""
    session: Phase6HoleEditorSession
    output: Path
    output_sha256: str
    context_key: str
    preview_features: tuple
    active: bool = True

    def _assert_same_preview(self) -> None:
        if not self.active:
            raise CadcraftCommandProofError("STAGE_ALREADY_RESOLVED")
        snapshot = self.session.snapshot()
        if (snapshot.context_key != self.context_key or
                not snapshot.active_edit or snapshot.features != self.preview_features):
            raise CadcraftCommandProofError("STALE_OR_MODIFIED_WHD_SESSION")
        try:
            digest = sha256(self.output.read_bytes()).hexdigest()
        except OSError as exc:
            raise CadcraftCommandProofError("CADCRAFT_OUTPUT_MISSING") from exc
        if digest != self.output_sha256:
            raise CadcraftCommandProofError("CADCRAFT_OUTPUT_CHANGED_AFTER_VALIDATION")

    def confirm(self):
        """Explicit user confirmation only. Invalid proof rolls back *this* draft."""
        try:
            self._assert_same_preview()
        except CadcraftCommandProofError:
            # A tampered/missing CADCraft file must not leave a valid-looking
            # transient preview for some later unrelated Confirm All click.
            snapshot = self.session.snapshot()
            if (snapshot.context_key == self.context_key and snapshot.active_edit
                    and snapshot.features == self.preview_features):
                self.session.execute(HoleEditorAction.cancel_active())
                self.active = False
            raise
        state = self.session.execute(HoleEditorAction.commit_active(keep_selected=False))
        self.active = False
        return state

    def cancel(self):
        """Discard transient staged changes without touching persisted WHD data."""
        if not self.active:
            raise CadcraftCommandProofError("STAGE_ALREADY_RESOLVED")
        if self.session.active_context_key != self.context_key:
            raise CadcraftCommandProofError("WHD_CONTEXT_CHANGED_CANNOT_CANCEL")
        state = self.session.execute(HoleEditorAction.cancel_active())
        self.active = False
        return state


def stage_verified_cadcraft_drawing(
    *, output: Path, whd_candidates: Sequence,
    session: Phase6HoleEditorSession, surface, width: float, height: float,
) -> CadcraftSessionStage:
    """Fail closed before any write, then use Session's reversible preview_all.

    WHD feature candidates must already come from verified WHD finished-face
    coordinates. We never infer manufacturing layers/holes from arbitrary CADCraft.
    """
    if not isinstance(session, Phase6HoleEditorSession):
        raise TypeError("WHD_PHASE6_SESSION_REQUIRED")
    if session.has_active_edit:
        raise CadcraftCommandProofError("PREEXISTING_ACTIVE_EDIT")
    # Session remains the only transaction owner; Engine verifies all
    # finished-face geometry and independent CADCraft DXF proof.
    current = session.snapshot()
    candidates = tuple(whd_candidates)
    checked_hash = manufacturing_api.verify_cadcraft_verified_candidate_stage(
        output, candidates, current.features, surface, width, height,
    )
    if session.snapshot() != current:
        raise CadcraftCommandProofError("WHD_SESSION_CHANGED_DURING_PROOF")

    intended = current.features + candidates
    session.execute(HoleEditorAction.preview_all(intended))
    return CadcraftSessionStage(
        session=session, output=output, output_sha256=checked_hash,
        context_key=current.context_key, preview_features=intended,
    )
