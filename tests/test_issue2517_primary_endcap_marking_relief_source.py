"""The ordinary marking owner must bind the same verified EndCap as DXF."""
from copy import deepcopy
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from gui import Phase6PrimaryApplication
from gui_modules.project.export_actions import export_selected_dxf
from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
from phase6_project_file import read_project
from phase6_manufacturing_adapter import (
    build_manufacturing_request, build_scene_payload_for_app,
    operator_finished_dimensions_for_app,
)
from tests.test_issue3414_root_owner_native_modal import _actual_editor_confirm
from tests.test_issue3414_scoped_marking_proto import _raw_write
from tests.test_issue2517_direct_door_partspec_original_source_engine_gate import _row
import fold_designer_bridge as bridge


def _head_request(app):
    request = build_manufacturing_request(
        app, scene_payload_builder=lambda key: build_scene_payload_for_app(app, key),
        render_data_provider=app._scene_query_callback,
        part_spec_provider=app._part_spec_query_callback,
        finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(app, key),
    )
    result = api.resolve_manufacturing_request(request)
    raw = next(part for part in request.parts if part.part_key == "head").render_data
    resolved = next(part for part in result.geometry.parts if part.part_key == "head").render_data
    solution = result.diagnostics.relief_solutions["head"]
    assert solution.verified and not solution.cut_polygon_2d.is_empty
    return raw, resolved, solution, result.geometry


def test_primary_head_marking_uses_verified_relief_and_rejects_real_relief_change(tmp_path, monkeypatch):
    row = _row()
    row.update(zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=-10.0,
               multi_door_enabled=False, existing_parts=["box_body", "head", "door"])
    original = _raw_write(tmp_path / "original.p6fold", row)
    failures = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: failures.append((title, text)))
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(original))
        app.project_file_menu.invoke(0)
        root.update()
        app.activate_part("head")
        root.update()
        raw, resolved, solution, geometry = _head_request(app)
        assert raw.material.wkb != resolved.material.wkb
        editor = host.open_part_hole_editor("head")
        root.update()
        assert editor is not None and not failures, failures
        callback = editor._manual_marking_place
        state = dict(zip(callback.__code__.co_freevars, (c.cell_contents for c in callback.__closure__)))['s']
        receipt = state.manual_marking_draft
        assert receipt.output_capability == "verified_normal"
        assert receipt.context.render_data.material.wkb == resolved.material.wkb
        assert tuple(receipt.context.render_data.fold_guides) == tuple(resolved.fold_guides)
        before_seal = receipt.source_sha256
        point = receipt.context.render_data.material.representative_point()
        x, y = state.canvas_view.transform.world_to_canvas(Vec2(point.x, point.y))
        state.manual_mark_length.set("8")
        state.manual_mark_angle.set("82")
        editor._manual_marking_controls[0].invoke()
        host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        mark, = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists() and not failures, failures
        snapshot = current_workspace_marking_source(app)
        owner = api.resolve_workspace_physical_root_owner(snapshot, "head")
        record = deepcopy(api.read_workspace_marking_owner_record(snapshot, owner))
        assert record["source_sha256"] == before_seal
        assert record["features"] == (mark,)
        saved = tmp_path / "saved.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        app.project_file_menu.invoke(2)
        root.update()
        assert not failures and saved.is_file(), failures
        saved_sha = hashlib.sha256(saved.read_bytes()).hexdigest()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        app.project_file_menu.invoke(0)
        root.update()
        assert host.fold_designer_app is app and not failures, failures
        raw2, resolved2, solution2, geometry2 = _head_request(app)
        assert raw2.material.wkb == raw.material.wkb
        assert resolved2.material.wkb == resolved.material.wkb
        assert solution2.cut_polygon_2d.wkb == solution.cut_polygon_2d.wkb
        assert api.read_workspace_marking_owner_record(read_project(saved)["snapshot"], owner) == record
        assert api.open_selected_ordinary_marking_modal_source(
            current_workspace_marking_source(app), geometry2, "head").source_sha256 == before_seal
        flags = ("z", "head", "tail", "door", "base_plate", "ib", "ib_door")
        for key in flags:
            getattr(host, f"export_{key}_var").set(key == "head")
        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
        export_selected_dxf(host)
        assert not failures, failures
        path, = out.glob("*.dxf")
        dxf = ezdxf.readfile(path)
        assert dxf.units == 4 and not dxf.audit().errors
        ink, = dxf.modelspace().query('LWPOLYLINE[layer=="MARKING"]')
        assert tuple(map(tuple, ink.get_points("xy"))) == tuple((p.x, p.y) for p in mark.points)
        prior = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}

        # Actual operator assembly transaction: same raw sheet, another
        # verified Registry rule and different physical relief. No synthetic
        # cut, changed rounding, or re-sealing is permitted.
        app.assembly_type_var.set("嵌入")
        bridge._phase6_on_assembly_type_selected(app)
        root.update()
        raw3, resolved3, solution3, geometry3 = _head_request(app)
        assert raw3.material.wkb == raw2.material.wkb
        assert solution3.rule_id != solution2.rule_id
        assert not solution3.cut_polygon_2d.equals(solution2.cut_polygon_2d)
        assert not resolved3.material.equals(resolved2.material)
        current = current_workspace_marking_source(app)
        assert api.read_workspace_marking_owner_record(current, owner) == record
        assert api.open_selected_ordinary_marking_modal_source(current, geometry3, "head").source_sha256 != before_seal
        assert host.open_part_hole_editor("head") is None
        assert any("ROOT_MARKING_SOURCE_STALE" in str(text) for _, text in failures), failures
        failures.clear()
        export_selected_dxf(host)
        assert any("ROOT_MARKING_SOURCE_STALE" in str(text) for _, text in failures), failures
        assert api.read_workspace_marking_owner_record(current_workspace_marking_source(app), owner) == record
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()} == prior
        assert hashlib.sha256(saved.read_bytes()).hexdigest() == saved_sha
        print("verified relief source preserved", solution.rule_id, before_seal,
              "changed rule rejected", solution3.rule_id, "raw unchanged; DXF SHA256", prior)
    finally:
        root.destroy()
