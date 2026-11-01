# -*- coding: utf-8 -*-
"""Source-verified Receiving Base Plate settings preflight in manufacturing Engine."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .receiving_base_plate_config import receiving_base_plate_blank_dimensions


def validate_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping, config: Mapping | None,
):
    """Validate physical plate and weld EAR slots before accepting operator state."""
    if not isinstance(input_snapshot, dict):
        raise ValueError("受電箱實體底板缺少可提交的專案狀態")
    if str(input_snapshot.get("model") or "").strip() not in {"受電箱", "RECEIVING"}:
        raise ValueError("只有受電箱可選擇專用底板")
    if config is not None and not isinstance(config, Mapping):
        raise ValueError("受電箱底板配置必須是完整欄位")

    if config is not None:
        probe = dict(input_snapshot)
        for key in ("w", "t"):
            if key in settings_values:
                probe[key] = settings_values[key]
        probe["receiving_base_plate"] = dict(config)
        receiving_base_plate_blank_dimensions(probe)

        # Validate the true EAR mounting holes through their manufacturing
        # owner, BEFORE accepting a new pattern.  LEFT/RIGHT blanks cannot
        # silently reuse the CENTER fold's shrink dimensions.
        from ae_engine.sheetmetal_part_adapters import build_receiving_base_plate_result
        from ae_engine.ae import _receiving_base_weld_ear_mount_slots
        from ae_engine.sheetmetal_drawing import DrawingScene

        result = build_receiving_base_plate_result(
            w=float(probe["w"]), h=float(config["height"]), t=float(probe["t"]),
            shrink_top=float(config["shrink_top"]),
            shrink_bottom=float(config["shrink_bottom"]),
            shrink_left=float(config["shrink_left"]),
            shrink_right=float(config["shrink_right"]),
            bend=float(config["bend"]),
            pattern=str(config["pattern"]),
        )
        _receiving_base_weld_ear_mount_slots(
            DrawingScene(), result=result, pattern=str(config["pattern"]),
            box_w=float(probe["w"]), t=float(probe["t"]),
        )

    return None if config is None else deepcopy(dict(config))
