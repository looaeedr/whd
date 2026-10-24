"""Receiving Base Plate Settings transaction with explicit state ownership.

A settings action may validate and update the existing physical Base Plate
selection only.  No GUI application object, new manufactured part, or
illustrative DXF world-coordinate mapping is accepted here.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite

from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions


def commit_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping,
    submit_geometry_update, config: Mapping | None,
):
    """Validate actual structural geometry then atomically commit one selection."""
    if not isinstance(input_snapshot, dict):
        raise ValueError("受電箱實體底板缺少可提交的專案狀態")
    if not isinstance(settings_values, Mapping):
        raise ValueError("受電箱底板設定缺少外箱尺寸來源")
    if str(input_snapshot.get("model") or "").strip() not in {"受電箱", "RECEIVING"}:
        raise ValueError("只有受電箱可選擇專用底板")
    if config is not None and not isinstance(config, Mapping):
        raise ValueError("受電箱底板配置必須是完整欄位")

    if config is not None:
        probe = dict(input_snapshot)
        for key in ("w", "t"):
            if key in settings_values:
                probe[key] = settings_values[key]
        if any(
            isinstance(probe.get(k), bool)
            or not isinstance(probe.get(k), (int, float))
            or not isfinite(float(probe[k]))
            or float(probe[k]) <= 0
            for k in ("w", "t")
        ):
            raise ValueError("受電箱底板外箱 W/T 必須是有限正數")
        probe["receiving_base_plate"] = dict(config)
        receiving_base_plate_blank_dimensions(probe)
        if probe.get("nfb_config_submitted") is True:
            receiving_base_plate_blank_dimensions({
                **probe,
                "nfb_config_submitted": False,
                "nfb_config": None,
            })

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

    existed = "receiving_base_plate" in input_snapshot
    previous = deepcopy(input_snapshot.get("receiving_base_plate"))
    try:
        if config is None:
            input_snapshot.pop("receiving_base_plate", None)
        else:
            input_snapshot["receiving_base_plate"] = deepcopy(dict(config))
        submit_geometry_update()
    except Exception:
        if existed:
            input_snapshot["receiving_base_plate"] = previous
        else:
            input_snapshot.pop("receiving_base_plate", None)
        raise
    return deepcopy(input_snapshot.get("receiving_base_plate"))
