"""Bounded manufacturing request-resolution owners."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from .contracts import EndCapPartSpec, FeatureLike, FoldProfileSegment
from .sheetmetal_geometry import EndCapAssemblySemantics, FourCornerTypePolicy


@dataclass(frozen=True)
class ResolvedEndCapRequest:
    """Normalized EndCap manufacturing request."""

    width: float
    depth: float
    thickness: float
    frame_width: float
    height: float | None
    model_name: str | None
    is_tail: bool
    fold_left: float
    fold_right: float
    nominal_fold_left: float
    nominal_fold_right: float
    box_body_formed_fw_left: float | None
    box_body_formed_fw_right: float | None
    fold_top: float
    fold_bottom: float
    x_topology: Literal['folded', 'flat']
    fold_profile_x: tuple[FoldProfileSegment, ...]
    fold_profile_y: tuple[FoldProfileSegment, ...]
    corner_policy: FourCornerTypePolicy | None
    assembly: EndCapAssemblySemantics | None
    depth_comp_t: float
    holes: tuple[FeatureLike, ...]


def resolve_endcap_request(
    spec: EndCapPartSpec,
    *,
    endcap_scalar,
    default_fold_left: float,
    default_fold_right: float,
    default_fold_top: float,
    default_fold_bottom: float,
    resolve_assembly_semantics,
) -> ResolvedEndCapRequest:
    scalar_left = endcap_scalar(spec.fold_left, default_fold_left)
    scalar_right = endcap_scalar(spec.fold_right, default_fold_right)
    left = scalar_left
    right = scalar_right
    top = endcap_scalar(spec.fold_top, default_fold_top)
    bottom = endcap_scalar(spec.fold_bottom, default_fold_bottom)

    x_rows = tuple(spec.fold_profile_x or ())
    flat_x = any(row.phase6_key == 'endcap_w_flat' for row in x_rows)
    core_index = next(
        (index for index, row in enumerate(x_rows) if row.core == 'W-2T'),
        None,
    )
    if flat_x:
        left = 0.0
        right = 0.0
    elif core_index is not None:
        left = sum(float(row.length) for row in x_rows[:core_index])
        right = sum(float(row.length) for row in x_rows[core_index + 1:])

    y_rows = tuple(spec.fold_profile_y or ())
    canonical_fw = next(
        (float(row.length) for row in y_rows if row.phase6_key == 'fw'),
        None,
    )
    if y_rows:
        top = sum(
            float(row.length)
            for row in y_rows
            if row.phase6_key not in {'fw', 'endcap_d_core', 'ybottom1'}
        )
        bottom_rows = [row for row in y_rows if row.phase6_key == 'ybottom1']
        if bottom_rows:
            bottom = sum(float(row.length) for row in bottom_rows)

    assembly = None
    corner_policy = spec.corner_policy
    if corner_policy is not None and canonical_fw is not None:
        corner_policy = replace(corner_policy, fw=float(canonical_fw))
    if corner_policy is not None:
        assembly = resolve_assembly_semantics(corner_policy)
        if assembly.x_topology == 'flat':
            left = 0.0
            right = 0.0
            x_rows = ()
        elif flat_x:
            left = scalar_left
            right = scalar_right
            x_rows = ()

    x_topology: Literal['folded', 'flat'] = (
        assembly.x_topology
        if assembly is not None
        else ('flat' if flat_x else 'folded')
    )

    return ResolvedEndCapRequest(
        width=float(spec.width),
        depth=float(spec.depth),
        thickness=float(spec.thickness),
        frame_width=float(spec.frame_width if canonical_fw is None else canonical_fw),
        height=None if spec.height is None else float(spec.height),
        model_name=spec.model_name,
        is_tail=bool(spec.is_tail),
        fold_left=left,
        fold_right=right,
        nominal_fold_left=scalar_left,
        nominal_fold_right=scalar_right,
        box_body_formed_fw_left=(
            None
            if spec.box_body_formed_fw_left is None
            else float(spec.box_body_formed_fw_left)
        ),
        box_body_formed_fw_right=(
            None
            if spec.box_body_formed_fw_right is None
            else float(spec.box_body_formed_fw_right)
        ),
        fold_top=top,
        fold_bottom=bottom,
        x_topology=x_topology,
        fold_profile_x=x_rows,
        fold_profile_y=y_rows,
        corner_policy=corner_policy,
        assembly=assembly,
        depth_comp_t=float(spec.depth_comp_t),
        holes=tuple(spec.holes or ()),
    )
