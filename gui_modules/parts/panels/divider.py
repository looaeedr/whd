"""Divider input-panel presentation boundary; geometry stays authoritative elsewhere."""


import math


def _positive_finite_float(value, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"中隔 {label} 不得為布林值")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"中隔 {label} 必須大於 0 且為有限數值")
    return parsed


def collect_divider_input(part_key, payload, *, default_depth, default_thickness):
    """Normalize divider UI payload without deriving manufacturing geometry."""
    data = dict(payload or {})
    raw_cols = tuple(data.get("door_layout_columns") or ())
    columns = []
    for row in raw_cols:
        if not isinstance(row, (list, tuple)) or len(row) < 2 or not isinstance(row[1], (list, tuple)):
            raise ValueError(f"中隔 door_layout_columns 格式不合法: {part_key}")
        col_w = _positive_finite_float(row[0], "欄寬")
        col_heights = tuple(_positive_finite_float(value, "門高") for value in row[1])
        if not col_heights:
            raise ValueError(f"中隔欄缺少門高列: {part_key}")
        columns.append((col_w, col_heights))
    columns = tuple(columns)
    if not columns:
        raise ValueError(f"中隔缺少 authoritative multi-door topology: {part_key}")

    raw_d = data.get("d")
    raw_t = data.get("t")
    depth = _positive_finite_float(default_depth if raw_d is None else raw_d, "深度")
    thickness = _positive_finite_float(default_thickness if raw_t is None else raw_t, "板厚")

    return {
        "columns": columns,
        "depth": depth,
        "thickness": thickness,
        "layout_scope": str(data.get("door_layout_scope") or "main").strip() or "main",
        "handle_edges": dict(data.get("door_handle_edges") or {}),
        "model_name": str(data.get("model") or "").strip() or None,
    }
