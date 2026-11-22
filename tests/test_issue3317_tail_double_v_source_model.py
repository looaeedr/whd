"""#3317 old unsupported +/-45-degree V MUST NOT be treated as user geometry.

Previous x/y tests reported formed gaps for a locally invented symmetric
triangle. They are intentionally replaced by one provenance gate after the
user rejected that flat outline. NO 3D or old-gap computation is done.
"""
from __future__ import annotations

import base64
import json

import pytest

from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_tail_dual_source_check import (
    project_tail_dual_v_same_source_check,
)
from ae_engine.v_miter_tail_flat_source_audit import (
    project_tail_original_flat_source_audit,
)
from tools.render_tail_flat_source_audit import (
    build_tail_flat_audit_pair,
)


def test_tail_unconfirmed_symmetric_v_must_not_enter_3d_or_machining():
    import gui
    import tkinter as tk

    root=tk.Tk()
    app=None
    try:
        app=gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("tail")
        app.ybottom1_var.set("48")
        snapshot=app._make_original_fold_designer_snapshot()
        spec,_=app._fold_designer_part_spec_from_payload("tail",snapshot)
        render=app._query_fold_designer_render_data("tail",snapshot)
        # This is the true source 2D audit, NOT the old folded model.
        audit=project_tail_original_flat_source_audit(spec,render)
        assert all(c.confirmed_source_cut_legs_xy is None
                   for c in audit.corner_rows)
        source_svg, source_json=build_tail_flat_audit_pair(
            audit,snapshot_baseline=app.baseline_var.get(),
        )
        result=json.loads(source_json)
        assert result["3D_or_formed_gap_from_legacy_assumption"]==(
            "NOT_RUN_NOT_USER_SPEC"
        )
        assert result["manufacturing_DXF"]=="NOT_ALLOWED"
        # Both possible operator first-fold choices are REJECTED
        # BEFORE entering the historical symmetric V 3D engine.
        for axis in ("x","y"):
            with pytest.raises(
                GeometryError,
                match="V_MITER_TAIL_OLD_SYMMETRIC_45_DEG_NOT_USER_CONFIRMED",
            ):
                project_tail_dual_v_same_source_check(
                    spec,render,
                    first_bend_axes={
                        "bottom_left":axis,"bottom_right":axis,
                    },
                )
        print(
            "WHD_3317_TAIL_SOURCE_2D_JSON="+
            json.dumps(result,ensure_ascii=False,sort_keys=True),
            flush=True,
        )
        encoded=base64.b64encode(source_svg).decode("ascii")
        for i in range(0,len(encoded),4096):
            print(
                "WHD_3317_TAIL_SOURCE_2D_SVG_BASE64_PART="+
                str(i//4096).zfill(4)+":"+encoded[i:i+4096],
                flush=True,
            )
        # Keep real V acceptance RED; this is not a license to merge or
        # automatically draw unknown user asymmetrical cut lines.
        pytest.fail(
            "V_MITER_TAIL_CONFIRMED_ASYMMETRIC_TWO_RAYS_NOT_YET_SOURCED_"
            "REVIEW_FACTORY_OLD_GUESS_FLAT_OVERLAY_BEFORE_3D",
            pytrace=False,
        )
    finally:
        if app is not None:
            designer=getattr(app,"fold_designer_app",None)
            if designer is not None:
                try: designer.root.destroy()
                except Exception: pass
        root.destroy()
