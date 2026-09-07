from __future__ import annotations

import os
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="requires Tk display",
)


def _pump(root):
    root.update_idletasks()
    root.update()


def _same_material(actual, expected, *, tol=1e-6):
    assert actual is not None and expected is not None
    assert float(actual.symmetric_difference(expected).area) <= tol
    assert float(actual.area) == pytest.approx(float(expected.area), abs=tol)


def _largest_cutting_polyline(path: Path) -> Polygon:
    doc = ezdxf.readfile(path)
    rows = [
        entity
        for entity in doc.modelspace().query("LWPOLYLINE")
        if str(entity.dxf.layer).upper() == "CUTTING" and bool(entity.closed)
    ]
    assert rows, f"no closed CUTTING LWPOLYLINE in {path}"
    polygons = [
        Polygon([(float(x), float(y)) for x, y, *_rest in entity.get_points()])
        for entity in rows
    ]
    return max(polygons, key=lambda polygon: float(polygon.area))


def test_t48_3_divider_final_material_is_one_source_for_2d_3d_dxf_and_reload(tmp_path):
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        app.on_baseline_changed()
        _pump(root)

        designer = app.open_original_fold_designer()
        _pump(root)

        divider_key = next(
            key for key in designer.designer_workspace.available_parts
            if str(key).startswith("box_body:divider:")
        )
        designer.activate_part(divider_key)
        _pump(root)

        # Canonical manufacturing solve owns the final Divider material.
        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        canonical = resolved.part(divider_key).render_data
        relief = dict(canonical.metadata.get("divider_assembly_relief") or {})
        assert relief.get("verified") is True
        assert dict(dict(relief.get("evidence") or {}).get("placement") or {}).get("valid") is True
        assert len(list(canonical.material.exterior.coords)) > 5

        # 2D active-sheet query must read the exact resolved material.
        sheet_2d = bridge._phase6_query_final_render_data(designer)
        _same_material(sheet_2d.material, canonical.material)

        # Single-part 3D must consume that same material, not reconstruct CUTTING.
        designer._phase6_3d_display_mode = "single"
        bridge._phase6_render_true_cutting_mesh(designer)
        _same_material(designer.final_scene_view.last_cutting_material, canonical.material)

        # Assembly 3D must also receive the same resolved Divider render data.
        assembly = bridge._phase6_query_assembly_render_data(designer)
        assembly_divider = next(
            part.render_data for part in assembly.assembly_parts
            if part.part_key == divider_key
        )
        _same_material(assembly_divider.material, canonical.material)

        # DXF is a sink of the already-resolved geometry.  Read the actual file
        # back and compare its CUTTING outer contour with canonical final material.
        outputs = save_resolved_manufacturing_geometry_dxf(
            resolved, tmp_path / "dxf", overwrite=True
        )
        divider_dxf = Path(outputs[divider_key])
        assert divider_dxf.is_file()
        exported_outer = _largest_cutting_polyline(divider_dxf)
        canonical_outer = Polygon(canonical.material.exterior.coords)
        assert float(exported_outer.symmetric_difference(canonical_outer).area) <= 1e-6

        dxf_doc = ezdxf.readfile(divider_dxf)
        cutting_circles = [
            entity for entity in dxf_doc.modelspace().query("CIRCLE")
            if str(entity.dxf.layer).upper() == "CUTTING"
        ]
        assert len(cutting_circles) == 6

        # Save/reload stores authoritative state, not one probe polygon.  Reload
        # through the real main-GUI project path and require deterministic solve.
        payload = bridge._phase6_build_project_snapshot(designer)
        project_path = project.write_project(tmp_path / "receiving-divider.p6fold", payload)
        reloaded = app.load_phase6_project(project_path, open_designer=True)
        designer = reloaded
        _pump(root)

        assert divider_key in designer.designer_workspace.available_parts
        designer.activate_part(divider_key)
        _pump(root)
        reloaded_resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        reloaded_divider = reloaded_resolved.part(divider_key).render_data
        _same_material(reloaded_divider.material, canonical.material)

        reloaded_relief = dict(reloaded_divider.metadata.get("divider_assembly_relief") or {})
        assert reloaded_relief.get("verified") is True
        placement = dict(dict(reloaded_relief.get("evidence") or {}).get("placement") or {})
        assert placement.get("valid") is True
        assert tuple(
            str(key) for key in designer.designer_workspace.available_parts
            if str(key).startswith("box_body:")
        )
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
