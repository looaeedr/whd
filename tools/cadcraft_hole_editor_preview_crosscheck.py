"""Independent real CADCraft CLI DXF roundtrip for Hole Editor preview PoC.

Only test-produced CHECK overlays are sent to CADCraft; no canonical DXF,
project file, or production geometry is modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, RectFeature, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_preview_bridge import build_hole_editor_cadcraft_scene


def emit(path: Path) -> None:
    surface = feature_surface_from_rect("cadcraft-smoke", Vec2(0, 0), Vec2(100, 80))
    features = (
        CircleFeature(diameter=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(25, 30), layer="CUTTING"),
        RectFeature(width=20, height=12,
                    anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(70, 45), layer="CUTTING"),
    )
    baseline = DrawingScene()
    baseline.add_polyline(((0, 0), (100, 0), (100, 80), (0, 80)),
                          layer="CUTTING", closed=True)
    baseline.add_line((10, 0), (10, 80), layer="BEND")
    expected = tuple(baseline.primitives)
    scene = build_hole_editor_cadcraft_scene(
        surface=surface, features=features, width=100, height=80,
        baseline_scene=baseline,
    )
    assert tuple(baseline.primitives) == expected
    path.parent.mkdir(parents=True, exist_ok=True)
    save_scene_dxf(str(path), scene)


def verify(source: Path, resaved: Path) -> None:
    # Reuse the repository's preexisting *independent* canonical entity witness.
    # This includes geometry, process layer, color, closed contours and circles.
    from tools.nfb_v5_cadcraft_crosscheck import _entities
    original = _entities(source)
    after = _entities(resaved)
    if original != after:
        raise ValueError(
            "CADCRAFT_HOLE_PREVIEW_ROUNDTRIP_DIFFERENCE "
            + repr({"lost": list((original - after).elements())[:8],
                    "extra": list((after - original).elements())[:8]})
        )
    types_and_layers = {(kind, layer) for kind, layer, _color, _shape in original}
    if (("LWPOLYLINE", "CUTTING") not in types_and_layers
            or ("LINE", "BEND") not in types_and_layers
            or ("CIRCLE", "CHECK") not in types_and_layers
            or ("LWPOLYLINE", "CHECK") not in types_and_layers):
        raise ValueError("CADCRAFT_HOLE_PREVIEW_REQUIRED_LAYERS_MISSING")
    print("CADCRAFT_HOLE_PREVIEW_ROUNDTRIP_PASS", sum(original.values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("emit", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("resaved", type=Path, nargs="?")
    args = parser.parse_args()
    if args.mode == "emit":
        emit(args.source)
    elif args.resaved is None:
        parser.error("verify requires resaved DXF")
    else:
        verify(args.source, args.resaved)


if __name__ == "__main__":
    main()
