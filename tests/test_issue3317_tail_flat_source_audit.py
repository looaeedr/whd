"""#3317 REAL Factory Tail 2D only: original, old guess, UNKNOWN new V.

The user rejected the +/-45deg V. This test must not execute any old
Tail dual-V 3D / seam-gap / mating-face trial, or assert a guessed cut.
"""
from __future__ import annotations

import base64
import json

import pytest
from shapely.geometry import Polygon

from ae_engine.v_miter_tail_flat_source_audit import (
    project_tail_original_flat_source_audit,
)
from tools.render_tail_flat_source_audit import build_tail_flat_audit_pair


def test_3317_real_tail_factory_cutting_versus_disowned_45deg_guess_source_2d():
    import tkinter as tk
    import gui

    root=tk.Tk()
    app=None
    try:
        app=gui.BoxCalculatorGUI(root)
        # This is the existing reproducible LOCALX "自訂" Factory test
        # snapshot, NOT an uploaded real commissioned-project box type.
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("tail")
        app.ybottom1_var.set("48")
        snapshot=app._make_original_fold_designer_snapshot()
        spec,_=app._fold_designer_part_spec_from_payload("tail",snapshot)
        render=app._query_fold_designer_render_data("tail",snapshot)
        source=tuple(render.scene.primitives)
        audit=project_tail_original_flat_source_audit(spec,render)

        assert audit.original_scene is render.scene
        assert audit.original_scene_primitives == source
        assert tuple(render.scene.primitives)==source
        assert audit.source_proof_status=="FACTORY_FINALSCENE_ORIGINAL_MATCH"
        assert audit.candidate_geometry_status.startswith("NOT_DETERMINED")
        assert audit.original_factory_cutting.geom_type=="Polygon"
        assert audit.original_factory_mother.geom_type=="Polygon"
        assert audit.historical_symmetric_cutting.geom_type=="Polygon"
        assert audit.original_factory_cutting.area>0
        assert audit.historical_symmetric_cutting.area>0
        assert len(audit.corner_rows)==2
        assert spec.is_tail
        assert spec.fold_bottom == pytest.approx(48)
        assert spec.fold_left == pytest.approx(15)
        assert spec.fold_right == pytest.approx(15)

        for row,side_x,apex_x in zip(
            audit.corner_rows,
            (0.,audit.original_factory_cutting.bounds[2]),
            (15.,audit.original_factory_cutting.bounds[2]-15.),
        ):
            assert row.outer_side_x_mm==pytest.approx(side_x)
            assert row.nominal_apex.x==pytest.approx(apex_x)
            assert row.nominal_apex.y==pytest.approx(48)
            # This is an old unapproved symmetric guess ONLY; these
            # numeric endpoints are evidence of the erroneous branch.
            assert row.historical_low_outer.y==pytest.approx(33)
            assert row.historical_high_outer.y==pytest.approx(63)
            assert row.actual_factory_removed_corner.area>0
            assert row.historical_symmetric_removed_wedge.area>0
            assert row.historical_added_vs_factory.area>=0
            assert row.historical_removed_vs_factory.area>=0
            assert row.confirmed_low_outer_y_mm is None
            assert row.confirmed_high_outer_y_mm is None
            assert row.confirmed_source_cut_legs_xy is None
            assert "UNCONFIRMED" in row.status
            assert all(
                x==pytest.approx(apex_x) for x,y in row.real_side_bend_xy
            )
            assert all(
                y==pytest.approx(48) for x,y in row.real_bottom_bend_xy
            )
        svg,data=build_tail_flat_audit_pair(
            audit,snapshot_baseline=app.baseline_var.get(),
        )
        report=json.loads(data)
        assert report["snapshot_baseline_selection"]=="自訂"
        assert report["snapshot_is_individual_user_project"] is False
        assert report["current_factory_cutting_changed"] is False
        assert report["strict_V_contract"]["asymmetric_slopes"]==(
            "ALLOWED_NOT_AUTOMATICALLY_45_DEGREES"
        )
        assert report["manufacturing_DXF"]=="NOT_ALLOWED"
        assert report["3D_or_formed_gap_from_legacy_assumption"]==(
            "NOT_RUN_NOT_USER_SPEC"
        )
        assert all(
            c["confirmed_two_angled_cut_edges_xy"] is None and
            c["confirmed_retained_and_removed_new_stock"] is None
            for c in report["left_and_right"]
        )
        markup=svg.decode("utf-8")
        assert markup.startswith("<svg ")
        assert markup.endswith("</svg>")
        assert markup.count('preserveAspectRatio="xMidYMid meet"')==6
        # All SIX source panels are exactly the same 49x86-mm UV window.
        assert markup.count("49.000 86.000")==6
        assert "OLD GUESS" in markup
        assert "Factory" in markup
        assert "33/63" in markup or "33" in markup and "63" in markup
        assert "未確定" in markup
        assert "尚無使用者確認的切線" in markup
        # Exact same-run JSON and SVG are logged for github artifact
        # preservation; no new guessed V CUTTING is ever emitted.
        print(
            "WHD_3317_TAIL_SOURCE_2D_JSON="+
            json.dumps(report,ensure_ascii=False,sort_keys=True),
            flush=True,
        )
        encoded=base64.b64encode(svg).decode("ascii")
        for i in range(0,len(encoded),4096):
            print(
                "WHD_3317_TAIL_SOURCE_2D_SVG_BASE64_PART="+
                str(i//4096).zfill(4)+":"+encoded[i:i+4096],
                flush=True,
            )
    finally:
        if app is not None:
            designer=getattr(app,"fold_designer_app",None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
