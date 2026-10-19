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

from shapely.geometry import Point, Polygon

from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, ProfileFeature, RectFeature,
    feature_is_strictly_within_surface, resolve_surface_features,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, from_whd_resolved, verify_dxf,
)

_ACCEPTED_TYPES = (CircleFeature, RectFeature, ProfileFeature)
_MAX_EXCHANGE_BYTES = 3_000_000


def _polygon(feature, width: float, height: float) -> Polygon:
    """Build finished-face physical footprints, never from DXF render hints."""
    from ae_engine.sheetmetal_features import feature_finished_point
    from ae_engine.sheetmetal_feature_core import _rotate_local_point
    center = feature_finished_point(feature, width, height)
    if isinstance(feature, CircleFeature):
        return Point(center.x, center.y).buffer(float(feature.diameter) / 2, quad_segs=64)
    if isinstance(feature, RectFeature):
        half_width, half_height = float(feature.width) / 2, float(feature.height) / 2
        local = (
            type(center)(-half_width, -half_height),
            type(center)(half_width, -half_height),
            type(center)(half_width, half_height),
            type(center)(-half_width, half_height),
        )
        points = [center + _rotate_local_point(p, feature.rotation_deg) for p in local]
    elif isinstance(feature, ProfileFeature) and not feature.layered_profiles:
        points = [center + _rotate_local_point(p, feature.rotation_deg)
                  for p in feature.points]
    else:
        raise CadcraftCommandProofError("UNSUPPORTED_EXISTING_FEATURE_GEOMETRY")
    polygon = Polygon([(p.x, p.y) for p in points])
    if not polygon.is_valid or polygon.area <= 1e-8:
        raise CadcraftCommandProofError("INVALID_WHD_FEATURE_FOOTPRINT")
    return polygon


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
    candidates = tuple(whd_candidates)
    if not candidates or len(candidates) > 100:
        raise CadcraftCommandProofError("INVALID_WHD_CANDIDATE_COUNT")
    current = session.snapshot()
    if not all(isinstance(f, _ACCEPTED_TYPES) and f.layer == "CUTTING"
               for f in candidates):
        raise CadcraftCommandProofError("ONLY_VERIFIED_WHD_CUTTING_FEATURES")
    if not all(isinstance(f, _ACCEPTED_TYPES) for f in current.features):
        raise CadcraftCommandProofError("UNKNOWN_EXISTING_WHD_FEATURE")
    try:
        for feature in candidates:
            if not feature_is_strictly_within_surface(surface, feature, width, height):
                raise CadcraftCommandProofError("OUTSIDE_WHD_PHYSICAL_SURFACE")
        footprints = [_polygon(f, width, height) for f in (*current.features, *candidates)]
        offset = len(current.features)
        for index in range(offset, len(footprints)):
            for previous in range(index):
                if footprints[index].intersects(footprints[previous]):
                    raise CadcraftCommandProofError("WHD_FEATURE_COLLISION")
        resolved = tuple(resolve_surface_features(surface, candidates, width, height))
        intent = from_whd_resolved(resolved)
        output = Path(output)
        if output.stat().st_size > _MAX_EXCHANGE_BYTES:
            raise CadcraftCommandProofError("CADCRAFT_EXCHANGE_TOO_LARGE")
        verify_dxf(output, intent)
        checked_hash = sha256(output.read_bytes()).hexdigest()
        # Recheck that we did not lose the selected context during verification.
        if session.snapshot() != current:
            raise CadcraftCommandProofError("WHD_SESSION_CHANGED_DURING_PROOF")
    except (OSError, ValueError, TypeError, IndexError) as exc:
        if isinstance(exc, CadcraftCommandProofError):
            raise
        raise CadcraftCommandProofError("CADCRAFT_STAGE_VALIDATION_FAILED") from exc

    intended = current.features + candidates
    session.execute(HoleEditorAction.preview_all(intended))
    return CadcraftSessionStage(
        session=session, output=output, output_sha256=checked_hash,
        context_key=current.context_key, preview_features=intended,
    )
