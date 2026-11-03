# -*- coding: utf-8 -*-
"""Canonical BoxBody operator inputs -> physical manufacturing PartSpec (#2517).

The existing Family/Topology and EndCap material readback remain authoritative.
No new Fold, rear-panel, corner, relief or DXF formula is defined here.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Mapping

from . import ae
from .box_body_fold_profile import profile_to_fold_segments
from .cabinet_types import policy as family_policy
from .contracts import BoxBodyPartSpec
from .endcap_xy_readback import project_manufacturing_endcap_bottom_fold_inputs


def _confirmed_endcap_lower_length(raw):
    """Validate the explicit or saved physical EndCap bottom outside length.

    An absent legacy Fold may use the existing Settings fallback, but an
    explicit bool, NaN, Infinity, negative or nonnumeric length is not proof
    of physical geometry. Do not reinterpret True as a 1-mm manufactured Fold.
    """
    if isinstance(raw, bool):
        raise ValueError("ENDCAP_BOTTOM_FOLD_SOURCE_INVALID")
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ENDCAP_BOTTOM_FOLD_SOURCE_INVALID") from exc
    if not isfinite(number) or number < 0:
        raise ValueError("ENDCAP_BOTTOM_FOLD_SOURCE_INVALID")
    return number


def _endcap_lower_outside_value(rows, values):
    """Read the same validated manufacturing ybottom1 as the GUI adapter.

    Source presence selects the real authored material/Fold. The historical
    value fallback only applies when no ybottom1 row exists at all.
    """
    measured = project_manufacturing_endcap_bottom_fold_inputs({
        "head": {"Y": rows or ()},
    })
    if "head_ybottom1" in measured:
        return measured["head_ybottom1"]
    return _confirmed_endcap_lower_length(
        values.get("ybottom1", ae.ybottom1_def),
    )


def build_box_body_operator_part_spec(
    values: Mapping[str, object],
    *,
    model_name,
    features=(),
    face_features=None,
    head_corner_policy=None,
    tail_corner_policy=None,
    fold_profile=(),
    structure_state=None,
    source_part_features=None,
    endcap_y_profiles=None,
    head_ybottom1=None,
    tail_ybottom1=None,
    snapshot=None,
) -> BoxBodyPartSpec:
    """Resolve current single/multipart BoxBody manufacturing input in Engine.

    GUI may collect the current profile and already-authored Features, but
    selecting which physical Fold/structure/back panel/part Feature belongs
    in the manufacturing PartSpec is exclusively Engine-owned.
    """
    source_structure = deepcopy(dict(structure_state or {}))
    canonical_structure = family_policy.resolve_box_body_structure_state(
        model_name, source_structure,
    )
    manufacturing_source = snapshot or values
    back_panel_contract = family_policy.resolve_box_body_back_panel_contract(
        model_name,
        manufacturing_source,
        structure_state=canonical_structure,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    workspace_features = dict(source_part_features or {})
    selected_piece_features = dict(
        (snapshot or {}).get(
            "physical_piece_features",
            {
                key: items for key, items in workspace_features.items()
                if str(key).startswith("box_body:")
                and not str(key).startswith("box_body:divider:")
            },
        )
    )
    # Receiving's confirmed side/back split is manufactured from its canonical
    # Fold Profile and physical pieces, not the legacy integral Z scalar tail.
    # Do not invent zr1/z_comp in CADSplit (or from Vault config.ini).
    # An absent canonical Fold still fails closed at this Engine boundary.
    is_receiving_split = (
        family_policy.canonical_family_name(model_name) == "受電箱"
        and str(canonical_structure.get("active_type")) == "three_piece_side_back_split"
        and bool(fold_profile)
        and bool(back_panel_contract)
    )

    def legacy_only_scalar(key):
        if key in values:
            return float(values[key])
        if is_receiving_split and key in ("zr1", "z_comp"):
            return None
        raise KeyError(key)

    y_profiles = dict(endcap_y_profiles or {})
    resolved_head = (
        _endcap_lower_outside_value(y_profiles.get("head", ()), values)
        if head_ybottom1 is None else _confirmed_endcap_lower_length(head_ybottom1)
    )
    resolved_tail = (
        _endcap_lower_outside_value(y_profiles.get("tail", ()), values)
        if tail_ybottom1 is None else _confirmed_endcap_lower_length(tail_ybottom1)
    )
    return BoxBodyPartSpec(
        width=float(values["w"]),
        height=float(values["h"]),
        depth=float(values["d"]),
        thickness=float(values["t"]),
        frame_width=float(values["fw"]),
        model_name=model_name,
        zl1=float(values["zl1"]),
        zl2=float(values["zl2"]),
        zr1=legacy_only_scalar("zr1"),
        zr2=float(values["zr2"]),
        z_comp=legacy_only_scalar("z_comp"),
        fold_profile=profile_to_fold_segments(fold_profile or ()),
        features=tuple(features or ()),
        face_features={
            key: tuple(items) for key, items in dict(face_features or {}).items()
        },
        physical_piece_features=deepcopy(selected_piece_features),
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
        structure_state=deepcopy(dict(canonical_structure or {})),
        back_panel_contract=deepcopy(dict(back_panel_contract or {})),
        head_ybottom1=resolved_head,
        tail_ybottom1=resolved_tail,
    )
