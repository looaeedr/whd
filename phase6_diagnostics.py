# -*- coding: utf-8 -*-
"""Phase6 診斷資料的純聚合與序列化深模組。

此模組只接收已解析的診斷 context 與 render provider；不擁有 GUI、交易、
專案狀態或製造幾何推導。
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Callable, Mapping, Sequence

from shapely.geometry import mapping

from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)


DIAGNOSTIC_SCHEMA = "phase6-fold-diagnostic-v1"


@dataclass(frozen=True)
class DiagnosticSnapshotContext:
    model: str
    active_part: str | None
    settings: Mapping[str, object]
    corner_state: Mapping[str, object]
    corner_pair_same: Mapping[str, object]
    workspace: Mapping[str, object]
    active_part_payload: Mapping[str, object]


def json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return json_safe(value.value)
    if is_dataclass(value):
        return {field.name: json_safe(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return repr(value)


def serialize_scene(scene):
    rows = []
    for primitive in getattr(scene, "primitives", ()):
        row = {
            "type": type(primitive).__name__,
            "layer": str(getattr(primitive, "layer", "")),
            "color": getattr(primitive, "color", None),
        }
        if isinstance(primitive, PolylinePrimitive):
            row.update(
                closed=bool(primitive.closed),
                points=[[float(p.x), float(p.y)] for p in primitive.points],
            )
        elif isinstance(primitive, LinePrimitive):
            row.update(
                p1=[float(primitive.p1.x), float(primitive.p1.y)],
                p2=[float(primitive.p2.x), float(primitive.p2.y)],
            )
        elif isinstance(primitive, CirclePrimitive):
            row.update(
                center=[float(primitive.center.x), float(primitive.center.y)],
                radius=float(primitive.radius),
            )
        elif isinstance(primitive, TextPrimitive):
            row.update(
                text=str(primitive.text),
                insert=[float(primitive.insert.x), float(primitive.insert.y)],
                char_height=float(primitive.char_height),
            )
        rows.append(row)
    return {"primitive_count": len(rows), "primitives": rows}


def material_diagnostic(material):
    def interior_count(geom):
        if geom is None or geom.is_empty:
            return 0
        if geom.geom_type == "Polygon":
            return len(geom.interiors)
        if hasattr(geom, "geoms"):
            return sum(interior_count(part) for part in geom.geoms)
        return 0

    return {
        "geometry_type": str(getattr(material, "geom_type", type(material).__name__)),
        "bounds": [float(v) for v in material.bounds],
        "area": float(material.area),
        "interior_count": int(interior_count(material)),
        "geojson": json_safe(mapping(material)),
    }


def serialize_fold_guides(guides):
    return [
        {
            "axis": str(getattr(g, "axis", "")),
            "position": float(getattr(g, "position", 0.0)),
            "span_start": float(getattr(g, "span_start", 0.0)),
            "span_end": float(getattr(g, "span_end", 0.0)),
        }
        for g in (guides or ())
    ]


def _serialize_render_data(render_data, *, include_fold_guides: bool) -> dict:
    result = {
        "scene": serialize_scene(render_data.scene),
        "material": material_diagnostic(render_data.material),
    }
    if include_fold_guides:
        result["fold_guides"] = serialize_fold_guides(getattr(render_data, "fold_guides", ()))
    return result


def build_active_diagnostic_snapshot(
    context: DiagnosticSnapshotContext,
    render_provider: Callable[[], object] | None,
) -> dict:
    result = {
        "schema": DIAGNOSTIC_SCHEMA,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": str(context.model or "").strip(),
        "active_part": context.active_part,
        "settings": json_safe(context.settings),
        "corner_state": json_safe(context.corner_state),
        "corner_pair_same": json_safe(context.corner_pair_same),
        "workspace": json_safe(context.workspace),
        "active_part_payload": json_safe(context.active_part_payload),
        "final_geometry": None,
        "render_error": None,
    }
    if context.active_part:
        try:
            if render_provider is None:
                raise RuntimeError("3D final-scene provider is not connected")
            result["final_geometry"] = _serialize_render_data(
                render_provider(), include_fold_guides=False
            )
        except Exception as exc:
            result["render_error"] = f"{type(exc).__name__}: {exc}"
    return result


def collect_final_geometry_diagnostics(
    part_keys: Sequence[str],
    payload_provider: Callable[[str], Mapping[str, object]],
    render_provider: Callable[[str, Mapping[str, object]], object] | None,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for raw_key in part_keys:
        key = str(raw_key)
        payload = payload_provider(key)
        row = {
            "payload": payload,
            "scene": None,
            "material": None,
            "fold_guides": [],
            "error": None,
        }
        if render_provider is None:
            row["error"] = "3D final-scene provider is not connected"
        else:
            try:
                row.update(_serialize_render_data(render_provider(key, payload), include_fold_guides=True))
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
        result[key] = row
    return result


def write_diagnostic_json(path, payload) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
