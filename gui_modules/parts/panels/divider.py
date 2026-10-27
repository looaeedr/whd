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

    try:
        data = dict(payload or {})
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("中隔設定資料必須為物件") from exc
    raw_columns = data.get("door_layout_columns") or ()
    # Reject corrupt saved topology before indexing a row or iterating heights.
    # Source dimensions and physical projection remain unchanged.
    if (not isinstance(raw_columns, (list, tuple))
            or any(not isinstance(row, (list, tuple)) or len(row) != 2
                   or not isinstance(row[1], (list, tuple)) for row in raw_columns)):
        raise ValueError(f"中隔缺少 authoritative multi-door topology: {part_key}")
    columns = tuple(
        (positive_dimension(row[0], "中隔欄寬"),
         tuple(positive_dimension(value, "中隔列高") for value in row[1]))
        for row in raw_columns
    )
    if not columns or any(not heights for _width, heights in columns):
        raise ValueError(f"中隔缺少 authoritative multi-door topology: {part_key}")

    depth = data.get("d")
    thickness = data.get("t")
    try:
        handle_edges = dict(data.get("door_handle_edges") or {})
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("中隔把手邊資料必須為物件") from exc
    return {
        "columns": columns,
        "depth": positive_dimension(default_depth if depth is None else depth, "中隔深度"),
        "thickness": positive_dimension(default_thickness if thickness is None else thickness, "中隔板厚"),
        "layout_scope": str(data.get("door_layout_scope") or "main").strip() or "main",
        "handle_edges": handle_edges,
        "model_name": str(data.get("model") or "").strip() or None,
    }
