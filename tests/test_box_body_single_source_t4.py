from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import ast
import os

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return "\n".join(lines[item.lineno - 1:item.end_lineno])
    raise AssertionError(f"missing {class_name}.{method_name}")


def _receiving_values():
    from ae_engine.cabinet_types import receiving

    values = receiving.apply_family_defaults({"t": 2.0})
    values["t"] = 2.0
    return values


def _receiving_profile_and_spec(*, structure=False):
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    values = _receiving_values()
    profile = build_box_body_profile(values)
    state = receiving.resolve_box_body_structure_state() if structure else {}
    spec = BoxBodyPartSpec(
        width=float(values["w"]),
        height=float(values["h"]),
        depth=float(values["d"]),
        thickness=float(values["t"]),
        frame_width=float(values["fw"]),
        model_name="受電箱",
        zl1=float(values["zl1"]),
        zl2=float(values["zl2"]),
        zr1=float(values.get("zr1", 15.0)),
        zr2=float(values["zr2"]),
        z_comp=float(values.get("z_comp", 2.0)),
        fold_profile=profile_to_fold_segments(profile),
        structure_state=state,
        head_ybottom1=float(values.get("ybottom1", 15.0)),
        tail_ybottom1=float(values.get("ybottom1", 15.0)),
    )
    return values, profile, spec


def test_t4_active_box_body_consumers_have_no_legacy_scalar_fallback():
    gui_path = ROOT / "gui.py"

    update_src = _class_method_source(gui_path, "BoxCalculatorGUI", "update_calculations")
    assert "calculate_z_length(" not in update_src

    draw_src = _class_method_source(gui_path, "BoxCalculatorGUI", "draw_box_body")
    assert "build_box_body_result(" not in draw_src
    assert "build_box_body_result_from_fold_profile(" not in draw_src
    assert "_authoritative_render_data(" in draw_src
    assert "box_body_face_contexts" in draw_src

    hole_src = _class_method_source(gui_path, "BoxCalculatorGUI", "open_part_hole_editor")
    early = hole_src.index('if part_key == "box_body":')
    early_return = hole_src.index("return", early)
    legacy = hole_src.index("build_box_body_result(", early_return)
    assert early < early_return < legacy, "legacy Box Body generic-editor branch must remain unreachable"


def test_t4_receiving_canonical_profile_and_multipart_blanks_are_single_source():
    from ae_engine import manufacturing_api

    _values, profile, spec = _receiving_profile_and_spec(structure=True)
    keys = [row.get("phase6_key") for row in profile]
    lengths = [float(row["len"]) for row in profile]

    assert keys == [
        "zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"
    ]
    assert "zr1" not in keys
    assert lengths == pytest.approx([22.0, 20.0, 25.0, 346.0, 796.0, 346.0, 25.0, 16.0])
    assert sum(lengths) == pytest.approx(1596.0)

    data = manufacturing_api.build_box_body_structure_render_data(spec)
    canonical = data.canonical_strip_render_data
    minx, _miny, maxx, _maxy = map(float, canonical.material.bounds)
    assert maxx - minx == pytest.approx(1596.0)

    assert tuple(piece.role for piece in data.pieces) == ("left_side", "back", "right_side")
    blanks = manufacturing_api.measure_unfolded_blanks(data, part_key="box_body")
    assert len(blanks) == 3
    assert all(blank.width > 0.0 and blank.height > 0.0 for blank in blanks)
    for piece, blank in zip(data.pieces, blanks):
        assert blank.width == pytest.approx(piece.material_dimensions[0])
        assert blank.height == pytest.approx(piece.material_dimensions[1])


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_t4_receiving_designer_controller_project_profile_owner_parity():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks()
        root.update()

        controller_profile = app.workspace_controller.box_body_profile()
        assert controller_profile
        assert "zr1" not in [row.get("phase6_key") for row in controller_profile]

        designer = app.open_original_fold_designer()
        designer.root.withdraw()
        designer.root.update_idletasks()
        designer.root.update()
        exported = designer.export_phase6_snapshot()
        exported_profile = exported["box_body_profile"]

        project_snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        project_profile = project_snapshot["workspace"]["box_body_profile"]

        assert exported_profile == controller_profile
        assert project_profile == controller_profile
        assert project_snapshot["box_body_profile"] == controller_profile

        # Apply the committed project snapshot and verify the one owner is unchanged.
        app._apply_phase6_project_snapshot(deepcopy(project_snapshot))
        assert app.workspace_controller.box_body_profile() == controller_profile
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


def test_t4_arbitrary_box_body_render_and_dxf_share_cutting_bbox_and_bends(tmp_path):
    import ezdxf

    from ae_engine import manufacturing_api
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from phase6_fold_profiles import profile_to_fold_segments

    profile = [
        {"len": 11.0, "angle": 45.0, "phase6_key": "outer_extra_left"},
        {"len": 25.0, "angle": -90.0, "phase6_key": "fw_left"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_left"},
        {"len": 396.0, "angle": -90.0, "core": "W", "phase6_key": "w"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_right"},
        {"len": 25.0, "angle": -45.0, "phase6_key": "fw_right"},
        {"len": 9.0, "phase6_key": "outer_extra_right"},
    ]
    spec = BoxBodyPartSpec(
        width=400.0, height=600.0, depth=250.0, thickness=2.0,
        frame_width=25.0, model_name=None,
        fold_profile=profile_to_fold_segments(profile),
    )
    data = manufacturing_api.build_part_render_data(spec, ManufacturingContext())

    expected_width = sum(float(row["len"]) for row in profile)
    minx, miny, maxx, maxy = map(float, data.material.bounds)
    assert maxx - minx == pytest.approx(expected_width)
    assert len([p for p in data.scene.primitives if getattr(p, "layer", "") == "BEND"]) == len(profile) - 1

    output = tmp_path / "box-body-authoritative.dxf"
    manufacturing_api.save_part_render_data_dxf(data, output, overwrite=True)
    doc = ezdxf.readfile(output)

    cutting_points = []
    bend_positions = []
    for entity in doc.modelspace():
        layer = str(entity.dxf.layer).upper()
        if layer == "CUTTING" and entity.dxftype() == "LWPOLYLINE":
            cutting_points.extend((float(x), float(y)) for x, y in entity.get_points("xy"))
        elif layer == "BEND" and entity.dxftype() == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            assert float(start.x) == pytest.approx(float(end.x))
            bend_positions.append(float(start.x))

    assert cutting_points
    dx = [p[0] for p in cutting_points]
    dy = [p[1] for p in cutting_points]
    assert (min(dx), min(dy), max(dx), max(dy)) == pytest.approx((minx, miny, maxx, maxy))

    expected_bends = sorted(
        float(guide.position) for guide in data.fold_guides if str(guide.axis) == "x"
    )
    assert sorted(bend_positions) == pytest.approx(expected_bends)
