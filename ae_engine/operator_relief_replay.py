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
    if not bool(saved.get("enabled")):
        return ()
    profile = box_body_profile or ()
    formed_left, formed_right = formed_box_body_fw_widths(
        profile, float(values.get("t", 0.0) or 0.0),
    )
    try:
        graph_fingerprint = resolved_joint_graph_fingerprint(dict(joint_state or {}))
    except Exception:
        return ()
    scalar = {
        name: float(values.get(name, default))
        for name, default in (
            ("w", 0.0), ("h", 0.0), ("d", 0.0),
            ("t", 0.0), ("fw", 0.0),
            ("zl1", ae.zl1_def), ("zr1", ae.zr1_def),
            ("yl1", ae.yl1_def), ("yr1", ae.yr1_def),
            ("ytop1", ae.ytop1_def), ("ybottom1", ae.ybottom1_def),
        )
    }
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
