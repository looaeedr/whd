"""Exact manufacturing equivalence of already-resolved physical demands."""
from dataclasses import dataclass, fields, is_dataclass
from collections.abc import Mapping
import hashlib
import json
import math

from .sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive, TextPrimitive,
)


@dataclass(frozen=True)
class ManufacturingParameters:
    material: object
    thickness: float
    process: object


@dataclass(frozen=True)
class QuantityManufacturingGroup:
    key: str
    parameters: ManufacturingParameters
    members: tuple
    render_data: object

    @property
    def quantity(self):
        return sum(row.quantity for row in self.members)

    @property
    def filename(self):
        return f"part_{self.key}.dxf"


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite manufacturing coordinate/parameter")
    return 0.0 if value == 0 else value


def _value(value):
    """Lossless bounded parameter serialization; never stringify unknown objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _number(value)
    if is_dataclass(value):
        return {field.name: _value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("manufacturing parameter keys must be strings")
        return {key: _value(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    raise TypeError(f"unsupported manufacturing parameter: {type(value).__name__}")


def _point(point):
    return (_number(point.x), _number(point.y))


def _polyline(points, closed):
    rows = tuple(_point(point) for point in points)
    if closed:
        if len(rows) > 1 and rows[0] == rows[-1]:
            rows = rows[:-1]
        if not rows:
            raise ValueError("empty manufacturing polyline")
        return min(tuple(chain[index:] + chain[:index])
                   for chain in (rows, tuple(reversed(rows)))
                   for index in range(len(rows)))
    return min(rows, tuple(reversed(rows)))


def _primitive(primitive):
    layer = str(primitive.layer).upper()
    if layer in {"CHECK", "STOCK"}:
        return None
    prefix = (type(primitive).__name__, layer, primitive.color)
    if isinstance(primitive, PolylinePrimitive):
        return (*prefix, bool(primitive.closed), _polyline(primitive.points, primitive.closed))
    if isinstance(primitive, LinePrimitive):
        return (*prefix, tuple(sorted((_point(primitive.p1), _point(primitive.p2)))))
    if isinstance(primitive, CirclePrimitive):
        return (*prefix, _point(primitive.center), _number(primitive.radius))
    if isinstance(primitive, TextPrimitive):
        return (*prefix, primitive.text, _point(primitive.insert),
                _number(primitive.char_height), primitive.attachment_point)
    raise TypeError(f"unsupported manufacturing primitive: {type(primitive).__name__}")


def manufacturing_equivalence_payload(render_data, parameters):
    """Compare all machining primitives and final material, never bbox/count/name."""
    from shapely import normalize
    if not isinstance(parameters, ManufacturingParameters):
        raise TypeError("explicit ManufacturingParameters required")
    thickness = _number(parameters.thickness)
    if thickness <= 0:
        raise ValueError("manufacturing thickness must be positive")
    material = render_data.material
    if material is None or material.is_empty or not material.is_valid:
        raise ValueError("valid resolved final material required")
    primitives = [_primitive(item) for item in render_data.scene.primitives]
    machining = [item for item in primitives if item is not None]
    if not any(item[1] == "CUTTING" for item in machining):
        raise ValueError("resolved manufacturing scene has no CUTTING")
    # Coordinates are not rounded or rebuilt. Canonical ring/primitive ordering
    # only removes representation differences from identical existing geometry.
    payload = dict(
        schema="WHD_MANUFACTURING_EQUIVALENCE_V1",
        material=normalize(material).wkb_hex,
        primitives=sorted(machining, key=lambda row: json.dumps(row, ensure_ascii=False)),
        parameters=dict(_value(parameters), thickness=thickness),
    )
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def group_quantity_physical_demands(demands, parameters_by_source):
    """Sum only fully equivalent sheets; source identity remains in members."""
    groups = {}
    payloads = {}
    seen = set()
    for demand in tuple(demands):
        identity = (demand.version_id, demand.physical_id)
        if identity in seen:
            raise ValueError(f"duplicate physical demand: {identity}")
        seen.add(identity)
        if isinstance(demand.quantity, bool) or not isinstance(demand.quantity, int) or demand.quantity < 1:
            raise ValueError("physical demand quantity must be a positive integer")
        parameters = parameters_by_source[(demand.version_id, demand.source_part_id)]
        payload = manufacturing_equivalence_payload(demand.render_data, parameters)
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if key in payloads and payloads[key] != payload:
            raise ValueError("manufacturing equivalence hash collision")
        payloads[key] = payload
        groups.setdefault(key, []).append((demand, parameters))
    if not groups:
        raise ValueError("at least one physical demand is required")
    result = []
    for key, entries in sorted(groups.items()):
        entries.sort(key=lambda row: (row[0].version_id, row[0].source_part_id, row[0].physical_id))
        representative, parameters = entries[0]
        result.append(QuantityManufacturingGroup(
            key, parameters, tuple(row[0] for row in entries), representative.render_data))
    return tuple(result)
