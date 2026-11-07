# -*- coding: utf-8 -*-
"""Headless Engine-owned Hole Editor context for real physical sheet sources.

This adapter selects only already-manufactured render parts. It must not
construct GUI previews, invent part identities or authorize unverified DXF.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import CustomFoldPartSpec
from .custom_part_catalog import is_custom_part
from .custom_fold_manufacturing import custom_fold_feature_context
from .physical_part_identity import is_box_body_physical_piece_key
from .physical_sheet_features import physical_sheet_feature_context


@dataclass(frozen=True)
class PhysicalSheetEditorContext:
    """Original material scene and its authoritative feature-placement surface."""

    render_data: object
    feature_surface: object
    width: float
    height: float
    reference_guide: object
    part_key: str | None = None


def resolve_physical_sheet_editor_context(
    part_key: str, render_data, *, custom_spec: CustomFoldPartSpec | None = None,
) -> PhysicalSheetEditorContext:
    """Select one physical sheet before a GUI opens its existing Hole Editor."""
    if not isinstance(part_key, str) or not part_key:
        raise ValueError("physical sheet editor requires a physical part key")
    render = render_data
    if is_box_body_physical_piece_key(part_key):
        pieces = tuple(getattr(render_data, "pieces", ()) or ())
        matches = [
            p for p in pieces
            if f"box_body:{getattr(p, 'role', '')}" == part_key
        ]
        if len(matches) != 1:
            raise ValueError(f"找不到唯一實體箱身板件：{part_key}")
        render = getattr(matches[0], "render_data", None)
    if render is None or getattr(render, "scene", None) is None:
        raise ValueError(f"實體板件缺少正式 DrawingScene：{part_key}")
    if is_custom_part(part_key):
        if not isinstance(custom_spec, CustomFoldPartSpec) or custom_spec.physical_id != part_key:
            raise ValueError(f"自訂板件 PartSpec 與實體身份不符：{part_key}")
        surface, width, height, guide = custom_fold_feature_context(custom_spec)
    else:
        if custom_spec is not None:
            raise ValueError("非自訂板件不接受 CustomFold PartSpec")
        surface, width, height, guide = physical_sheet_feature_context(part_key, render)
    return PhysicalSheetEditorContext(render, surface, width, height, guide, part_key)


def propose_operator_physical_sheet_hole_features(
    part_key: str, context: PhysicalSheetEditorContext, features,
):
    """Validate the entire current physical sheet draft before GUI writes it.

    Reuse the same typed feature conversion and material-surface resolver as
    the canonical CustomFold/physical-sheet render paths. The result retains
    the input representation for legacy project Save/Reload compatibility and
    never changes the source list or grants manufacturing/DXF release.
    """
    from collections.abc import Mapping
    from copy import deepcopy
    from .sheetmetal_feature_core import CircleFeature, RectFeature, ProfileFeature
    from .sheetmetal_features import legacy_hole_to_feature
    from .sheetmetal_feature_surface import resolve_surface_features

    if (not isinstance(part_key, str) or not part_key
            or not isinstance(context, PhysicalSheetEditorContext)
            or context.part_key != part_key):
        raise ValueError("實體孔位提交的板件身分不符")
    if features is None or isinstance(features, (str, bytes, Mapping)):
        raise ValueError("實體孔位提交需要完整孔型清單")
    try:
        detached = tuple(deepcopy(tuple(features)))
    except (TypeError, ValueError) as exc:
        raise ValueError("實體孔位清單不可遍歷") from exc
    normalized = []
    for feature in detached:
        if isinstance(feature, Mapping):
            normalized.append(legacy_hole_to_feature(dict(feature)))
        elif isinstance(feature, (CircleFeature, RectFeature, ProfileFeature)):
            normalized.append(feature)
        else:
            raise ValueError("實體孔位不是有效的 Feature")
    resolve_surface_features(
        context.feature_surface, tuple(normalized),
        context.width, context.height,
    )
    return detached


