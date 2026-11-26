"""Scoped Receiving LEFT circular ink uses the normal physical-sheet sink."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import read_project
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue3414_scoped_marking_proto import _ids, _raw_write, _real_source, _state


def _draft(snapshot, bay):
    return api.open_physical_sheet_marking("base_plate", snapshot=snapshot, selection=(0, bay))


def _centre(draft, dx=0):
    g = next(p for p in draft.context.render_data.scene.primitives
             if isinstance(p, LinePrimitive) and p.layer == "BEND")
    return Vec2((g.p1.x+g.p2.x)/2+dx, (g.p1.y+g.p2.y)/2)


def test_scoped_round_copy_and_dxf_roundtrip(tmp_path, monkeypatch):
    source = _real_source()
    a, b = _ids(source)
    key = api.SCOPED_BASE_PLATE_MARKS
    provider, _ = _provider(source)
    def export(snapshot, name, **kw):
        return api.export_current_receiving_multibay_dxf(
            snapshot, output_dir=tmp_path/name, flags={"base_plate": True},
            physical_bay_geometry_provider=provider, pre_commit_guard=lambda: None, **kw,
        )
    def inspect(files):
        result = {}
        for key, path in files.items():
            doc = ezdxf.readfile(path)
            assert doc.header["$INSUNITS"] == 4 and not doc.audit().errors
            stock = []
            ink = []
            for row in doc.modelspace():
                layer = row.dxf.layer
                if layer == "MARKING":
                    assert row.dxftype() == "CIRCLE"
                    ink.append((row.dxf.center.x, row.dxf.center.y, row.dxf.radius))
                elif layer in {"CUTTING","BEND"}:
                    data = {k:v for k,v in row.dxfattribs().items() if k not in {"handle","owner"}}
                    if row.dxftype() == "LWPOLYLINE":
                        data["points"] = tuple(map(tuple,row.get_points("xyseb")))
                    stock.append((row.dxftype(), data))
            result[key] = stock, ink
        return result
    old = inspect(export(source, "stock"))
    opening = _draft(source,0)
    p = _centre(opening)
    hole = next(row for row in opening.context.render_data.scene.primitives
                if isinstance(row,CirclePrimitive) and row.layer=="CUTTING")
    with pytest.raises(ValueError, match="ROUND_MARKING_CIRCUMFERENCE_OUTSIDE_RETAINED_MATERIAL"):
        api.create_physical_sheet_mark(opening, (), tool="circle",
                                      centre=Vec2(hole.center.x + hole.radius, hole.center.y), diameter=4)
    mark = api.create_physical_sheet_mark(opening, (), tool="circle", centre=p, diameter=8)
    source[key] = api.commit_physical_sheet_marking(opening, opening, (mark,)).scoped_store
    saved_path = _raw_write(tmp_path/"round.p6fold",source)
    saved = read_project(saved_path)["snapshot"]
    assert saved[key][a]["features"] == [mark] and b not in saved[key]
    assert _draft(saved,0).saved_marks == (mark,) and _draft(saved,1).saved_marks == ()
    files = export(saved,"marked")
    marked = inspect(files)
    assert [new[0] for new in marked.values()] == [row[0] for row in old.values()]
    assert sorted(row[1] for row in marked.values()) == [[],[(p.x,p.y,4.)]]
    q = _centre(_draft(saved,1),35)
    props = dict(project_path=saved_path,project_sha256=sha256(saved_path.read_bytes()).hexdigest(),
                 saved_snapshot=saved)
    (choice,) = api.list_saved_scoped_marking_copy_candidates(**props,target_owner_id=b)
    assert choice[0] == a and choice[3].startswith("circle:") and choice[4:] == (p.x,p.y,8.)
    tgt = _draft(saved,1)
    changed = deepcopy(saved)
    changed[key][a]["features"][0] = replace(mark, offset=Vec2(p.x + 0.001, p.y))
    with pytest.raises(ValueError, match="SCOPED_COPY_LIVE_SOURCE_CHANGED"):
        api.verify_saved_scoped_marking_copy(
            **props, live_snapshot=changed, source_owner_id=a, source_group_id=choice[3],
            opened_target=tgt,
        )
    copied = api.place_saved_scoped_marking_copy(**props,live_snapshot=saved,source_owner_id=a,
        source_group_id=choice[3],opened_target=tgt,target_features=(),target_position=q)
    assert api.is_manual_round_mark(copied) and copied.offset==q and copied.diameter==8
    newer = deepcopy(saved)
    newer[key] = api.commit_physical_sheet_marking(tgt,tgt,(copied,)).scoped_store
    assert newer[key][a] == saved[key][a] and newer[key][b]["features"]==[copied]
    reviewed = read_project(_raw_write(tmp_path/"copied.p6fold",newer))["snapshot"]
    both=export(reviewed,"both")
    assert sorted(row[1] for row in inspect(both).values()) == sorted([[(p.x,p.y,4.)],[(q.x,q.y,4.)]])
    prior = {Path(path): Path(path).read_bytes() for path in both.values()}
    from ae_engine import dxf_serialization
    writer = dxf_serialization.save_scene_dxf

    def distort_saved_circle(path, scene):
        result = writer(path, scene)
        reopened = ezdxf.readfile(path)
        circle, = reopened.modelspace().query('CIRCLE[layer=="MARKING"]')
        circle.dxf.radius += 0.5
        reopened.saveas(path)
        return result

    with monkeypatch.context() as broken_writer:
        broken_writer.setattr(dxf_serialization, "save_scene_dxf", distort_saved_circle)
        with pytest.raises(ValueError, match="SCOPED_MARK_DXF_ROUND_CHANGED"):
            export(reviewed, "both", overwrite=True)
    assert {p: p.read_bytes() for p in (tmp_path / "both").rglob("*") if p.is_file()} == prior

    reviewed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config_submitted"] = False
    with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_NOT_SOURCE_VERIFIED"):
        export(reviewed,"both",overwrite=True)
    assert all(path.read_bytes()==data for path,data in prior.items())


def test_native_scoped_circle_tool_saves_only_current_bay(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    from gui import Phase6PrimaryApplication
    from gui_modules.application.physical_part_hole_editor import open_scoped_receiving_base_plate_editor
    from tests.test_issue3413_primary_group_real_tk import _actual_editor_confirm

    source = _real_source()
    a,b = _ids(source)
    input_path = _raw_write(tmp_path/"source.p6fold",source)
    output = tmp_path/"saved.p6fold"
    root=tk.Tk()
    try:
        root.geometry("1400x900+0+0")
        host = Phase6PrimaryApplication(root)
        menu = host.fold_designer_app.project_file_menu
        errors=[]
        monkeypatch.setattr(messagebox,"showerror",lambda title,msg,**kw: errors.append(msg))
        monkeypatch.setattr(filedialog,"askopenfilename",lambda **kw: str(input_path))
        menu.invoke(0)
        root.update()
        editor=open_scoped_receiving_base_plate_editor(host,0,0,expected_owner=a)
        root.update()
        state=_state(editor)
        assert hasattr(editor, "_manual_round_marking_controls")
        button,diameter=editor._manual_round_marking_controls
        diameter.set("10")
        button.invoke()
        p=_centre(state.manual_marking_draft)
        x,y=state.canvas_view.transform.world_to_canvas(p)
        state.canvas.event_generate("<ButtonPress-1>",x=round(x),y=round(y))
        state.canvas.event_generate("<ButtonRelease-1>",x=round(x),y=round(y))
        root.update()
        (mark,)=state.live_context.feature_list
        assert api.is_manual_round_mark(mark) and mark.diameter==10
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists() and not errors
        monkeypatch.setattr(filedialog,"asksaveasfilename",lambda **kw:str(output))
        menu.invoke(2)
        root.update()
        saved=read_project(output)["snapshot"]
        assert _draft(saved,0).saved_marks==(mark,) and _draft(saved,1).saved_marks==()
        original_output = output.read_bytes()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(output))
        menu.invoke(0)
        root.update()
        assert Path(host.project_controller.project_path) == output
        editor = open_scoped_receiving_base_plate_editor(host, 0, 1, expected_owner=b)
        root.update()
        state = _state(editor)
        def select_round(title, prompt, **options):
            assert "第1連" in prompt and "圓形 Ø10.00" in prompt
            return 1
        monkeypatch.setattr(simpledialog, "askinteger", select_round)
        state.manual_mark_copy_button.invoke()
        root.update()
        assert "點選目標圓心" in state.manual_mark_status.cget("text")
        q = _centre(state.manual_marking_draft, 35)
        x, y = state.canvas_view.transform.world_to_canvas(q)
        state.canvas.event_generate("<ButtonPress-1>", x=round(x), y=round(y))
        state.canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
        root.update()
        (copied,) = state.live_context.feature_list
        assert api.is_manual_round_mark(copied) and copied.diameter == mark.diameter
        assert copied.offset != mark.offset
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists() and not errors
        copied_path = tmp_path / "copied.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(copied_path))
        menu.invoke(2)
        root.update()
        replay = read_project(copied_path)["snapshot"]
        from ae_engine.manufacturing_contracts import freeze_manufacturing_value
        assert freeze_manufacturing_value(_draft(replay, 0).saved_marks) == freeze_manufacturing_value((mark,))
        assert _draft(replay, 1).saved_marks == (copied,)
        assert output.read_bytes() == original_output
    finally:
        root.destroy()
