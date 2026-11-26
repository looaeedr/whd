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


@pytest.mark.parametrize(("same_project", "shape"), [
    pytest.param(False, "group", id="other-project"),
    pytest.param(True, "group", id="same-project"),
    pytest.param(False, "line", id="standalone-line"),
    pytest.param(False, "line_discard_delete", id="standalone-discard-delete"),
    pytest.param(False, "line_discard_undo", id="standalone-discard-undo"),
    pytest.param(False, "line_keep", id="standalone-retained-source-changed"),
    pytest.param(False, "line_keep_undo", id="standalone-delete-undo-source-changed"),
    pytest.param(False, "line_keep_moved", id="standalone-moved-source-changed"),
    pytest.param(False, "line_choice", id="two-source-lines"),
    pytest.param(True, "circle", id="standalone-circle"),
])
def test_existing_editor_copies_saved_head_group_into_distinct_tail(tmp_path, monkeypatch, same_project, shape):
    multiple = shape == "line_choice"
    copy_lifecycle = shape.removeprefix("line_") if shape.startswith(("line_discard_", "line_keep")) else ""
    if multiple or copy_lifecycle:
        shape = "line"
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
        predicate = {"group": api.is_manual_group, "line": api.is_manual_straight_mark,
                     "circle": api.is_manual_round_mark}[shape]
        if shape == "line":
            state.manual_mark_length.set("28")
            editor._manual_marking_controls[0].invoke()
        elif shape == "circle":
            button, diameter = editor._manual_round_marking_controls
            diameter.set("8")
            button.invoke()
        else:
            state.manual_group_tools["l"].invoke()
        click(state, Vec2(p.x + 44, p.y + 15))
        if multiple:
            state.manual_mark_length.set("12")
            editor._manual_marking_controls[0].invoke()
            click(state, Vec2(p.x - 34, p.y + 15))
            not_chosen, source_group = [f for f in state.live_context.feature_list if predicate(f)]
        else:
            source_group, = [f for f in state.live_context.feature_list if predicate(f)]
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
        original_marks = api.read_workspace_marking_owner_record(tail, target_owner)["features"]
        original_stock, original_ink = stock_and_ink("tail", "original-dxf")

        editor, state = open_editor("tail")
        p = center(state)
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(tail_saved if same_project else head_saved))
        # Source role selected explicitly even when only one physical sheet is marked.
        monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: "封頭")
        if multiple:
            shown = []
            def cancel_picker(title, body, **kwargs):
                assert kwargs["minvalue"] == 1 and kwargs["maxvalue"] == 2
                shown.append(body)
                return None
            with monkeypatch.context() as cancelled:
                cancelled.setattr(simpledialog, "askinteger", cancel_picker)
                state.manual_mark_copy_button.invoke()
                root.update()
            assert len(shown) == 1
            assert "28.00 mm" in shown[0] and "12.00 mm" in shown[0]
            assert shown[0].count("X=") == 2 and "line:" not in shown[0]
            assert tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f)) == original_marks
            monkeypatch.setattr(simpledialog, "askinteger", lambda *args, **kwargs: 2)
        state.manual_mark_copy_button.invoke()
        root.update()
        status = state.manual_mark_status.cget("text")
        assert ("點選目標轉角" if shape == "group" else "點選目標中點" if shape == "line" else "點選目標圓心") in status, status
        click(state, Vec2(p.x + 44, p.y + 15))
        copies = [f for f in state.live_context.feature_list if predicate(f) and f not in original_marks]
        assert len(copies) == 1, state.manual_mark_status.cget("text")
        copied, = copies
        assert copied is not source_group
        if shape == "group":
            before = api.group_parameters(source_group)
            after = api.group_parameters(copied)
            assert before["group_id"] != after["group_id"]
            assert before["kind"] == after["kind"] == "l"
        elif shape == "line":
            assert copied.source_params == source_group.source_params
            assert len(copied.layered_profiles) == len(source_group.layered_profiles)
            if multiple:
                from math import hypot
                def length(mark):
                    a, b = mark.points
                    return hypot(b.x-a.x, b.y-a.y)
                assert length(copied) == pytest.approx(length(source_group))
                assert length(copied) != pytest.approx(length(not_chosen))
        else:
            assert copied.diameter == source_group.diameter
        if copy_lifecycle:
            if copy_lifecycle in {"discard_delete", "keep_undo"}:
                index = next(i for i, f in enumerate(state.live_context.feature_list) if f is copied)
                from phase6_hole_editor_session import HoleEditorAction
                state.hole_session.execute(HoleEditorAction.select(index))
                state.delete_btn.invoke()
                root.update()
                assert all(f is not copied for f in state.live_context.feature_list)
            if copy_lifecycle in {"discard_undo", "keep_undo"}:
                state.undo_btn.invoke()
                root.update()
            keep = copy_lifecycle.startswith("keep")
            assert any(f is copied for f in state.live_context.feature_list) == keep
            if copy_lifecycle == "keep_moved":
                p1, p2 = copied.points
                midpoint = Vec2((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
                canvas = host.last_hole_editor_canvas
                for event, delta, timestamp in (("<ButtonPress-1>", 0, 1500),
                                                ("<B1-Motion>", 14, 1530),
                                                ("<ButtonRelease-1>", 14, 1580)):
                    x, y = state.canvas_view.transform.world_to_canvas(Vec2(midpoint.x + delta, midpoint.y))
                    canvas.event_generate(event, x=round(x), y=round(y), time=timestamp)
                    root.update()
                edited, = [f for f in state.live_context.feature_list if predicate(f) and f not in original_marks]
                assert edited is not copied and edited.points != copied.points
            head_saved.write_bytes(original_bytes + b"\n")
            assert read_project(head_saved)["snapshot"] == head
            target_file_before = tail_saved.read_bytes()
            if keep:
                _actual_editor_confirm(editor)
                root.update()
                assert editor.winfo_exists()
                assert any("MANUAL_COPY_SOURCE_SAVED_SOURCE_CHANGED" in text for _, text in failures)
                assert tail_saved.read_bytes() == target_file_before
                return
            state.manual_mark_length.set("11")
            editor._manual_marking_controls[0].invoke()
            click(state, Vec2(p.x - 44, p.y + 15))
            surviving = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
            assert surviving[:len(original_marks)] == original_marks
            assert len(surviving) == len(original_marks) + 1
            assert all(f is not copied for f in surviving)
            finish(editor)
            assert tail_saved.read_bytes() == target_file_before
            final = save_project(tail_final)
            open_project(tail_final)
            assert api.read_workspace_marking_owner_record(final, target_owner)["features"] == surviving
            stock, ink = stock_and_ink("tail", "discarded-copy-dxf")
            assert stock == original_stock and len(ink) == len(original_ink) + 1
            return
        finish(editor)
        live = current_workspace_marking_source(app)
        assert api.resolve_workspace_physical_root_owner(live, "tail") == target_owner
        expected = api.read_workspace_marking_owner_record(live, target_owner)["features"]
        assert copied in expected
        if shape == "group":
            assert source_group not in expected
        final = save_project(tail_final)
        open_project(tail_final)
        assert api.read_workspace_marking_owner_record(final, target_owner)["features"] == expected
        if same_project:
            assert api.read_workspace_marking_owner_record(final, source_owner)["features"] == (source_group,)
        stock, ink = stock_and_ink("tail", "copied-dxf")
        assert stock == original_stock and len(ink) > len(original_ink)
        if multiple:
            from math import hypot
            emitted = [row for row in ink if row not in original_ink]
            assert all(kind == "LWPOLYLINE" for kind, _ in emitted)
            total = sum(hypot(b[0]-a[0], b[1]-a[1]) for _, row in emitted
                        for a, b in zip(row["xyseb"], row["xyseb"][1:]))
            expected_length = sum(hypot(b.x-a.x, b.y-a.y) for _, points, _ in copied.layered_profiles
                                  for a, b in zip(points, points[1:]))
            assert total == pytest.approx(expected_length)
        assert head_saved.read_bytes() == original_bytes
    finally:
        root.destroy()


@pytest.mark.parametrize("donor,target,label", [
    ("door", "base_plate", "\u9580\u677f"),
    ("base_plate", "door", "\u5e95\u677f"),
])
@pytest.mark.parametrize("target_previously_marked", [True, False])
def test_existing_vault_editor_copies_saved_mark_between_door_and_base(tmp_path, monkeypatch, donor, target, label, target_previously_marked):
    from tests.test_issue2517_direct_door_partspec_original_source_engine_gate import _row
    from phase6_manufacturing_adapter import build_scene_payload_for_app

    source = _row()
    source["multi_door_enabled"] = False
    source["existing_parts"] = ["box_body", "door", "base_plate"]
    initial = _raw_write(tmp_path / "vault.p6fold", source)
    saved = tmp_path / "saved.p6fold"
    copied = tmp_path / "copied.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu
        failures = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **_: failures.append((title, text)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)

        def open_saved(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            menu.invoke(0)
            root.update()

        def editor(key):
            app.activate_part(key)
            root.update()
            modal = host.open_part_hole_editor(key)
            root.update()
            callback = modal._manual_marking_place
            state = dict(zip(callback.__code__.co_freevars, (c.cell_contents for c in callback.__closure__)))["s"]
            return modal, state

        def click(state, offset):
            point = state.manual_marking_draft.context.render_data.material.representative_point()
            x, y = state.canvas_view.transform.world_to_canvas(Vec2(point.x + offset, point.y))
            host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            root.update()

        def confirm(modal):
            _actual_editor_confirm(modal)
            root.update()
            assert not modal.winfo_exists() and not failures, failures

        open_saved(initial)
        for part, length in ((donor, "12"), (target, "6")):
            if part == target and not target_previously_marked:
                continue
            modal, state = editor(part)
            state.manual_mark_length.set(length)
            modal._manual_marking_controls[0].invoke()
            click(state, 0)
            confirm(modal)
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        menu.invoke(2)
        root.update()
        snapshot = read_project(saved)["snapshot"]
        old = {}
        for key in (donor, target):
            live = current_workspace_marking_source(app)
            geometry = api.selected_normal_marking_inventory(
                key, host._query_fold_designer_render_data(key, build_scene_payload_for_app(app, key)),
            )
            receipt = api.open_selected_ordinary_marking_modal_source(live, geometry, key)
            replay = api.open_selected_ordinary_marking_modal_source(
                snapshot, api.resolve_saved_ordinary_copy_geometry(snapshot, key), key,
            )
            assert replay.source_sha256 == receipt.source_sha256, key
            record = (None if receipt.owner_id is None else
                      api.read_workspace_marking_owner_record(snapshot, receipt.owner_id))
            old[key] = () if record is None else record["features"]
        modal, state = editor(target)
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: label)
        state.manual_mark_copy_button.invoke()
        root.update()
        click(state, 35)
        marks = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        assert len(marks) == len(old[target]) + 1 and marks[:-1] == old[target], state.manual_mark_status.cget("text")
        copied_mark = marks[-1]
        assert copied_mark != old[donor][0]
        confirm(modal)
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(copied))
        menu.invoke(2)
        root.update()
        open_saved(copied)
        final = read_project(copied)["snapshot"]
        for key in (donor, target):
            owner = api.resolve_workspace_physical_root_owner(final, key)
            wanted = old[key] if key == donor else (*old[key], copied_mark)
            assert api.read_workspace_marking_owner_record(final, owner)["features"] == wanted
            for role in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
                getattr(host, f"export_{role}_var").set(role == key)
            out = tmp_path / f"verified-{key}"
            out.mkdir()
            monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
            export_selected_dxf(host)
            assert not failures, failures
            file, = out.glob("*.dxf")
            drawing = ezdxf.readfile(file)
            assert drawing.header["$INSUNITS"] == 4 and not drawing.audit().errors
            ink = drawing.modelspace().query('LWPOLYLINE[layer=="MARKING"]')
            assert {tuple(map(tuple, row.get_points("xy"))) for row in ink} == {
                tuple((point.x, point.y) for point in feature.points) for feature in wanted
            }
    finally:
        root.destroy()
@pytest.mark.parametrize("target_previously_marked", [True, False])
def test_vault_version_copy_gui(tmp_path, monkeypatch, target_previously_marked):
    from tests.test_issue2517_direct_door_partspec_original_source_engine_gate import _row
    from hashlib import sha256
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    donor, target, label = 'door', 'base_plate', '\u9580\u677f'

    source = _row()
    source["multi_door_enabled"] = False
    source["existing_parts"] = ["box_body", "door", "base_plate"]
    initial = _raw_write(tmp_path / "vault.p6fold", source)
    saved = tmp_path / "saved.p6fold"
    copied = tmp_path / "copied.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu
        failures = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **_: failures.append((title, text)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)

        def open_saved(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            menu.invoke(0)
            root.update()

        def editor(key):
            app.activate_part(key)
            root.update()
            modal = host.open_part_hole_editor(key)
            root.update()
            callback = modal._manual_marking_place
            state = dict(zip(callback.__code__.co_freevars, (c.cell_contents for c in callback.__closure__)))["s"]
            return modal, state

        def click(state, offset):
            point = state.manual_marking_draft.context.render_data.material.representative_point()
            x, y = state.canvas_view.transform.world_to_canvas(Vec2(point.x + offset, point.y))
            host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            root.update()

        def confirm(modal):
            _actual_editor_confirm(modal)
            root.update()
            assert not modal.winfo_exists() and not failures, failures

        open_saved(initial)
        app.activate_part(donor)
        root.update()
        controls = app.receiving_mode_controls.quantity_editor
        controls.count_var.set("2")
        controls.commit_count()
        root.update()
        model = app.designer_workspace.quantity_model
        first_version = model.selected_version_id
        assert model.selected_piece_count == 2
        controls.ports["add"]()
        root.update()
        second_version = model.selected_version_id
        assert first_version != second_version
        controls.count_var.set("3")
        controls.commit_count()
        root.update()
        assert app.designer_workspace.quantity_model.selected_piece_count == 3
        def mark(key, length, offset=0):
            modal, state = editor(key)
            state.manual_mark_length.set(length)
            state.manual_mark_angle.set("0")
            modal._manual_marking_controls[0].invoke()
            click(state, offset)
            confirm(modal)

        mark(donor, "29")
        if target_previously_marked:
            mark(target, "6")
        app.designer_workspace.quantity_model.select(first_version)
        root.update()
        mark(donor, "12")
        if target_previously_marked:
            mark(target, "8")
        app.designer_workspace.quantity_model.select(second_version)
        root.update()
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        menu.invoke(2)
        root.update()
        snapshot = read_project(saved)["snapshot"]
        assert api.list_ordinary_marking_copy_versions(snapshot, donor) == ((first_version, 2), (second_version, 3))
        digest = sha256(saved.read_bytes()).hexdigest()
        args = dict(source_snapshot=snapshot, source_project_path=saved, source_project_sha256=digest,
                    source_part_key=donor, resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry)
        with pytest.raises(ValueError, match="EXPLICIT_QUANTITY_VERSION"):
            api.list_saved_endcap_marking_copy_candidates(args)
        first, = api.list_saved_endcap_marking_copy_candidates(dict(args, source_version_id=first_version))
        second, = api.list_saved_endcap_marking_copy_candidates(dict(args, source_version_id=second_version))
        assert first[4] == pytest.approx(12) and second[4] == pytest.approx(29)
        live = current_workspace_marking_source(app)
        geometry = api.selected_normal_marking_inventory(
            target, host._query_fold_designer_render_data(target, build_scene_payload_for_app(app, target)),
        )
        target_args = dict(target_snapshot=snapshot, target_project_path=saved, target_project_sha256=digest,
                           target_part_key=target, target_version_id=first_version,
                           target_live_snapshot=live, target_live_geometry=geometry,
                           resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry)
        with pytest.raises(ValueError, match="TARGET_EDITOR_SESSION_STALE"):
            api.verify_saved_endcap_marking_copy(
                source_group_id=first[0], source=dict(args, source_version_id=first_version), target=target_args,
            )
        modal, state = editor(target)
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: label)
        monkeypatch.setattr(simpledialog, "askinteger", lambda *args, **kwargs: 1)
        state.manual_mark_copy_button.invoke()
        root.update()
        click(state, 35)
        marks = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        assert len(marks) == (2 if target_previously_marked else 1), state.manual_mark_status.cget("text")
        assert abs(marks[-1].points[1].x - marks[-1].points[0].x) == pytest.approx(12)
        confirm(modal)
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(copied))
        menu.invoke(2)
        root.update()
        open_saved(copied)
        final = read_project(copied)["snapshot"]
        for key in (donor, target):
            for version in (first_version, second_version):
                before = (api.read_quantity_physical_marking(snapshot, key, version_id=version) or {}).get("features", ())
                after = (api.read_quantity_physical_marking(final, key, version_id=version) or {}).get("features", ())
                assert after == marks if (key, version) == (target, second_version) else after == before
        for key in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{key}_var").set(key == target)
        out = tmp_path / "version-copy-dxf"
        out.mkdir()
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
        export_selected_dxf(host)
        assert not failures, failures
        counts = {}
        for file in out.glob("*.dxf"):
            drawing = ezdxf.readfile(file)
            assert drawing.header["$INSUNITS"] == 4 and not drawing.audit().errors
            qty, = (e.plain_text() for e in drawing.modelspace().query('MTEXT[layer=="CHECK"]')
                    if e.plain_text().startswith("Q"))
            counts[qty] = len(drawing.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
        assert counts == ({"Q2": 1, "Q3": 2} if target_previously_marked else {"Q2": 0, "Q3": 1})
    finally:
        root.destroy()
