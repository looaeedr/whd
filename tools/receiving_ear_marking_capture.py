# -*- coding: utf-8 -*-
"""Capture real WHD source-driven 2D SIDE and assembled 3D EAR MARKING.

These are headless render captures from the program's DrawingScene and
FinalSceneRenderer, NOT screenshots of a live Windows Tk GUI.  They use the
same verified T2/BEND23 EAR and SIDE source fixtures as #1503 tests.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ae_engine.sheetmetal_drawing import LinePrimitive, PolylinePrimitive
from gui_modules.application.receiving_ear_side_2d import (
    project_receiving_ear_side_piece_2d_preview,
)
from phase6_final_scene_contracts import (
    AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
)
from phase6_final_scene_projection import _phase6_contract_profile_rows
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _save_2d(snapshot, geometry, root: Path):
    body = geometry.part("box_body").render_data
    for side in ("left_side", "right_side"):
        piece = next(p for p in body.pieces if p.role == side)
        displayed = project_receiving_ear_side_piece_2d_preview(
            snapshot, piece, piece_key="box_body:" + side,
            geometry=geometry, dimensions=(800., 1600., 350.),
            sheet_thickness=2.,
        )
        scene = displayed.render_data.scene
        expected = displayed.render_data.metadata["ear_side_mark_preview_count"]
        lines = [p for p in scene.primitives
                 if isinstance(p, LinePrimitive) and p.layer == "MARKING"]
        assert expected == 4 and len(lines) >= 4
        fig = Figure(figsize=(11.5, 8.5), dpi=135)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        material = displayed.render_data.material
        polygons = tuple(getattr(material, "geoms", (material,)))
        for poly in polygons:
            if poly.geom_type != "Polygon":
                continue
            x, y = poly.exterior.xy
            ax.fill(x, y, facecolor="#d1d5db", alpha=0.20)
            ax.plot(x, y, color="#334155", linewidth=1.8)
            for inner in poly.interiors:
                xx, yy = inner.xy
                ax.plot(xx, yy, color="#334155", linewidth=1)
        for prim in scene.primitives:
            if isinstance(prim, LinePrimitive):
                if prim.layer == "MARKING":
                    ax.plot((prim.p1.x, prim.p2.x), (prim.p1.y, prim.p2.y),
                            color="#eab308", linewidth=2.9)
                elif prim.layer == "BEND":
                    ax.plot((prim.p1.x, prim.p2.x), (prim.p1.y, prim.p2.y),
                            color="#0ea5e9", linewidth=1.2, linestyle="--")
            elif isinstance(prim, PolylinePrimitive) and prim.layer == "MARKING":
                xx = [p.x for p in prim.points]
                yy = [p.y for p in prim.points]
                if prim.closed and xx:
                    xx.append(xx[0]); yy.append(yy[0])
                ax.plot(xx, yy, color="#eab308", linewidth=2.2)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"WHD 2D SIDE: {side} | EAR contact MARKING (T2 / BEND23)")
        ax.set_xlabel("source-flat X (mm)")
        ax.set_ylabel("source-flat Y (mm)")
        ax.grid(False)
        fig.text(0.02, 0.018,
                 "Source-render evidence only; not a live Windows GUI screenshot or weld release.",
                 fontsize=9)
        fig.savefig(root / f"receiving_ear_2d_{side}.png", bbox_inches="tight")


def _save_3d(snapshot, geometry, root: Path):
    view = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    view._formed_ear_display_cache = None
    view.last_formed_ear_display_blocker = None
    formed = view._formed_ear_assembly_preview(snapshot, {"base_plate"})
    assert len(formed) == 2
    parts = tuple(
        AssemblyScenePart(
            part_key=p.part_key, render_data=p.render_data,
            x_profile=tuple(_phase6_contract_profile_rows(p.x_profile)),
            y_profile=tuple(_phase6_contract_profile_rows(p.y_profile)),
            placement=p.placement, offset=p.offset,
        )
        for p in geometry.parts
    )
    scene = AssemblySceneRenderData(
        assembly_parts=parts,
        visible_part_keys=("box_body", "head"),
        visible_box_body_piece_keys=("box_body:left_side", "box_body:right_side", "box_body:back"),
        formed_fixing_plate_skins=formed,
        preserve_endcap_core_origin=True,
    )
    fig = Figure(figsize=(14, 10), dpi=135)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d")
    renderer = Phase6FinalSceneRenderer(type("AxisHost", (), {"ax3d": ax})())
    renderer.render(FinalSceneViewRequest(
        render_data=scene, x_profile=(), y_profile=(), part_key="assembly",
        thickness=2.0, finished_dimensions=(800., 1600., 350.),
        alpha_bend=0.25,
    ))
    assert len(renderer.last_receiving_ear_marking_segments) == 8
    assert len(renderer.last_formed_ear_display_ids) == 2
    for azimuth, name in ((-52, "isometric"), (8, "front_inner")):
        ax.view_init(elev=22, azim=azimuth)
        fig.text(0.02, 0.018,
                 "Yellow: real EAR contact boundary projected on SIDE inside skin. "
                 "Preview only, not weld approval / live Windows GUI.",
                 fontsize=9)
        fig.savefig(root / f"receiving_ear_3d_{name}.png", bbox_inches="tight")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/ear_marking")
    args = parser.parse_args()
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    snapshot, geometry = _actual(_assembled)
    _save_2d(snapshot, geometry, root)
    _save_3d(snapshot, geometry, root)
    print("EAR_MARKING_HEADLESS_SCREENSHOTS_OK " + str(root))


if __name__ == "__main__":
    main()
