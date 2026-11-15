"""#2517: an Engine-verified DXF stage stays *byte-identical* through GUI modals.

Uses the real saved .p6fold source, actual GUI export_selected_dxf, real
canonical Engine 2D CUTTING/BEND, and independently reopened DXF files.
Only the already-manufactured staged transport is modified in test dialogs.
No second GUI manufacturing geometry or fabricated certified part is used.
"""
from __future__ import annotations

import os
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
from tests.test_issue2517_gui_final_dxf_publish_source_guard import (
    _host, _physical_panels, _project_source,
)


def _real_dxf(path, width):
    result = api.save_composed_panel_dxf(
        _physical_panels(width), path, pre_commit_guard=lambda: None,
    )
    assert Path(result.path).is_file()
    drawing = ezdxf.readfile(path)
    assert drawing.audit().errors == []
    assert {"CUTTING", "BEND"} <= {
        item.dxf.layer for item in drawing.modelspace()
    }


def _run_actual_gui(monkeypatch, host, folder, *, mutation=None, partial=False):
    events = []
    stage = {"path": None}
    monkeypatch.setattr(gui, "_selected_export_flags",
                        lambda *_: {"door": True})
    monkeypatch.setattr(gui, "_validate_selected_indicator_exports",
                        lambda *_: None)
    monkeypatch.setattr(api, "plan_unconfigured_receiving_base_export_retry",
                        lambda *_: None)
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_: str(folder))

    def engine(_host, staging, _vals, _flags, _draw_stock):
        stage["path"] = Path(staging)
        _real_dxf(Path(staging) / "P1.dxf", 165.0)
        if partial:
            # Dialog transport only; the source for the test DXF remains
            # an authentic verified canonical Engine panel.
            host._phase6_nfb_partial_export_report = {
                "actual_export_count": 1,
                "held_actual_count": 1,
                "rows": [{
                    "version_id": "V1", "part_id": "P1", "status": "PART_ONLY",
                    "actual_count": 1, "reason": "other physical source held",
                }],
            }
        return ["P1.dxf"], []

    monkeypatch.setattr(gui, "_export_selected_parts", engine)

    def confirm(title, *_args, **_kwargs):
        events.append(("modal", title))
        if mutation is not None:
            mutation(stage["path"])
        return True

    monkeypatch.setattr(gui.messagebox, "askyesno", confirm)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda _title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda _title, detail: events.append(("success", detail)))
    gui.export_selected_dxf(host)
    return events


def _replace_stage_with_another_valid_engine_dxf(stage):
    alternative = stage / "alternate.dxf"
    _real_dxf(alternative, 135.0)
    os.replace(alternative, stage / "P1.dxf")
    # Names still exactly match the original manifest; bytes no longer do.
    assert sorted(path.name for path in stage.iterdir()) == ["P1.dxf"]


@pytest.mark.parametrize("mutation", (
    "extra_dxf", "missing", "replaced_dxf", "extra_directory", "symlink",
))
def test_true_saved_selected_gui_modal_cannot_publish_modified_verified_stage(
    tmp_path, monkeypatch, mutation,
):
    saved = _project_source(tmp_path)
    original_snapshot = dict(saved)
    host, workspace = _host(saved)
    current = tmp_path / "P1.dxf"
    _real_dxf(current, 110.0)
    previous = current.read_bytes()

    def mutate(stage):
        if mutation == "extra_dxf":
            _real_dxf(stage / "unreported.dxf", 135.0)
        elif mutation == "missing":
            (stage / "P1.dxf").unlink()
        elif mutation == "replaced_dxf":
            _replace_stage_with_another_valid_engine_dxf(stage)
        elif mutation == "extra_directory":
            (stage / "unreported-folder").mkdir()
        elif mutation == "symlink":
            # Exactly the original name and *valid* DXF bytes, but not the
            # original Engine-verified staging file.
            previous_stage = stage / "P1.dxf"
            previous_stage.unlink()
            try:
                os.symlink(current, previous_stage)
            except (OSError, NotImplementedError):
                pytest.skip("file symlink creation not authorized here")
        else:
            pytest.fail(f"unknown transport mutation {mutation}")

    events = _run_actual_gui(
        monkeypatch, host, tmp_path, mutation=mutate,
    )
    assert any(e[0] == "modal" and e[1] == "DXF 檔名已存在"
               for e in events), events
    assert any(e[0] == "error" and "暫存檔案與引擎回報不一致" in e[1]
               for e in events), events
    assert not any(e[0] == "success" for e in events)
    assert current.read_bytes() == previous
    assert not ezdxf.readfile(current).audit().errors
    assert {item.name for item in tmp_path.glob("*.dxf")} == {"P1.dxf"}
    assert not tuple(tmp_path.glob(".whd-export-backup-*"))
    assert workspace.snapshot()["part_features"] == original_snapshot["part_features"]


def test_true_saved_gui_partial_export_modal_cannot_publish_postapproval_extra(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    host, _workspace = _host(saved)
    events = _run_actual_gui(
        monkeypatch, host, tmp_path, partial=True,
        mutation=lambda stage: _real_dxf(stage / "unreported.dxf", 135.0),
    )
    assert any(e[0] == "modal" and e[1] == "NFB 僅部分匯出"
               for e in events), events
    assert any(e[0] == "error" and "暫存檔案與引擎回報不一致" in e[1]
               for e in events), events
    assert not any(e[0] == "success" for e in events)
    assert not list(tmp_path.glob("*.dxf"))
    assert not tuple(tmp_path.glob(".whd-export-backup-*"))


def test_true_saved_gui_unchanged_modal_reopens_only_exact_engine_dxf(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    host, _workspace = _host(saved)
    destination = tmp_path / "P1.dxf"
    _real_dxf(destination, 110.0)
    before = destination.read_bytes()
    events = _run_actual_gui(monkeypatch, host, tmp_path)
    assert any(e[0] == "modal" and e[1] == "DXF 檔名已存在"
               for e in events)
    assert [e[0] for e in events if e[0] in ("error", "success")] == ["success"]
    after = destination.read_bytes()
    assert after != before
    drawing = ezdxf.readfile(destination)
    assert not drawing.audit().errors
    assert {"CUTTING", "BEND"} <= {
        row.dxf.layer for row in drawing.modelspace()
    }
    assert not tuple(tmp_path.glob(".whd-export-backup-*"))


def test_batch_rollback_if_stage_contents_change_during_second_source_guard(
    tmp_path,
):
    saved = _project_source(tmp_path)
    host, workspace = _host(saved)
    guard = gui._current_authoritative_export_guard(
        host.fold_designer_app, saved,
    )
    stage = tmp_path / "engine-stage"
    stage.mkdir()
    _real_dxf(stage / "P1.dxf", 165.0)
    seal = gui._seal_staged_export_manifest(stage, ["P1.dxf"])
    dest = tmp_path / "P1.dxf"
    _real_dxf(dest, 110.0)
    prior = dest.read_bytes()
    calls = 0

    def change_stage_after_original_files_are_backed_up():
        nonlocal calls
        calls += 1
        guard()
        if calls == 2:
            _replace_stage_with_another_valid_engine_dxf(stage)

    with pytest.raises(ValueError, match="暫存檔案與引擎回報不一致"):
        gui._commit_staged_project_export(
            stage, tmp_path, expected_manifest=seal,
            pre_commit_guard=change_stage_after_original_files_are_backed_up,
        )
    assert calls == 2
    assert dest.read_bytes() == prior
    assert not ezdxf.readfile(dest).audit().errors
    assert not tuple(tmp_path.glob(".whd-export-backup-*"))
    assert workspace.snapshot()["part_features"] == saved["part_features"]
