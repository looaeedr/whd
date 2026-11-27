from hashlib import sha256

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_selected_export import save_selected_resolved_manufacturing_dxf
from ae_engine.physical_sheet_editor_context import resolve_box_body_piece_manufacturing_witness
from tests.test_issue3414_box_body_piece_marking_confirm import KEYS, case, marks, opened, reload_project


def _raw(path, layers):
    view = ezdxf.readfile(path).modelspace()
    # Compare actual emitted entities while ignoring per-document handle IDs.
    return [(e.dxftype(), {k:v for k,v in e.dxf.all_existing_dxf_attribs().items()
                           if k not in {"handle", "owner"}}, tuple(e.get_points()) if e.dxftype()=="LWPOLYLINE" else ())
            for e in view if e.dxf.layer in layers]


def test_selected_ordinary_export_uses_exact_saved_piece_and_preserves_stock(tmp_path):
    ws,read = case()
    s,g = read()
    flags = {"box_body":True}
    plain = save_selected_resolved_manufacturing_dxf(s,g,flags,tmp_path/"plain")
    for key in KEYS[:2]:
        assert ws.commit_box_body_piece_marking(opened(*read(),key),marks(g,key),read_current=read)
    source = reload_project(tmp_path/"saved.p6fold", read()[0])
    # Reopen the project before producing the actual DXF files.
    directory = tmp_path/"marked"
    def current():
        return source,g
    written = save_selected_resolved_manufacturing_dxf(source,g,flags,directory,read_current_owner_source=current)
    assert len(written) == 3 and set(plain) == set(written)
    for i, k in enumerate(KEYS):
        physical, stock = resolve_box_body_piece_manufacturing_witness(g,k)
        p, w = plain[physical],written[physical]
        assert _raw(p,{"CUTTING","BEND","BLIND_HOLE"}) == _raw(w,{"CUTTING","BEND","BLIND_HOLE"})
        original, marked = _raw(p,{"MARKING"}),_raw(w,{"MARKING"})
        if i < 2:
            assert marked[:len(original)] == original
            line, circle = marked[len(original):]
            centre = stock.material.representative_point()
            assert line[0] == "LWPOLYLINE"
            assert len(line[2]) == 2
            assert tuple(tuple(row[:2]) for row in line[2]) == (
                (centre.x-10.5, centre.y), (centre.x-5.5, centre.y),
            )
            assert circle[0] == "CIRCLE"
            assert tuple(circle[1]["center"]) == (centre.x+8, centre.y, 0.)
            assert circle[1]["radius"] == 2.5
        else:
            # This right side has native source ink, not an empty MARKING layer.
            # Reopen left then right from the same saved snapshot to distinguish
            # baseline circles from editable user ink independently of the GUI.
            assert len(opened(source,g,KEYS[0]).saved_marks) == 2
            right_draft = opened(source,g,k)
            assert right_draft.owner_id is None
            assert not right_draft.saved_marks
            assert [entity[0] for entity in original] == ["CIRCLE", "CIRCLE"]
            assert [entity[0] for entity in _raw(w,{"BLIND_HOLE"})] == ["CIRCLE"]
            assert marked == original

    expected = {file.name:sha256(file.read_bytes()).digest() for file in directory.glob("*.dxf")}
    ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"integral",800))
    ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"three_piece_side_back_split",800))
    with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
        save_selected_resolved_manufacturing_dxf(source,g,flags,directory,read_current_owner_source=read)
    assert {file.name:sha256(file.read_bytes()).digest() for file in directory.glob("*.dxf")} == expected


def test_replaced_owner_after_staging_does_not_replace_existing_dxfs(tmp_path):
    ws, read = case()
    _,g = read()
    assert ws.commit_box_body_piece_marking(opened(*read(),KEYS[1]),marks(g,KEYS[1]),read_current=read)
    marked = read()[0]
    folder = tmp_path / "output"
    save_selected_resolved_manufacturing_dxf(marked,g,{"box_body":True},folder,read_current_owner_source=read)
    original = {f.name:sha256(f.read_bytes()).digest() for f in folder.glob("*.dxf")}
    modified = False
    def switches_after_stage():
        nonlocal modified
        if not modified and any(folder.glob(".whd-dxf-stage-*/*.dxf")):
            ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"integral",800))
            modified = True
        return read()
    with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
        save_selected_resolved_manufacturing_dxf(marked,g,{"box_body":True},folder,read_current_owner_source=switches_after_stage)
    assert modified
    assert not tuple(folder.glob(".whd-dxf-stage-*"))
    assert {f.name:sha256(f.read_bytes()).digest() for f in folder.glob("*.dxf")} == original
