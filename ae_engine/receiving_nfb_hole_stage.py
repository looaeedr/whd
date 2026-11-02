"""Engine-only physical source admission for original inner-door Hole Editor.

Do not infer physical NFB certification from a ProfileFeature source_type:
upstream CSV/verified-proof owners establish provenance. This read-only stage
guard only validates the current finished-face, original part and duplication.
No GUI/Tk import, Registry mutation, project commit or DXF permission.
"""
from __future__ import annotations

from .sheetmetal_feature_core import ProfileFeature
from .sheetmetal_feature_surface import feature_is_strictly_within_surface


def plan_operator_inner_door_nfb_hole_stage(
    *,
    part_key: str,
    surface,
    width: float,
    height: float,
    current_features,
    incoming_features,
    mode: str,
) -> tuple:
    """Plan a session-only preview of verified or CSV draft NFB CUTTING holes.

    mode='verified_append': append a previously verified physical-source import
    only if no NFB source hole is already present.
    mode='csv_replace': replace previous CSV drafts, never an operator's other
    holes or an earlier real-source-verified NFB opening.
    """
    part_id = str(part_key or "")
    if (not part_id.startswith("inner_door:")
            or not part_id.endswith(":panel")):
        raise ValueError("NFB 主孔必須屬於實體內門板")
    if mode not in ("verified_append", "csv_replace"):
        raise ValueError("unknown NFB inner-door staging operation")
    current = tuple(current_features)
    incoming = tuple(incoming_features)
    if mode == "verified_append":
        if not incoming or any(
            not isinstance(feature, ProfileFeature)
            or feature.source_type not in ("NFB_VERIFIED_SOURCE", "NFB_CSV_SOURCE")
            for feature in incoming
        ):
            raise ValueError("不能帶入未完成實體來源驗證的 NFB 孔")
        if any(
            getattr(feature, "source_type", "") in
            ("NFB_VERIFIED_SOURCE", "NFB_CSV_SOURCE")
            for feature in current
        ):
            raise ValueError("此門板已有相同 NFB 來源主孔；請重新開啟編輯驗證")
        for feature in incoming:
            bound_part_id = dict(feature.source_params).get("part_id")
            if bound_part_id is not None and bound_part_id != part_id:
                raise ValueError("NFB 開孔不可帶入其他實體內門")
            if not feature_is_strictly_within_surface(
                surface, feature, width, height,
            ):
                raise ValueError("NFB 來源主孔超出內門實體平面")
        return (*current, *incoming)

    if any(
        not isinstance(feature, ProfileFeature)
        or feature.source_type != "NFB_CSV_SOURCE"
        for feature in incoming
    ):
        raise ValueError("NFB 頁籤只能暫存合法 CSV 主孔")
    if any(dict(feature.source_params).get("part_id") != part_id
           for feature in incoming):
        raise ValueError("NFB 開孔不可帶入其他實體內門")
    if incoming and any(
        getattr(feature, "source_type", None) == "NFB_VERIFIED_SOURCE"
        for feature in current
    ):
        raise ValueError("已有來源驗證的 NFB 孔，不可重複產生")
    for feature in incoming:
        if not feature_is_strictly_within_surface(
            surface, feature, width, height,
        ):
            raise ValueError("NFB 主孔超出目前內門板面")
    # Empty incoming deliberately removes earlier CSV drafts, retaining the
    # operator's own features and any verified physical-source NFB openings.
    retained = tuple(
        feature for feature in current
        if getattr(feature, "source_type", None) != "NFB_CSV_SOURCE"
    )
    return (*retained, *incoming)
