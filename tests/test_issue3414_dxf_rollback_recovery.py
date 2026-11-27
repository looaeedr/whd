from hashlib import sha256
from pathlib import Path
import os
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_selected_export import save_selected_resolved_manufacturing_dxf
from tests.test_issue3414_box_body_piece_marking_confirm import KEYS, case, marks, opened

def test_failed_restore_keeps_all_original_dxf_bytes(tmp_path, monkeypatch):
    ws, read = case()
    _,geometry = read()
    assert ws.commit_box_body_piece_marking(opened(*read(),KEYS[1]),marks(geometry,KEYS[1]),read_current=read)
    snapshot = read()[0]
    folder = tmp_path / "out"
    folder.mkdir()
    def emit():
        return save_selected_resolved_manufacturing_dxf(snapshot,geometry,{"box_body":True},folder,read_current_owner_source=read)
    assert len(emit()) == 3
    def digest():
        return {p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
    before=digest()
    real=os.replace
    moved=[]
    restore_attempts=[]
    def replace_then_switch(src,dst,*args,**kwargs):
        a,b=Path(src),Path(dst)
        if a.parent.name.startswith(".whd-dxf-backup-") and b.parent == folder:
            restore_attempts.append(b.name)
            if len(restore_attempts) == 1:
                raise PermissionError("simulated locked destination during restore")
        result=real(src,dst,*args,**kwargs)
        if b.parent==folder and b.suffix==".dxf" and a.parent.name.startswith(".whd-dxf-stage-"):
            moved.append(b.name)
            if len(moved)==1:
                ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"integral",800))
        return result
    monkeypatch.setattr(os,"replace",replace_then_switch)
    with pytest.raises(OSError, match="WHD_DXF_ROLLBACK_INCOMPLETE") as error:
        emit()
    assert isinstance(error.value.__cause__, ValueError)
    assert "ROOT_MARKING_OWNER_STALE" in str(error.value.__cause__)
    assert len(restore_attempts) == 3
    first, *restored = restore_attempts
    recovery, = folder.glob(".whd-dxf-backup-*")
    assert str(recovery) in str(error.value)
    assert [p.name for p in recovery.iterdir()] == [first]
    assert sha256((recovery / first).read_bytes()).hexdigest() == before[first]
    assert all(sha256((folder / name).read_bytes()).hexdigest() == before[name]
               for name in restored)
    assert not list(folder.glob(".whd-dxf-stage-*"))
