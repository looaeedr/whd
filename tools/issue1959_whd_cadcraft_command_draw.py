"""#1959: WHD resolved holes -> new CADCraft drawing, isolated roundtrip proof only.

No existing DXF is opened; no WHD holes, sessions, CSV, or manufacturing
files are modified. CADCraft is a renderer and disposable geometry witness.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess

import ezdxf
from shapely.geometry import Polygon

from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedProfile, ResolvedRect


class CadcraftCommandProofError(ValueError):
    """WHD / CADCraft independent geometry check failed; do not use output."""


@dataclass(frozen=True)
class DrawInstruction:
    kind: str
    points: tuple[tuple[float, float], ...] = ()
    radius: float = 0.0


MAX_ENTITY_COUNT = 100
MAX_COORD = 1_000_000.0
TOLERANCE_MM = 0.00001


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise CadcraftCommandProofError("NON_NUMERIC_COORDINATE")
    f = float(value)
    if not math.isfinite(f) or abs(f) > MAX_COORD:
        raise CadcraftCommandProofError("OUT_OF_RANGE_COORDINATE")
    return f


def _point(point: object) -> tuple[float, float]:
    return (_number(point.x), _number(point.y))


def _ring(points: tuple[tuple[float, float], ...]) -> None:
    if not 3 <= len(points) <= 100:
        raise CadcraftCommandProofError("INVALID_CLOSED_PROFILE_VERTEX_COUNT")
    if len(set(points)) != len(points):
        raise CadcraftCommandProofError("DUPLICATE_OR_ZERO_LENGTH_VERTEX")
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 1e-8:
        raise CadcraftCommandProofError("SELF_INTERSECTING_OR_ZERO_AREA_PROFILE")
    if not polygon.exterior.is_simple:
        raise CadcraftCommandProofError("INVALID_PROFILE_BOUNDARY")


def from_whd_resolved(features: tuple[object, ...]) -> tuple[DrawInstruction, ...]:
    """Only accept already-validated WHD resolved geometry, never raw DXF tags."""
    if not features or len(features) > MAX_ENTITY_COUNT:
        raise CadcraftCommandProofError("INVALID_WHD_FEATURE_COUNT")
    result: list[DrawInstruction] = []
    for feature in features:
        if isinstance(feature, ResolvedCircle):
            radius = _number(feature.radius)
            if radius <= 0:
                raise CadcraftCommandProofError("NON_POSITIVE_RADIUS")
            result.append(DrawInstruction("circle", (_point(feature.center),), radius))
        elif isinstance(feature, ResolvedRect):
            width, height = _number(feature.width), _number(feature.height)
            if width <= 0 or height <= 0:
                raise CadcraftCommandProofError("NON_POSITIVE_RECTANGLE_DIMENSION")
            points = tuple(_point(p) for p in feature.points)
            _ring(points)
            result.append(DrawInstruction("rectangle", points))
        elif isinstance(feature, ResolvedProfile):
            if feature.layered_profiles:
                raise CadcraftCommandProofError("COMPLEX_LAYERED_PROFILE_NOT_SUPPORTED")
            points = tuple(_point(p) for p in feature.points)
            _ring(points)
            result.append(DrawInstruction("profile", points))
        else:
            raise CadcraftCommandProofError("UNSUPPORTED_WHD_FEATURE")
    return tuple(result)


def cadcraft_argv(cli: str, instructions: tuple[DrawInstruction, ...],
                  output: Path, preview: Path | None = None) -> list[str]:
    if not cli or not instructions or len(instructions) > MAX_ENTITY_COUNT:
        raise CadcraftCommandProofError("INVALID_COMMAND_REQUEST")
    args = [str(cli), "run", "--metric"]
    for item in instructions:
        if item.kind == "circle":
            command = "circle"
            payload = {"center": list(item.points[0]), "radius": item.radius}
        elif item.kind in ("rectangle", "profile"):
            command = "pline"
            payload = {"vertices": [list(p) for p in item.points], "closed": True}
        else:
            raise CadcraftCommandProofError("UNKNOWN_DRAW_INSTRUCTION")
        args.extend(("--cmd", command + " " + json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False)))
    args.extend(("--save", str(output)))
    if preview is not None:
        args.extend(("--export", str(preview)))
    return args


def _near(a: object, b: object) -> bool:
    return math.isclose(float(a), float(b), abs_tol=TOLERANCE_MM, rel_tol=0)


def verify_dxf(path: Path, expected: tuple[DrawInstruction, ...]) -> dict:
    if not path.is_file() or not expected:
        raise CadcraftCommandProofError("NO_OUTPUT_OR_NO_EXPECTED_GEOMETRY")
    doc = ezdxf.readfile(path)
    units = doc.header.get("$INSUNITS")
    if units != 4 or doc.header.get("$MEASUREMENT") != 1:
        raise CadcraftCommandProofError("MILLIMETRE_HEADER_MISMATCH")
    entities = list(doc.modelspace())
    if len(entities) != len(expected):
        raise CadcraftCommandProofError("ENTITY_COUNT_MISMATCH")
    observations = []
    for index, (e, item) in enumerate(zip(entities, expected)):
        if e.dxf.layer != "0" or not all(_near(a, b) for a, b in zip(e.dxf.get("extrusion", (0, 0, 1)), (0, 0, 1))):
            raise CadcraftCommandProofError("UNEXPECTED_LAYER_OR_EXTRUSION")
        if item.kind == "circle":
            if e.dxftype() != "CIRCLE":
                raise CadcraftCommandProofError("MISSING_CIRCLE")
            center = e.dxf.center
            if not (_near(center.x, item.points[0][0]) and _near(center.y, item.points[0][1])
                    and _near(center.z, 0) and _near(e.dxf.radius, item.radius)):
                raise CadcraftCommandProofError("CIRCLE_COORDINATE_OR_RADIUS_MISMATCH")
        else:
            if e.dxftype() != "LWPOLYLINE" or not e.closed:
                raise CadcraftCommandProofError("OPEN_OR_WRONG_ENTITY_PROFILE")
            if not _near(e.dxf.get("const_width", 0), 0):
                raise CadcraftCommandProofError("NONZERO_POLYLINE_WIDTH")
            verts = list(e.get_points("xyseb"))
            if len(verts) != len(item.points):
                raise CadcraftCommandProofError("VERTEX_COUNT_MISMATCH")
            for (x, y, sw, ew, bulge), (ex, ey) in zip(verts, item.points):
                if not (_near(x, ex) and _near(y, ey)
                        and _near(sw, 0) and _near(ew, 0) and _near(bulge, 0)):
                    raise CadcraftCommandProofError("POLYGON_COORDINATE_OR_BULGE_MISMATCH")
            if not _near(e.dxf.get("elevation", 0), 0):
                raise CadcraftCommandProofError("UNEXPECTED_ELEVATION")
        observations.append({"index": index, "kind": item.kind, "check": "PASS"})
    return {
        "status": "PASS",
        "scope": "new blank metric CADCraft drawing, isolated CHECK, not WHD manufacturing",
        "units": "millimetre",
        "entity_count": len(entities),
        "geometry": observations,
    }


def run_proof(cli: str, instructions: tuple[DrawInstruction, ...],
              output: Path, preview: Path | None = None) -> dict:
    """Create a NEW disposable CADCraft drawing and independently inspect it."""
    output = Path(output)
    if output.exists() or (preview is not None and Path(preview).exists()):
        raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE")
    output.parent.mkdir(parents=True, exist_ok=True)
    args = cadcraft_argv(cli, instructions, output, preview)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
        if proc.returncode != 0:
            raise CadcraftCommandProofError("CADCRAFT_COMMAND_FAILED:" + proc.stderr[-350:])
        result = verify_dxf(output, instructions)
        if preview is not None and not Path(preview).is_file():
            raise CadcraftCommandProofError("PREVIEW_NOT_CREATED")
        return result
    except Exception:
        output.unlink(missing_ok=True)
        if preview is not None:
            Path(preview).unlink(missing_ok=True)
        raise


def demo_instructions() -> tuple[DrawInstruction, ...]:
    """WHD actual ResolvedFeature types, not hand-built DXF geometry."""
    from ae_engine.sheetmetal_features import Vec2
    return from_whd_resolved((
        ResolvedCircle(center=Vec2(25, 30), radius=5),
        ResolvedRect(center=Vec2(70, 45), width=20, height=12, rotation_deg=90),
        ResolvedProfile(points=(
            Vec2(-20, 5), Vec2(-7, 4), Vec2(-5, 16), Vec2(-24, 20),
        )),
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cadcraft-cli", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = run_proof(args.cadcraft_cli, demo_instructions(), args.output, args.preview)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
