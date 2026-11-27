"""Both genuine Receiving EndCaps replay one physical shell through project Save/Open."""
from collections import Counter
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_export import resolved_physical_render_parts
from phase6_manufacturing_adapter import build_scene_payload_for_app
from tests.test_issue3414_scoped_marking_proto import _raw_write, _real_source, _resize


def test_native_receiving_head_tail_save_open_real_batch_and_reject_changed_cutting(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox

    from gui import Phase6PrimaryApplication

    source = _resize(_real_source(), 1)
    source["existing_parts"] = ["box_body", "head", "tail", "base_plate"]
    first = _raw_write(tmp_path / "endcaps.p6fold", source)
    output = tmp_path / "actual-dxf-batch"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda _title, msg, **_kw: errors.append(msg))
    try:
        host = Phase6PrimaryApplication(root)

        def load(path):
            host.load_phase6_project(path, open_designer=True)
            root.update()
            assert not errors
            return host.fold_designer_app

        def current_endcaps(app):
            head_tail = []
            for key in ("head", "tail"):
                app.activate_part(key)
                root.update()
                spec, _ = host._fold_designer_part_spec_from_payload(
                    key, build_scene_payload_for_app(app, key),
                )
                assert spec.model_name == "受電箱" and spec.is_tail is (key == "tail")
                assert len(spec.resolved_assembly_relief_cuts) == 2
                render = dict(resolved_physical_render_parts(
                    app._phase6_resolve_manufacturing_geometry(),
                ))[key]
                head_tail.append((key, render))
            return tuple(head_tail)

        def batch(rows):
            return api.save_verified_final_scene_batch_dxf(
                rows, output, overwrite=True, pre_commit_guard=lambda: None,
            )

        def reopen(rows, paths):
            accepted = {}
            for key, render in rows:
                path = Path(paths[key])
                doc = ezdxf.readfile(path)
                assert not doc.audit().errors and doc.units == ezdxf.units.MM
                model = doc.modelspace()
                outer, = model.query('LWPOLYLINE[layer=="CUTTING"]')
                assert outer.closed
                assert Counter((e.dxf.layer, e.dxftype()) for e in model if e.dxf.layer != "MARKING") == {
                    ("CUTTING", "LWPOLYLINE"): 1, ("CUTTING", "CIRCLE"): 3,
                    ("BEND", "LINE"): 9, ("CHECK", "MTEXT"): 1,
                }
                assert api.verify_saved_part_render_data_dxf(render, path).ok
                accepted[key] = (
                    tuple(outer.get_points("xy")),
                    sorted((tuple(e.dxf.center), e.dxf.radius)
                           for e in model.query('CIRCLE[layer=="CUTTING"]')),
                    sorted(tuple(sorted((tuple(e.dxf.start), tuple(e.dxf.end))))
                           for e in model.query('LINE[layer=="BEND"]')),
                )
            return accepted

        app = load(first)
        fresh = current_endcaps(app)
        first_shapes = reopen(fresh, batch(fresh))

        saved = tmp_path / "reopened.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kw: str(saved))
        app.project_file_menu.invoke(2)
        root.update()
        assert not errors and saved.is_file()

        restored = current_endcaps(load(saved))
        paths = batch(restored)
        assert reopen(restored, paths) == first_shapes
        previous = {name: Path(path).read_bytes() for name, path in paths.items()}
        serializer = api.save_scene_dxf

        def corrupt_tail(path, scene):
            serializer(path, scene)
            if not Path(path).name.lstrip(".").startswith("tail."):
                return
            doc = ezdxf.readfile(path)
            outer, = doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]')
            x, y = outer.get_points("xy")[0]
            outer[0] = (x + 1.0, y)
            doc.saveas(path)

        monkeypatch.setattr(api, "save_scene_dxf", corrupt_tail)
        with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED: tail"):
            batch(restored)
        assert {name: Path(path).read_bytes() for name, path in paths.items()} == previous
        assert set(output.iterdir()) == {Path(path) for path in paths.values()}
    finally:
        root.destroy()
