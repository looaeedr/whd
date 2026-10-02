# -*- coding: utf-8 -*-
"""Canonical corner-dimension display text shared by Main GUI and Fold Designer."""
from __future__ import annotations

_CORNER_LABELS = {
    "bottom_left": "左下",
    "bottom_right": "右下",
    "top_left": "左上",
    "top_right": "右上",
}


def measurement_text(measurement):
    def n(value):
        number = float(value)
        nearest = round(number)
        if abs(number - nearest) <= 1e-4:
            return str(int(nearest))
        return f"{number:.3f}".rstrip("0").rstrip(".")

    text = f"{n(measurement.primary_u)}×{n(measurement.primary_v)}"
    secondary_u = getattr(measurement, "secondary_u", None)
    secondary_depth = getattr(measurement, "secondary_depth", None)
    if secondary_u is not None and secondary_depth is not None:
        text += f" + {n(secondary_u)}×{n(secondary_depth)}"
    return text


# Backward-compatible local alias; callers should import measurement_text.
_measurement_text = measurement_text


def render_data_corner_dimension_text(render_data):
    """Return display text measured from canonical manufacturing material."""
    from ae_engine.assembly_collision import measure_material_corner_reliefs

    groups = []
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if pieces:
        for piece in pieces:
            material = getattr(getattr(piece, "render_data", None), "material", None)
            measurements = measure_material_corner_reliefs(material)
            if not measurements:
                continue
            rows = [
                f"{_CORNER_LABELS.get(m.corner_name, m.corner_name)} {measurement_text(m)}"
                for m in measurements
            ]
            role = str(getattr(piece, "role", getattr(piece, "key", "板件")) or "板件")
            groups.append(f"{role}：{' / '.join(rows)}")
    else:
        material = getattr(render_data, "material", None)
        measurements = measure_material_corner_reliefs(material)
        if measurements:
            groups.extend(
                f"{_CORNER_LABELS.get(m.corner_name, m.corner_name)} {measurement_text(m)}"
                for m in measurements
            )
    return "截角尺寸：" + ("；".join(groups) if groups else "無")
