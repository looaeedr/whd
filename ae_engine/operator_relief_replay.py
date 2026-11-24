# -*- coding: utf-8 -*-
"""Engine owner for operator-source verified persisted Assembly Relief replay.

GUI transports current workspace/part inputs only.  The existing Joint Graph,
BoxBody formed FW, canonical persisted signature and Registered Relief identity
remain the sole manufacturing provenance.  Never authorize new CUTTING here.
"""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping

from . import ae
from .assembly_joint import resolved_joint_graph_fingerprint
from .box_body_editor_readback import formed_box_body_fw_widths
from .assembly_relief_state import (
    build_current_source_signature, committed_relief_cuts,
)
from .operator_settings_transactions import normalize_operator_settings_boolean


def build_operator_current_relief_source_signature(
    *, scalar_source, joint_state, structure_state, box_body_profile, part_profiles,
):
    """Return the canonical current Assembly Relief replay source identity.

    GUI/CADSplit provide their current, caller-specific source data only.
    Existing Engine Joint and formed-FW owners determine mechanical identity;
    persistence uses exactly the original canonical signature serializer.
    This does not authorize a CUTTING or manufacture result.
    """
    if not isinstance(scalar_source, Mapping):
        raise ValueError("RELIEF_SCALAR_SOURCE_MAPPING_REQUIRED")
    if not isinstance(joint_state, Mapping):
        raise ValueError("RELIEF_JOINT_SOURCE_MAPPING_REQUIRED")
    scalar = dict(scalar_source)
    profile = deepcopy(list(box_body_profile or ()))
    left, right = formed_box_body_fw_widths(
        profile, float(scalar.get("t", 0.0) or 0.0),
    )
    return build_current_source_signature(
        scalar_source=scalar,
        joint_graph_fingerprint=resolved_joint_graph_fingerprint(joint_state),
        structure_state=structure_state,
        cabinet_family=str(
            scalar.get("model") or scalar.get("cabinet_type") or ""
        ),
        formed_left=left, formed_right=right,
        box_body_profile=profile, part_profiles=part_profiles,
    )


def resolve_operator_committed_relief_cuts(
    part_key, values, *, relief_state, joint_state=None,
    structure_state=None, cabinet_family="", box_body_profile=(),
    part_profiles=None,
):
    """Validate a saved CUT against current operator-supplied physical sources.

    Preserve the original disabled short circuit, scalar defaults, mechanical
    joint identity, formed Fold width and stale-source refusal exactly.
    """
    saved = deepcopy(dict(relief_state or {}))
    if not normalize_operator_settings_boolean(
        saved["enabled"] if "enabled" in saved else False
    ):
        return ()
    # A committed CUT may only be replayed against the exact physical
    # operator source.  Coercing bool(True) to 1 mm or carrying NaN into the
    # signature could make a stale saved polygon appear valid.  Qualify the
    # complete active source before computing any formed-FW or Joint identity.
    from .operator_settings_transactions import normalize_operator_source_dimension
    from .door_operator_part_spec import _finite_operator_number

    if not isinstance(values, Mapping):
        raise ValueError("RELIEF_SCALAR_SOURCE_MAPPING_REQUIRED")
    scalar = {
        name: normalize_operator_source_dimension(values.get(name), field=name)
        for name in ("w", "h", "d", "t", "fw")
    }
    scalar.update({
        name: _finite_operator_number(values.get(name, default), name)
        for name, default in (
            ("zl1", ae.zl1_def), ("zr1", ae.zr1_def),
            ("yl1", ae.yl1_def), ("yr1", ae.yr1_def),
            ("ytop1", ae.ytop1_def), ("ybottom1", ae.ybottom1_def),
        )
    })
    profile = box_body_profile or ()
    formed_left, formed_right = formed_box_body_fw_widths(
        profile, scalar["t"],
    )
    try:
        graph_fingerprint = resolved_joint_graph_fingerprint(dict(joint_state or {}))
    except Exception:
        return ()
    current = build_current_source_signature(
        scalar_source=scalar,
        joint_graph_fingerprint=graph_fingerprint,
        structure_state=structure_state,
        cabinet_family=str(cabinet_family or ""),
        formed_left=formed_left,
        formed_right=formed_right,
        box_body_profile=profile,
        part_profiles={
            str(part_key): deepcopy(dict(part_profiles or {})),
        },
    )
    return committed_relief_cuts(saved, str(part_key), current)
