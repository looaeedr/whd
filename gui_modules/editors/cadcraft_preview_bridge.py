"""Opt-in, read-only CADCraft preview of the existing Hole Editor.

The WHD 2D editor/session and its manufacturing/DXF authority remain unchanged.
CADCraft receives only a disposable CHECK-layer inspection copy; drawings
edited in CADCraft are NEVER imported, committed, or written to baseline files.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import tempfile

import ezdxf
from .cadcraft_paths import cadcraft_binary
from ae_engine.dxf_serialization import add_drawing_scene_to_dxf, setup_dxf_layers
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_features import (
    ResolvedCircle, ResolvedRect, ResolvedProfile, resolve_surface_features,
)


class CadcraftPreviewError(ValueError):
    """CADCraft is unavailable or the current preview is not safe to export."""


def find_cadcraft_gui(*, configured=None):
    """Prefer WHD's local ./cadcraft portable directory, not PATH or env."""
    path = (Path(configured).expanduser() if configured is not None
            else cadcraft_binary("gui"))
    if not path.is_file():
        raise CadcraftPreviewError(
            f"找不到 CADCraft 程式：{path}。"
            "請將 CADCraft 免安裝版放在 WHD 主程式旁的 cadcraft 資料夾。"
        )
    return str(path)


def _points(points):
    return tuple((float(point.x), float(point.y)) for point in points)


def build_hole_editor_cadcraft_scene(*, surface, features, width, height, baseline_scene=None):
    """Produce an inspection-only copy from the active 2D editor context.

    Geometry is resolved by WHD's existing feature authority. The editor's
    current holes are placed on CHECK, never on manufacturing CUTTING/BEND.
    Unsupported/invalid geometry fails before a preview or source change.
    """
    w, h = float(width), float(height)
    if not all(math.isfinite(value) and value > 0 for value in (w, h)):
        raise CadcraftPreviewError("板件寬高不是有效數值")
    if baseline_scene is not None and not isinstance(baseline_scene, DrawingScene):
        raise CadcraftPreviewError("板件基準圖不是 DrawingScene，無法安全預覽")
    scene = DrawingScene()
    if baseline_scene is not None:
        scene.extend(tuple(baseline_scene.primitives))  # snapshot, never mutate baseline
    else:
        polygon = getattr(surface, "polygon", None)
        if polygon is None or polygon.is_empty:
            raise CadcraftPreviewError("目前板件沒有可檢視的實體表面")
        polygons = (polygon,) if polygon.geom_type == "Polygon" else tuple(
            polygon.geoms if polygon.geom_type == "MultiPolygon" else ()
        )
        if not polygons:
            raise CadcraftPreviewError("目前板件的表面輪廓不支援 CADCraft 預覽")
        for part in polygons:
            for ring in (part.exterior, *part.interiors):
                scene.add_polyline(tuple(ring.coords)[:-1], layer="CHECK", closed=True)
    try:
        resolved = resolve_surface_features(surface, tuple(features), w, h)
    except (ValueError, TypeError) as exc:
        raise CadcraftPreviewError(f"開孔資料未通過既有 WHD 定位驗證：{exc}") from exc
    for feature in resolved:
        if isinstance(feature, ResolvedCircle):
            scene.add_circle((feature.center.x, feature.center.y), feature.radius, layer="CHECK")
        elif isinstance(feature, ResolvedRect):
            scene.add_polyline(_points(feature.points), layer="CHECK", closed=True)
        elif isinstance(feature, ResolvedProfile):
            # DXF-profile records already carry their own closed/open witnesses.
            if feature.layered_profiles:
                for _layer, points, closed in feature.layered_profiles:
                    scene.add_polyline(_points(points), layer="CHECK", closed=closed)
            elif len(feature.points) >= 3:
                scene.add_polyline(_points(feature.points), layer="CHECK", closed=True)
            else:
                raise CadcraftPreviewError("複合開孔輪廓無法安全判定閉合狀態")
        else:
            raise CadcraftPreviewError(f"尚未支援的孔型：{type(feature).__name__}")
    if not scene.primitives:
        raise CadcraftPreviewError("沒有可輸出的圖面")
    return scene


def save_cadcraft_preview_dxf(path, scene):
    """Keep WHD millimetre coordinates explicit for the external DXF viewer."""
    if not isinstance(scene, DrawingScene):
        raise TypeError("CADCraft preview requires a resolved DrawingScene")
    document = ezdxf.new("R2010", units=ezdxf.units.MM)
    setup_dxf_layers(document)
    add_drawing_scene_to_dxf(document.modelspace(), scene)
    document.saveas(str(path))


def open_hole_editor_cadcraft_preview(
    *, surface, features, width, height, baseline_scene=None,
    executable=None, output_dir=None, launcher=None,
):
    """Start CADCraft only on explicit button click; do not block Tk.

    The disposable .dxf remains in the OS temp directory so the external app
    can read it after this call returns. No CADCraft output is read back.
    """
    binary = find_cadcraft_gui(configured=executable)
    scene = build_hole_editor_cadcraft_scene(
        surface=surface, features=features, width=width, height=height,
        baseline_scene=baseline_scene,
    )
    directory = Path(output_dir) if output_dir is not None else Path(
        tempfile.mkdtemp(prefix="whd-cadcraft-preview-")
    )
    directory.mkdir(parents=True, exist_ok=True)
    # mkstemp guarantees one unique, non-canonical path even across editors.
    fd, filename = tempfile.mkstemp(prefix="whd-inspection-", suffix=".dxf", dir=directory)
    os.close(fd)
    target = Path(filename)
    try:
        save_cadcraft_preview_dxf(target, scene)
        spawn = launcher if launcher is not None else subprocess.Popen
        spawn([binary, str(target)])  # argv only: never shell=True
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "CadcraftPreviewError", "find_cadcraft_gui",
    "build_hole_editor_cadcraft_scene", "save_cadcraft_preview_dxf",
    "open_hole_editor_cadcraft_preview",
]
