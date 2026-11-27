"""Native drawing-canvas acceptance for Receiving three-piece box marking."""
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3414_box_body_piece_marking_occupancy import KEYS, actual
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm
from tests.test_issue3414_box_body_piece_marking_export import _raw


def test_three_piece_drawing_double_click_save_reopen_and_dxf(tmp_path, monkeypatch):
    import fold_designer_bridge as bridge
    from gui import Phase6PrimaryApplication
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source

    structure, _ = actual()
    original = Path(__file__).parent / 'fixtures/issue1503_legacy_receiving_without_nfb_base.p6fold'
    snapshot = read_project(original)['snapshot']
    snapshot.update(w=800., h=1600., d=350., t=2., fw=29., zl1=-24., zl2=24., zr2=18.,
                    box_body_structure=structure)
    source = write_project(tmp_path/'source.p6fold', {'schema':PROJECT_SCHEMA, 'snapshot':snapshot})
    root = tk.Tk()
    root.geometry('1400x900+0+0')
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu

        def load(path):
            monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(path))
            menu.invoke(0)
            root.update()
            assert str(host.project_controller.project_path) == str(path)

        def geometry():
            return app._phase6_resolve_manufacturing_geometry()

        def current():
            resolved = geometry()
            return current_workspace_marking_source(app), resolved

        def export(folder):
            s, g = current()
            return api.save_selected_resolved_manufacturing_dxf(
                s,g,{'box_body':True},tmp_path/folder,read_current_owner_source=current)

        def edit(key, clock):
            bridge._phase6_show_corner_data(app)
            bridge._phase6_select_corner_data_part(app,key)
            root.update()
            canvas = app.corner_data_canvas
            for tick in (clock,clock+50):
                canvas.event_generate('<ButtonPress-1>',x=80,y=100,time=tick)
                canvas.event_generate('<ButtonRelease-1>',x=80,y=100,time=tick)
            root.update()
            window = host.last_unified_hole_editor
            assert window.winfo_exists()
            place = window._manual_marking_place
            state = dict(zip(place.__code__.co_freevars, (c.cell_contents for c in place.__closure__)))['s']
            assert state.manual_marking_draft.context.part_key == key
            assert window._manual_round_marking_controls[0].winfo_exists()
            return window,state,canvas

        load(source)
        plain = export('plain')
        left, rear, right = KEYS
        canvas = None
        for key, clock in ((left,1000),(rear,1600)):
            window,state,canvas=edit(key,clock)
            centre=state.manual_marking_draft.context.render_data.material.representative_point()
            state.manual_mark_length.set('25')
            state.manual_mark_angle.set('0')
            window._manual_marking_controls[0].invoke()
            x,y=state.canvas_view.transform.world_to_canvas(Vec2(centre.x,centre.y))
            host.last_hole_editor_canvas.event_generate('<Button-1>',x=round(x),y=round(y))
            root.update()
            assert sum(api.is_manual_mark(f) for f in state.live_context.feature_list)==1
            _actual_editor_confirm(window)
            root.update()
            assert not window.winfo_exists()
        window,state,other_canvas=edit(right,2200)
        assert other_canvas is canvas
        assert not tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        _actual_editor_confirm(window)
        root.update()
        saved=tmp_path/'reopen.p6fold'
        monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(saved))
        menu.invoke(2)
        root.update()
        assert saved.is_file()
        load(saved)
        written=export('written')
        assert len(plain)==len(written)==3
        s,g=current()
        for key,expected in ((left,1),(rear,1),(right,0)):
            draft,_=api.open_box_body_piece_marking_modal_source(s,g,key)
            assert len(draft.saved_marks)==expected
            p,q=plain[draft.physical_key],written[draft.physical_key]
            original_marks=_raw(p,{'MARKING'})
            assert _raw(q,{'MARKING'})[:len(original_marks)]==original_marks
            assert len(_raw(q,{'MARKING'}))==len(original_marks)+expected
            assert _raw(q,{'CUTTING','BEND','BLIND_HOLE'})==_raw(p,{'CUTTING','BEND','BLIND_HOLE'})
            if key==right:
                assert [e[0] for e in original_marks]==['CIRCLE','CIRCLE']
                assert [e[0] for e in _raw(q,{'BLIND_HOLE'})]==['CIRCLE']
    finally:
        root.destroy()
