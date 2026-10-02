"""Divider input-panel presentation boundary; geometry stays authoritative elsewhere."""


def collect_divider_input(part_key, payload, *, default_depth, default_thickness):
    """Normalize divider UI payload without deriving manufacturing geometry."""
    data = dict(payload or {})
    columns = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in tuple(data.get("door_layout_columns") or ())
    )
    if not columns:
        raise ValueError(f"中隔缺少 authoritative multi-door topology: {part_key}")

    return {
        "columns": columns,
        "depth": float(data.get("d", default_depth)),
        "thickness": float(data.get("t", default_thickness)),
        "layout_scope": str(data.get("door_layout_scope") or "main").strip() or "main",
        "handle_edges": dict(data.get("door_handle_edges") or {}),
        "model_name": str(data.get("model") or "").strip() or None,
    }
