"""#3414: bounded witness of SELECTED saved manual-marking intent.

A selected physical sheet's saved MARKING is manufacturing intent even where
its dash has no ink.  This witness is attached only to already selected
Engine-resolved flats and rechecks that exact live render before atomic output
publication. It never grants manufacturing eligibility or resolves Set/Bay.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from collections.abc import Mapping


def _has_saved_manual_intent(render):
    """Pure *presence* check; no source/Family/manufacturing admission.

    Even a selected unmarked NFB/PAD preview must first reach its original
    manufacturing reject gate. A late manual-marking field or actual ink,
    including malformed stored content, is a source change, not a new gate.
    """
    from .operator_manual_marking import MANUAL_MARK_SOURCE
    from .operator_manual_marking_groups import MANUAL_GROUP_SOURCE

    metadata = getattr(render, "metadata", None)
    if isinstance(metadata, Mapping) and "manual_marking_v1_features" in metadata:
        authored = metadata["manual_marking_v1_features"]
        # A malformed field (including a scalar/empty string) is still a
        # present source, never silently treated as an empty valid feature list.
        if authored is not None and not (
            isinstance(authored, (tuple, list)) and len(authored) == 0
        ):
            return True
    scene = getattr(render, "scene", None)
    return any(
        getattr(row, "semantic_id", None) == MANUAL_MARK_SOURCE
        or getattr(row, "source_type", None) in
        (MANUAL_MARK_SOURCE, MANUAL_GROUP_SOURCE)
        for row in tuple(getattr(scene, "primitives", ()) or ())
    )


def _marking_source_signature(render):
    from .operator_manual_marking import (
        MANUAL_MARK_SOURCE, is_manual_mark, verify_manual_marking_output,
    )
    from .operator_manual_marking_groups import MANUAL_GROUP_SOURCE

    if not _has_saved_manual_intent(render):
        return None
    scene = getattr(render, "scene", None)
    meta = getattr(render, "metadata", None) or {}
    if scene is None or not isinstance(meta, Mapping):
        raise ValueError("MANUAL_BATCH_SELECTED_RENDER_UNRESOLVED")
    authored = meta.get("manual_marking_v1_features") or ()

    # Reuse the *whole original* source/CUTTING/hole and stored-ink gate.
    # No new GUI geometry, partial dash-only validation, or family bypass.
    verify_manual_marking_output(render)
    if not authored or not all(is_manual_mark(item) for item in authored):
        raise ValueError("MANUAL_BATCH_SAVED_INTENT_MISSING")

    stable = meta.get("stable_id")
    if not isinstance(stable, str) or not stable:
        raise ValueError("MANUAL_BATCH_PHYSICAL_OWNER_MISSING")
    topology = getattr(render, "unfolded_topology", None)
    material = getattr(render, "material", None)
    if material is None or topology is None:
        raise ValueError("MANUAL_BATCH_PHYSICAL_SOURCE_MISSING")
    # Dataclass repr is exact within this process; material WKB avoids GEOS
    # object identity, and authored source includes *complete dashed arms*.
    source = (
        stable,
        repr(topology),
        repr(tuple(authored)),
        repr(tuple(scene.primitives)),
        material.wkb,
    )
    fingerprint = sha256()
    for value in source:
        data = value if isinstance(value, bytes) else value.encode("utf-8")
        fingerprint.update(len(data).to_bytes(8, "big"))
        fingerprint.update(data)
    return stable, fingerprint.hexdigest()


@dataclass(frozen=True)
class SelectedManualMarkingWitness:
    """Verified physical owner + actual render object, never a name-only key."""

    selected: tuple[tuple[str, object, str | None, str | None], ...]

    def assert_current(self):
        for output_key, render, stable_id, digest in self.selected:
            if stable_id is None:
                # Snapshot the ABSENCE of saved manual ink too. Never run
                # the full newly-invented marking admission gate on a
                # previously unmarked sheet; detect only absent→present.
                if _has_saved_manual_intent(render):
                    raise ValueError(
                        "MANUAL_BATCH_SELECTED_SOURCE_CHANGED:" + output_key
                    )
                continue
            current = _marking_source_signature(render)
            if current != (stable_id, digest):
                raise ValueError(
                    "MANUAL_BATCH_SELECTED_SOURCE_CHANGED:" + output_key
                )


def witness_selected_manual_marking_rows(rows):
    """Witness *all* selected flats, including the absence of saved marks.

    Rows contain canonical physical part keys, NEVER a display-panel or
    filename prefix. This function cannot infer Set/Bay/Version from a
    string suffix. Caller must independently own any scoped identity.
    Repeated physical roles in different composed panels are permitted;
    panel labels alone supply no source identity evidence.
    """
    selected = []
    for key, render in tuple(rows):
        # Important: no metadata/scene/Family validation here for unmarked
        # rows. Original NFB/PAD/CUTTING/BEND manufacturing gates own them.
        if not _has_saved_manual_intent(render):
            selected.append((key, render, None, None))
            continue
        proof = _marking_source_signature(render)
        if proof is None:
            raise ValueError("MANUAL_BATCH_SELECTED_RENDER_UNRESOLVED")
        stable, digest = proof
        # A namespace or display label ending in ':base_plate' does NOT
        # prove the selected Set/Bay owner. Fail closed until actual scoped
        # identity was resolved, rather than authorizing by suffix.
        if not isinstance(key, str) or key != stable:
            raise ValueError("MANUAL_BATCH_SELECTED_PHYSICAL_ID_MISMATCH:" + str(key))
        selected.append((key, render, stable, digest))
    return SelectedManualMarkingWitness(tuple(selected))
