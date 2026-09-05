# -*- coding: utf-8 -*-
"""Data-driven catalog for through holes and blind pipe holes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv

from .sheetmetal_geometry import Vec2


@dataclass(frozen=True)
class HoleDefinition:
    name: str
    shape: str
    process: str
    diameter: float | None = None
    width: float | None = None
    height: float | None = None
    profile_path: Path | None = None
    source_code: str | None = None

    @property
    def directional(self) -> bool:
        return self.shape in {"rectangle", "profile"}


def _read_rows(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        yield from csv.reader(f)


def load_hole_catalog(base_dir) -> list[HoleDefinition]:
    base = Path(base_dir)
    path = base / '開孔.csv'
    if not path.exists():
        return []
    result = []
    rows = _read_rows(path)
    next(rows, None)
    for row in rows:
        cells = [c.strip() for c in row]
        if not cells or not cells[0]:
            continue
        name = cells[0]
        values = [c for c in cells[1:] if c]
        if not values:
            continue
        if len(values) == 1:
            try:
                diameter = float(values[0])
            except ValueError:
                result.append(HoleDefinition(name=name, shape='profile', process='FROM_DXF', profile_path=base / values[0]))
            else:
                result.append(HoleDefinition(name=name, shape='circle', process='CUTTING', diameter=diameter))
        else:
            try:
                width, height = float(values[0]), float(values[1])
            except ValueError as exc:
                raise ValueError(f'開孔.csv 尺寸格式錯誤: {name}') from exc
            result.append(HoleDefinition(name=name, shape='rectangle', process='CUTTING', width=width, height=height))
    return result


def load_pipe_catalog(base_dir) -> list[HoleDefinition]:
    base = Path(base_dir)
    path = base / '管孔尺寸清單.csv'
    if not path.exists():
        return []
    result = []
    rows = _read_rows(path)
    next(rows, None)
    for row in rows:
        cells = [c.strip() for c in row]
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        raw_diameter = cells[1].replace('Ø', '').replace('⌀', '').replace('Φ', '').strip()
        try:
            diameter = float(raw_diameter)
        except ValueError:
            continue
        result.append(HoleDefinition(name=cells[0], shape='circle', process='BLIND_HOLE', diameter=diameter, source_code=cells[0]))
    return result


def custom_circle_definition(diameter: float, *, blind: bool = False) -> HoleDefinition:
    return HoleDefinition(
        name="自訂圓孔", shape="circle", process=("BLIND_HOLE" if blind else "CUTTING"),
        diameter=float(diameter),
    )


def custom_rectangle_definition(width: float, height: float, *, blind: bool = False) -> HoleDefinition:
    return HoleDefinition(
        name="自訂方孔", shape="rectangle", process=("BLIND_HOLE" if blind else "CUTTING"),
        width=float(width), height=float(height),
    )


def load_profile_entities(path):
    """Read a DXF-backed hole profile while preserving its entity layers.

    Supported geometry is normalized around the overall profile bounding-box
    center so rotation and placement happen about one stable insertion point.
    """
    import math
    import ezdxf
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'找不到孔型 DXF: {path}')
    doc = ezdxf.readfile(path)
    raw = []
    all_x, all_y = [], []
    for ent in doc.modelspace():
        layer = str(getattr(ent.dxf, 'layer', '') or 'CUTTING').upper()
        etype = ent.dxftype()
        points = None
        closed = False
        if etype == 'LWPOLYLINE':
            points = [Vec2(float(x), float(y)) for x, y, *_ in ent.get_points()]
            closed = bool(ent.closed)
        elif etype == 'POLYLINE':
            points = [Vec2(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
            closed = bool(ent.is_closed)
        elif etype == 'LINE':
            points = [Vec2(float(ent.dxf.start.x), float(ent.dxf.start.y)), Vec2(float(ent.dxf.end.x), float(ent.dxf.end.y))]
            closed = False
        elif etype == 'CIRCLE':
            cx, cy, r = float(ent.dxf.center.x), float(ent.dxf.center.y), float(ent.dxf.radius)
            points = [Vec2(cx + r * math.cos(2*math.pi*i/64), cy + r * math.sin(2*math.pi*i/64)) for i in range(64)]
            closed = True
        if not points or len(points) < 2:
            continue
        raw.append((layer, tuple(points), closed))
        all_x.extend(p.x for p in points); all_y.extend(p.y for p in points)
    if not raw:
        raise ValueError(f'孔型 DXF 沒有可用幾何: {path.name}')
    cx, cy = (min(all_x)+max(all_x))/2.0, (min(all_y)+max(all_y))/2.0
    centered = tuple((layer, tuple(Vec2(p.x-cx, p.y-cy) for p in pts), closed) for layer, pts, closed in raw)
    return centered


def load_profile_points(path) -> tuple[Vec2, ...]:
    """Compatibility helper returning the largest closed CUTTING profile."""
    entities = load_profile_entities(path)
    candidates = [pts for layer, pts, closed in entities if layer == 'CUTTING' and closed and len(pts) >= 3]
    if not candidates:
        candidates = [pts for _layer, pts, closed in entities if closed and len(pts) >= 3]
    if not candidates:
        raise ValueError(f'孔型 DXF 沒有封閉輪廓: {Path(path).name}')
    return max(candidates, key=lambda ps: (max(p.x for p in ps)-min(p.x for p in ps))*(max(p.y for p in ps)-min(p.y for p in ps)))


def feature_from_definition(definition: HoleDefinition, point: Vec2, width: float, height: float, *, rotation_deg: int = 360):
    """Build one semantic Feature from a catalog definition at a finished/world point."""
    from .sheetmetal_features import (
        CircleFeature, RectFeature, ProfileFeature, placement_from_finished_point,
    )
    placement = placement_from_finished_point(point, width, height)
    rotation = int(rotation_deg) % 360
    if definition.shape == 'circle':
        params = ()
        source_type = definition.name
        add_centerline = False
        if definition.process == 'BLIND_HOLE':
            source_type = '管孔'
            add_centerline = True
            params = (("code", definition.source_code or definition.name),)
        return CircleFeature(
            diameter=float(definition.diameter), anchor=placement.anchor, offset=placement.offset,
            layer=definition.process, add_centerline=add_centerline, source_type=source_type,
            source_params=params, rotation_deg=rotation,
        )
    if definition.shape == 'rectangle':
        return RectFeature(
            width=float(definition.width), height=float(definition.height), anchor=placement.anchor,
            offset=placement.offset, layer=definition.process, source_type=definition.name,
            rotation_deg=rotation,
        )
    if definition.shape == 'profile':
        entities = load_profile_entities(definition.profile_path)
        closed = [pts for _layer, pts, is_closed in entities if is_closed and len(pts) >= 3]
        if not closed:
            raise ValueError(f'孔型 DXF 沒有封閉輪廓: {Path(definition.profile_path).name}')
        points = max(closed, key=lambda ps: (max(p.x for p in ps)-min(p.x for p in ps))*(max(p.y for p in ps)-min(p.y for p in ps)))
        return ProfileFeature(
            points=points, anchor=placement.anchor, offset=placement.offset,
            layer='FROM_DXF', source_type=definition.name,
            source_params=(("profile_path", str(definition.profile_path)),), rotation_deg=rotation,
            layered_profiles=entities,
        )
    raise ValueError(f'不支援的孔型: {definition.shape}')
