# -*- coding: utf-8 -*-
"""Engine-owned Receiving side/back split Fold, topology and physical rear contract.

External clients supply canonical *outside* dimensions. This module delegates
to the existing Receiving Family/Fold authority; it never invents alternate
back-width compensation, fixed slots, or a second source DXF formula.
"""
from __future__ import annotations

from dataclasses import replace
import math
from collections.abc import Mapping

from .contracts import BoxBodyPartSpec

_REQUIRED = {"model", "w", "h", "d", "t", "fw", "zl1", "zl2", "zr2"}
_REAR_MODES = frozenset({"FULL", "BACK_OPENING"})
_FOLD_KEYS = (
    "zl1", "zl2", "fw_left", "d_left", "w",
    "d_right", "fw_right", "zr2",
)


def _canonical_receiving_split_input(snapshot: Mapping) -> dict:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _REQUIRED or snapshot.get("model") != "受電箱":
        raise ValueError("Receiving split source must contain exact confirmed outside inputs")
    if any(type(snapshot[k]) not in (int, float) or not math.isfinite(snapshot[k])
           for k in _REQUIRED - {"model"}):
        raise ValueError("Receiving split outside dimensions/Fold inputs must be finite numbers")
    values = {k: float(snapshot[k]) for k in _REQUIRED - {"model"}}
    w, h, d, t, fw = (values[k] for k in ("w", "h", "d", "t", "fw"))
    if (min(w, h, d, t, fw) <= 0 or w <= 4 * t or h <= 2 * t
            or d <= 4 * t or fw <= 2 * t or fw >= min(w, d)):
        raise ValueError("Receiving split physical outside dimensions impossible")
    return {"model": "受電箱", **values}


def resolve_receiving_split_box_body_spec(snapshot: Mapping) -> BoxBodyPartSpec:
    """Resolve the genuine 8-segment side/back physical manufacturing request."""
    from .cabinet_types import receiving
    from .cabinet_types.policy import resolve_box_body_back_panel_contract
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    source = _canonical_receiving_split_input(snapshot)
    rows = build_box_body_profile(source)
    if (tuple(row.get("phase6_key") for row in rows) != _FOLD_KEYS
            or any(not math.isfinite(float(row["len"])) or float(row["len"]) <= 0
                   for row in rows)):
        raise ValueError("Receiving 8-segment D-W-D Fold source changed")
    fold = profile_to_fold_segments(rows)
    state = receiving.resolve_box_body_structure_state(None)
    contract = resolve_box_body_back_panel_contract(
        "受電箱", source, structure_state=state,
    )
    if not isinstance(contract, Mapping) or contract.get("mode") != "FULL":
        raise ValueError("Receiving canonical FULL rear contract unavailable")
    return BoxBodyPartSpec(
        width=source["w"], height=source["h"], depth=source["d"],
        thickness=source["t"], frame_width=source["fw"], model_name="受電箱",
        fold_profile=fold, structure_state=state, back_panel_contract=contract,
    )


def select_receiving_split_rear_mode(
    spec: BoxBodyPartSpec, snapshot: Mapping, *, mode: str,
) -> BoxBodyPartSpec:
    """Engine-only rear mode selection; a Worker may validate but cannot derive CUTTING."""
    from .cabinet_types.policy import resolve_box_body_back_panel_contract
    from phase6_box_body_structure import back_panel_mode, set_side_back_back_panel_mode

    source = _canonical_receiving_split_input(snapshot)
    if (not isinstance(spec, BoxBodyPartSpec) or spec.model_name != "受電箱"
            or mode not in _REAR_MODES or not spec.fold_profile
            or any(getattr(spec, field) != source[key] for field, key in (
                ("width", "w"), ("height", "h"), ("depth", "d"),
                ("thickness", "t"), ("frame_width", "fw"),
            ))):
        raise ValueError("Receiving rear-mode request does not match its physical Fold source")
    state = set_side_back_back_panel_mode(spec.structure_state, mode)
    if back_panel_mode(state).value != mode:
        raise ValueError("Receiving rear-panel source mode was not persisted")
    contract = resolve_box_body_back_panel_contract(
        "受電箱", source, structure_state=state,
    )
    if (contract.get("mode") != mode
            or len(tuple(contract.get("fixed_slot_profiles") or ())) != 4
            or (contract.get("opening") is not None) != (mode == "BACK_OPENING")):
        raise ValueError("Receiving certified rear CUTTING contract missing")
    return replace(spec, structure_state=state, back_panel_contract=contract)
