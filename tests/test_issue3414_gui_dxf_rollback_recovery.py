import os
from pathlib import Path

from tests.test_issue2517_gui_dxf_stage_modal_byte_seal import (
    _host, _project_source, _real_dxf, _run_actual_gui, gui,
)


def test_gui_retains_old_verified_dxf_if_restore_is_denied(tmp_path, monkeypatch):
    host, workspace = _host(_project_source(tmp_path))
    old = tmp_path / 'P1.dxf'
    _real_dxf(old, 110.0)
    original = old.read_bytes()
    actual_replace = os.replace
    exposed = []
    restore = []

    def swap(src, dst, *args, **kwargs):
        a,b = Path(src),Path(dst)
        if a.parent.name.startswith('.whd-export-backup-') and b == old:
            restore.append(a)
            raise PermissionError('simulated locked DXF during rollback')
        result = actual_replace(src, dst, *args, **kwargs)
        if b == old and a.parent != tmp_path:
            exposed.append(b)
            workspace.source['part_features']['door'].append({'confirmed':'new source during publish'})
        return result

    monkeypatch.setattr(gui.os, 'replace', swap)
    events = _run_actual_gui(monkeypatch, host, tmp_path)
    assert exposed and restore and any(k == 'error' for k,_ in events), events
    assert not any(k == 'success' for k,_ in events)
    assert restore[0].is_file(), (events, tuple(tmp_path.iterdir()))
    assert restore[0].read_bytes() == original
    assert any(k == 'error' and 'WHD_DXF_ROLLBACK_INCOMPLETE' in msg
               and str(restore[0].parent) in msg for k,msg in events)


def test_legacy_transport_still_checks_staged_seal_without_destination_opt_in(
    tmp_path, monkeypatch,
):
    from ae_engine import manufacturing_export

    stage = tmp_path / "stage"
    stage.mkdir()
    staged = stage / "P1.dxf"
    target = tmp_path / staged.name
    _real_dxf(staged, 165.0)
    expected = gui._seal_staged_export_manifest(stage, [staged.name])
    checked = []
    original_digest = manufacturing_export.verified_dxf_content_digest

    def observe(path):
        checked.append(Path(path))
        return original_digest(path)

    monkeypatch.setattr(manufacturing_export, "verified_dxf_content_digest", observe)
    assert gui._commit_staged_project_export(
        stage, tmp_path, expected_manifest=expected, verify_moved_bytes=False,
    ) == (staged.name,)
    assert checked == [staged]
    assert original_digest(target) == dict(expected)[target.name]
