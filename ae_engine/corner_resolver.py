# -*- coding: utf-8 -*-
"""Joint-local corner resolution primitives.

STANDARD is derived from actual unfolded fold topology. Certified semantic
adjustments are applied by the registry/solver on top of this baseline.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StandardCornerGeometry:
    corner_name: str
    primary_u: float
    primary_v: float
    evidence: tuple[str, ...] = ()


def _rows(profile):
    return tuple(profile or ())


def _by_key(profile):
    return {str(getattr(row, "phase6_key", "") or ""): row for row in _rows(profile) if getattr(row, "phase6_key", None)}


def standard_corner_geometry(corner_name, x_profile, y_profile, *, nominal_fold_left=None, nominal_fold_right=None):
    """Measure material edge -> innermost actual fold using semantic Fold Profile keys."""
    name = str(corner_name)
    x = _by_key(x_profile)
    y = _by_key(y_profile)
    left = "left" in name
    top = "top" in name

    if "endcap_w_flat" in x:
        nominal = nominal_fold_left if left else nominal_fold_right
        u = 0.0 if nominal is None else float(nominal)
        u_evidence = "nominal_fold_left" if left else "nominal_fold_right"
    else:
        key = "yl1" if left else "yr1"
        if key in x:
            u = float(x[key].length)
            u_evidence = key
        else:
            nominal = nominal_fold_left if left else nominal_fold_right
            if nominal is None:
                raise ValueError(f"STANDARD missing X fold evidence for {name}")
            u = float(nominal)
            u_evidence = "nominal_fold_left" if left else "nominal_fold_right"

    if top:
        values = []
        evidence = []
        for key in ("ytop1", "fw"):
            if key in y:
                values.append(float(y[key].length)); evidence.append(key)
        if not values:
            raise ValueError(f"STANDARD missing top Y fold evidence for {name}")
        v = sum(values)
        v_evidence = "+".join(evidence)
    else:
        if "ybottom1" not in y:
            raise ValueError(f"STANDARD missing bottom Y fold evidence for {name}")
        v = float(y["ybottom1"].length)
        v_evidence = "ybottom1"

    return StandardCornerGeometry(name, max(0.0, u), max(0.0, v), (u_evidence, v_evidence))


def nearby_corner_relations(graph, part: str, corner_name: str) -> tuple[str, ...]:
    return tuple(sorted(j.relation.value for j in graph.nearby_joints(part, corner_name)))


def registry_intent_for_corner(graph, part: str, corner_name: str):
    """Project one local two-edge Joint pattern onto the legacy registry intent key.

    This projection exists only because the current certified JSON is keyed by
    the historical intent id.  The mechanical source remains the two explicit
    edge relations from the graph.
    """
    from .assembly_joint import AssemblyJointRelation
    from .sheetmetal_geometry import CornerTypeId
    rows = tuple(graph.nearby_joints(part, corner_name))
    by_edge = {str(j.edge).upper(): j.relation for j in rows if getattr(j, "edge", "")}
    vertical = "TOP" if "top" in str(corner_name).lower() else "BOTTOM"
    side = "LEFT" if "left" in str(corner_name).lower() else "RIGHT"
    face_relation = by_edge.get(vertical)
    side_relation = by_edge.get(side)
    if vertical != "TOP":
        return None
    if face_relation is AssemblyJointRelation.INSERT and side_relation is AssemblyJointRelation.INSERT:
        return CornerTypeId.INSERT
    if face_relation is AssemblyJointRelation.OVERLAY and side_relation is AssemblyJointRelation.OVERLAY:
        return CornerTypeId.OVERLAY
    if face_relation is AssemblyJointRelation.OVERLAY and side_relation is AssemblyJointRelation.INSERT:
        return CornerTypeId.INSERT_OVERLAY
    return None
