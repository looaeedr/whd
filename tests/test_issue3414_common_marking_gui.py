"""One live Tk placement modal, with existing scoped owner authorization."""
import tkinter as tk

import pytest
from ae_engine import manufacturing_api as api
from ae_engine.operator_scoped_base_plate_marks import normalize_scoped_base_plate_marks
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue3414_scoped_marking_proto import _ids, _raw_write, _real_source
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm


def test_two_real_scoped_selection_receipts_share_existing_tk_actions(tmp_path):
    from gui import Phase6PrimaryApplication
    from gui_modules.application.physical_part_hole_editor import (
        open_scoped_receiving_base_plate_editor,
    )

    source = _real_source()
    original_ids = _ids(source)
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        host.load_phase6_project(_raw_write(tmp_path / "real.p6fold", source), open_designer=True)
        root.update()
        app = host.fold_designer_app
        live = app._phase6_input_snapshot
        assert _ids(live) == original_ids

        def edit(bay):
            editor = open_scoped_receiving_base_plate_editor(
                host, 0, bay, expected_owner=original_ids[bay],
            )
            root.update()
            cb = editor._manual_marking_place
            state = dict(zip(cb.__code__.co_freevars, (c.cell_contents for c in cb.__closure__)))["s"]
            receipt = state.manual_marking_draft
            assert receipt.owner_id == original_ids[bay]
            assert receipt.allowed_tools == ("line",)
            assert not hasattr(editor, "_manual_round_marking_controls")
            assert not state.manual_group_tools
            return editor, state

        with pytest.raises(ValueError, match="OWNER_STALE"):
            open_scoped_receiving_base_plate_editor(host, 0, 1, expected_owner=original_ids[0])
        for bay in (0, 1):
            editor, state = edit(bay)
            bend = next(p for p in state.manual_marking_draft.context.render_data.scene.primitives
                        if isinstance(p, LinePrimitive) and p.layer == "BEND")
            point = Vec2((bend.p1.x+bend.p2.x)/2 + 18*(bay + 1), (bend.p1.y+bend.p2.y)/2)
            x, y = state.canvas_view.transform.world_to_canvas(point)
            before = normalize_scoped_base_plate_marks(live)
            state.manual_mark_length.set("12")
            state.manual_mark_angle.set("37")
            editor._manual_marking_controls[0].invoke()
            host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            root.update()
            assert len(state.live_context.feature_list) == 1
            mark, = state.live_context.feature_list
            assert api.is_manual_mark(mark)
            assert normalize_scoped_base_plate_marks(live) == before
            _actual_editor_confirm(editor)
            root.update()
            assert not editor.winfo_exists()
            after = normalize_scoped_base_plate_marks(live)
            assert after[original_ids[bay]]["features"] == [mark]
            assert all(after[key] == value for key, value in before.items())

        editor, state = edit(0)
        assert tuple(state.live_context.feature_list) == tuple(
            normalize_scoped_base_plate_marks(live)[original_ids[0]]["features"]
        )
        state.cancel_all_btn.invoke()
        root.update()
        assert not editor.winfo_exists()
        assert set(normalize_scoped_base_plate_marks(live)) == set(original_ids)
    finally:
        root.destroy()


def test_same_geometry_other_project_rejects_stale_scoped_modal(tmp_path, monkeypatch):
    from gui import Phase6PrimaryApplication
    from gui_modules.application.physical_part_hole_editor import (
        open_scoped_receiving_base_plate_editor,
    )
    from gui_modules.editors.hole_editor import messagebox

    source = _real_source()
    path_a = _raw_write(tmp_path / "origin.p6fold", source)
    path_b = _raw_write(tmp_path / "other.p6fold", source)
    root = tk.Tk()
    try:
        host = Phase6PrimaryApplication(root)
        host.load_phase6_project(path_a, open_designer=True)
        root.update()
        app = host.fold_designer_app
        epoch = host.project_controller.project_load_epoch
        opened = open_scoped_receiving_base_plate_editor(host, 0, 0, expected_owner=_ids(source)[0])
        root.update()
        host.load_phase6_project(path_b, open_designer=True)
        root.update()
        assert host.project_controller.project_load_epoch != epoch
        current = host.fold_designer_app._phase6_input_snapshot
        assert _ids(current) == _ids(source)  # same geometry AND same mirrored stored owner
        baseline = normalize_scoped_base_plate_marks(current)
        if opened.winfo_exists():
            errors = []
            monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: errors.append(text))
            _actual_editor_confirm(opened)
            root.update()
            assert errors == ["PHYSICAL_MARK_PROJECT_SESSION_STALE"]
        # An already destroyed old modal is also unable to publish.
        assert normalize_scoped_base_plate_marks(current) == baseline
    finally:
        root.destroy()
