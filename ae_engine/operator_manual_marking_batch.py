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


def _marking_source_signature(render):
    from .operator_manual_marking import (
        MANUAL_MARK_SOURCE, is_manual_mark, verify_manual_marking_output,
    )
    from .operator_manual_marking_groups import MANUAL_GROUP_SOURCE

    scene = getattr(render, "scene", None)
    meta = getattr(render, "metadata", None) or {}
    if not isinstance(meta, Mapping) or scene is None:
        raise ValueError("MANUAL_BATCH_SELECTED_RENDER_UNRESOLVED")
    authored = meta.get("manual_marking_v1_features") or ()
    owned = tuple(
        row for row in getattr(scene, "primitives", ()) or ()
        if getattr(row, "semantic_id", None) == MANUAL_MARK_SOURCE
        or getattr(row, "source_type", None) in (MANUAL_MARK_SOURCE, MANUAL_GROUP_SOURCE)
    )
    if not authored and not owned:
        return None

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

    selected: tuple[tuple[str, object, str, str], ...]

    def assert_current(self):
        for output_key, render, stable_id, digest in self.selected:
            current = _marking_source_signature(render)
            if current != (stable_id, digest):
                raise ValueError(
                    "MANUAL_BATCH_SELECTED_SOURCE_CHANGED:" + output_key
                )


def witness_selected_manual_marking_rows(rows):
    """Capture only selected, uniquely resolved real physical sheets.

    Rows: (physical output identity, PartRenderData). Namespace/Set/Bay may
    prefix physical ID; bare matching role in another scope is not accepted.
    """
    selected = []
    seen = set()
    for key, render in tuple(rows):
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError("MANUAL_BATCH_SELECTED_PHYSICAL_ID_AMBIGUOUS")
        seen.add(key)
        proof = _marking_source_signature(render)
        if proof is None:
            continue
        stable, digest = proof
        if key != stable and not key.endswith(":" + stable):
            raise ValueError("MANUAL_BATCH_SELECTED_PHYSICAL_ID_MISMATCH:" + key)
        selected.append((key, render, stable, digest))
    return SelectedManualMarkingWitness(tuple(selected))
