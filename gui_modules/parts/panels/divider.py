"""Divider input-panel presentation boundary; geometry stays authoritative elsewhere."""


def collect_divider_input(part_key, payload, *, default_depth, default_thickness):
    """Normalize divider UI payload without deriving manufacturing geometry."""
    import math

    def positive_dimension(value, field):
        if isinstance(value, bool):
            raise ValueError(f"{field}必須是有限正數")
        try:
            amount = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field}必須是有限正數") from exc
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"{field}必須是有限正數")
        return amount

    data = dict(payload or {})
    columns = tuple(
        (positive_dimension(row[0], "中隔欄寬"),
         tuple(positive_dimension(value, "中隔列高") for value in row[1]))
        for row in tuple(data.get("door_layout_columns") or ())
    )
    if not columns or any(not heights for _width, heights in columns):
        raise ValueError(f"中隔缺少 authoritative multi-door topology: {part_key}")

    depth = data.get("d")
    thickness = data.get("t")
    return {
        "columns": columns,
        "depth": positive_dimension(default_depth if depth is None else depth, "中隔深度"),
        "thickness": positive_dimension(default_thickness if thickness is None else thickness, "中隔板厚"),
        "layout_scope": str(data.get("door_layout_scope") or "main").strip() or "main",
        "handle_edges": dict(data.get("door_handle_edges") or {}),
        "model_name": str(data.get("model") or "").strip() or None,
    }
