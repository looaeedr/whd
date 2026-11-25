"""Exercise the real ordinary Head/Tail editor for saved group copying."""
import tkinter as tk
from tkinter import filedialog, simpledialog

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from gui import Phase6PrimaryApplication
from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
from gui_modules.editors.hole_editor import messagebox
from gui_modules.project.export_actions import export_selected_dxf
from phase6_project_file import read_project
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm
from tests.test_issue3414_scoped_marking_proto import _raw_write, _real_source, _resize


@pytest.mark.parametrize("same_project", [False, True], ids=["other-project", "same-project"])
def test_existing_editor_copies_saved_head_group_into_distinct_tail(tmp_path, monkeypatch, same_project):
    def initial(key):
        snapshot = _resize(_real_source(), 1)
        snapshot["existing_parts"] = ["box_body", "base_plate", "head", "tail"] if same_project else ["box_body", "base_plate", key]
        return _raw_write(tmp_path / f"original-{key}.p6fold", snapshot)

    head_input, tail_input = initial("head"), initial("tail")
    head_saved = tmp_path / "marked-head.p6fold"
    tail_saved = tmp_path / "marked-tail.p6fold"
    tail_final = tmp_path / "copied-tail.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu
        failures = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **_: failures.append((title, text)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)

        def open_project(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(path))
            menu.invoke(0)
            root.update()
            assert host.project_controller.project_path == str(path)

        def save_project(path):
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_: str(path))
            menu.invoke(2)
            root.update()
            assert path.is_file() and not failures, failures
            return read_project(path)["snapshot"]

        def open_editor(key):
            app.activate_part(key)
            root.update()
            editor = host.open_part_hole_editor(key)
            root.update()
            callback = editor._manual_marking_place
            state = dict(zip(callback.__code__.co_freevars,
                             (cell.cell_contents for cell in callback.__closure__)))["s"]
            assert state.manual_marking_draft.output_capability == "verified_normal"
            return editor, state

        def click(state, point):
            x, y = state.canvas_view.transform.world_to_canvas(point)
            host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            root.update()

        def center(state):
            p = state.manual_marking_draft.context.render_data.material.representative_point()
            return Vec2(p.x, p.y)

        def finish(editor):
            _actual_editor_confirm(editor)
            root.update()
            assert not editor.winfo_exists() and not failures, failures

        def stock_and_ink(key, name):
            out = tmp_path / name
            out.mkdir()
            for role in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
                getattr(host, f"export_{role}_var").set(role == key)
            monkeypatch.setattr(filedialog, "askdirectory", lambda **_: str(out))
            export_selected_dxf(host)
            assert not failures, failures
            path, = out.glob("*.dxf")
            doc = ezdxf.readfile(path)
            assert doc.header["$INSUNITS"] == 4 and not doc.audit().errors
            stock = []
            ink = []
            for entity in doc.modelspace():
                if entity.dxf.layer not in {"CUTTING", "BEND", "MARKING"}:
                    continue
                fields = {k: v for k, v in entity.dxfattribs().items() if k not in {"owner", "handle"}}
                if entity.dxftype() == "LWPOLYLINE":
                    fields["xyseb"] = tuple(map(tuple, entity.get_points("xyseb")))
                (ink if entity.dxf.layer == "MARKING" else stock).append((entity.dxftype(), fields))
            return stock, ink

        open_project(head_input)
        editor, state = open_editor("head")
        p = center(state)
        state.manual_mark_pattern.set("dashed")
        state.manual_mark_dash.set("4")
        state.manual_mark_gap.set("17")
        state.manual_group_arm_x.set("28")
        state.manual_group_arm_y.set("8")
        state.manual_group_tools["l"].invoke()
        click(state, Vec2(p.x + 44, p.y + 15))
        source_group, = [f for f in state.live_context.feature_list if api.is_manual_group(f)]
        finish(editor)
        head = save_project(head_saved)
        source_owner = api.resolve_workspace_physical_root_owner(head, "head")
        assert source_owner
        original_bytes = head_saved.read_bytes()
        from phase6_manufacturing_adapter import build_scene_payload_for_app
        live = current_workspace_marking_source(app)
        live_render = host._query_fold_designer_render_data("head", build_scene_payload_for_app(app, "head"))
        live_receipt = api.open_selected_ordinary_marking_modal_source(
            live, api.selected_normal_marking_inventory("head", live_render), "head",
        )
        actual = api.open_selected_ordinary_marking_modal_source(
            head, api.resolve_saved_endcap_copy_geometry(head, "head"), "head",
        )
        def brief(receipt):
            render = receipt.context.render_data
            return {
                "bounds": render.material.bounds, "area": render.material.area,
                "guides": [repr(row) for row in render.fold_guides],
                "topology": repr(render.unfolded_topology),
                "cut": [
                    repr(row)[:350] for row in render.scene.primitives if row.layer == "CUTTING"
                ][:8],
            }
        assert live_receipt.source_sha256 == api.read_workspace_marking_owner_record(live, source_owner)["source_sha256"]
        if live_receipt.source_sha256 != actual.source_sha256:
            from dataclasses import fields
            from ae_engine.operator_saved_endcap_copy_inputs import _build_saved_endcap_copy_part_spec
            live_spec, _ = host._fold_designer_part_spec_from_payload("head", build_scene_payload_for_app(app, "head"))
            detached_spec = _build_saved_endcap_copy_part_spec(head, "head")
            for field in fields(live_spec):
                first, second = getattr(live_spec, field.name), getattr(detached_spec, field.name)
                if first != second:
                    print("ENDCAP_DIFF", field.name, "LIVE", repr(first))
                    print("ENDCAP_DIFF", field.name, "SAVED", repr(second))
            for key, value in brief(live_receipt).items():
                compare = brief(actual)[key]
                if value != compare:
                    print("RENDER_DIFF", key, "LIVE", repr(value))
                    print("RENDER_DIFF", key, "SAVED", repr(compare))
        assert live_receipt.source_sha256 == actual.source_sha256, "saved EndCap stock differs from native stock"

        if same_project:
            editor, state = open_editor("head")
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(head_saved))
            monkeypatch.setattr(simpledialog, "askstring", lambda *a, **k: "封頭")
            state.manual_mark_copy_button.invoke()
            root.update()
            assert "MANUAL_COPY_SAME_PHYSICAL_OWNER" in state.manual_mark_status.cget("text")
            finish(editor)
        open_project(head_saved if same_project else tail_input)
        editor, state = open_editor("tail")
        p = center(state)
        state.manual_mark_length.set("8")
        editor._manual_marking_controls[0].invoke()
        click(state, p)
        finish(editor)
        tail = save_project(tail_saved)
        target_owner = api.resolve_workspace_physical_root_owner(tail, "tail")
        assert target_owner and target_owner != source_owner
        original_stock, original_ink = stock_and_ink("tail", "original-dxf")

        editor, state = open_editor("tail")
        p = center(state)
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(tail_saved if same_project else head_saved))
        # Source role selected explicitly even when only one physical sheet is marked.
        monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: "封頭")
        state.manual_mark_copy_button.invoke()
        root.update()
        status = state.manual_mark_status.cget("text")
        assert "點選目標轉角" in status, status
        click(state, Vec2(p.x + 44, p.y + 15))
        copies = [f for f in state.live_context.feature_list if api.is_manual_group(f)]
        assert len(copies) == 1, state.manual_mark_status.cget("text")
        copied, = copies
        before = api.group_parameters(source_group)
        after = api.group_parameters(copied)
        assert before["group_id"] != after["group_id"]
        assert before["kind"] == after["kind"] == "l"
        finish(editor)
        live = current_workspace_marking_source(app)
        assert api.resolve_workspace_physical_root_owner(live, "tail") == target_owner
        expected = api.read_workspace_marking_owner_record(live, target_owner)["features"]
        assert copied in expected and source_group not in expected
        final = save_project(tail_final)
        open_project(tail_final)
        assert api.read_workspace_marking_owner_record(final, target_owner)["features"] == expected
        if same_project:
            assert api.read_workspace_marking_owner_record(final, source_owner)["features"] == (source_group,)
        stock, ink = stock_and_ink("tail", "copied-dxf")
        assert stock == original_stock and len(ink) > len(original_ink)
        assert head_saved.read_bytes() == original_bytes
    finally:
        root.destroy()
