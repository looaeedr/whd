"""A real Receiving Head stays exactly one material blank through Save/Open."""
from dataclasses import replace

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from phase6_manufacturing_adapter import build_scene_payload_for_app
from tests.test_issue3414_scoped_marking_proto import _raw_write, _real_source, _resize


def test_native_receiving_head_canonical_cutting_save_open_replace_and_isolation(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox

    import gui

    source = _resize(_real_source(), 1)
    source["existing_parts"] = ["box_body", "head", "base_plate"]
    first = _raw_write(tmp_path / "head.p6fold", source)
    target = tmp_path / "ordinary-head.dxf"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = gui.Phase6PrimaryApplication(root)
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append(message))

        def load(path):
            host.load_phase6_project(path, open_designer=True)
            root.update()
            app = host.fold_designer_app
            app.activate_part("head")
            root.update()
            return app

        def save_as(app, name):
            saved = tmp_path / name
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
            app.project_file_menu.invoke(2)
            root.update()
            assert not errors and saved.is_file()
            return saved

        def request(app):
            spec, context = host._fold_designer_part_spec_from_payload(
                "head", build_scene_payload_for_app(app, "head"),
            )
            assert spec.model_name == "受電箱" and spec.is_tail is False
            assert spec.fold_profile_x and spec.fold_profile_y and not spec.holes
            assert len(spec.resolved_assembly_relief_cuts) == 2
            return spec, replace(context, overwrite=True)

        def export(spec, context):
            host._export_authoritative_part(spec, target, context)
            doc = ezdxf.readfile(target)
            assert doc.header["$INSUNITS"] == ezdxf.units.MM
            msp = doc.modelspace()
            outer, = msp.query('LWPOLYLINE[layer=="CUTTING"]')
            assert outer.closed
            assert not msp.query('*[layer=="MARKING"]')
            circles = sorted((tuple(e.dxf.center), e.dxf.radius)
                             for e in msp.query('CIRCLE[layer=="CUTTING"]'))
            bends = sorted(tuple(sorted((tuple(e.dxf.start), tuple(e.dxf.end))))
                           for e in msp.query('LINE[layer=="BEND"]'))
            return Polygon(list(outer.get_points("xy"))), circles, bends

        app = load(first)
        fresh, context = request(app)
        boundary, holes, bends = export(fresh, context)
        assert boundary.bounds == (0, 0, 822, 402)
        assert boundary.area == pytest.approx(326354)
        assert [r for _, r in holes] == pytest.approx([3.2, 2.5, 3.2])
        assert len(bends) == 9

        app = load(save_as(app, "opened.p6fold"))
        reopened, context = request(app)
        assert reopened.resolved_assembly_relief_cuts == fresh.resolved_assembly_relief_cuts
        reopened_boundary, reopened_holes, reopened_bends = export(reopened, context)
        assert reopened_boundary.equals(boundary)
        assert reopened_holes == holes and reopened_bends == bends

        assert app.remove_part("head")
        root.update()
        app.add_part("head")
        root.update()
        app = load(save_as(app, "replacement.p6fold"))
        replacement, context = request(app)
        assert replacement.resolved_assembly_relief_cuts == fresh.resolved_assembly_relief_cuts
        replacement_boundary, replacement_holes, replacement_bends = export(replacement, context)
        assert replacement_boundary.equals(boundary)
        assert replacement_holes == holes and replacement_bends == bends

        # The native route still cannot publish changed actual CUTTING bytes.
        original_bytes = target.read_bytes()
        serializer = api.save_scene_dxf

        def corrupt(path, scene):
            serializer(path, scene)
            doc = ezdxf.readfile(path)
            outline, = doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]')
            x, y = outline.get_points("xy")[0]
            outline[0] = (x + 1, y)
            doc.saveas(path)

        monkeypatch.setattr(api, "save_scene_dxf", corrupt)
        with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
            export(replacement, context)
        assert target.read_bytes() == original_bytes
        assert not list(tmp_path.glob(".whd-dxf-*"))
    finally:
        root.destroy()
