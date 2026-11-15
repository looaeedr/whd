"""#2517: actual GUI PAD+Base button consumes saved Engine 2D/3D and real DXFs.

No manufacturing API monkeypatches: only Tk dialogs and the GUI FinalScene
reader are headlessly wired to the real installed physical Engine parts.
This is PART_ONLY CHECK/Q, NEVER whole-cabinet/PAD production certification.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from tkinter import simpledialog

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, update_receiving_bay
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_pad_pair_manufacturing import (
    verified_pad_base_physical_sheets,
)
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_receiving_nfb_pad_delivery import installed_pair
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make


def _physical_gui_saved_source(tmp_path):
    original, installed = installed_pair()
    initial_copy = deepcopy(original)
    before_pad, before_sheets = verified_pad_base_physical_sheets(
        original, installed,
    )
    assert len(before_pad) == 1 and len(before_sheets) == 2
    physical = deepcopy(original)
    # An older in-memory fixture's proto layout is not a persisted project.
    # Use the original public Set/Bay writer and the exact committed NFB rows.
    physical["receiving_layout"] = update_receiving_bay(
        new_receiving_layout(
            width=original["w"], height=original["h"], depth=original["d"],
        ),
        set_index=0, bay_index=0,
        nfb_config_submitted=True,
        nfb_config=deepcopy(original["nfb_config"]),
    )
    project_path = project.write_project(
        tmp_path / "committed-pad-base-gui-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": physical},
    )
    loaded = project.read_project(project_path)["snapshot"]
    selected = api.resolve_receiving_pad_base_export_source(loaded)
    assert selected.version_id
    assert selected.snapshot["nfb_config_submitted"] is True
    assert selected.snapshot["nfb_config"] == original["nfb_config"]
    assert api.committed_nfb_pad_draft_parts(loaded)
    # Real Engine FinalScene assembly; the GUI adapter will read these exact
    # same resolved physical sheets (not a fake or view-only stage).
    restored_parts = apply_committed_csv_v5_to_canonical_parts(
        selected.snapshot, (_make(selected.snapshot),),
    )
    after_pad, after_sheets = verified_pad_base_physical_sheets(
        selected.snapshot, restored_parts,
    )
    assert len(after_pad) == len(before_pad)
    assert {row.physical_id for row in after_pad} == {
        row.physical_id for row in before_pad
    }
    assert set(after_sheets) == set(before_sheets)
    for key in before_sheets:
        assert after_sheets[key].material.equals(before_sheets[key].material)
        assert after_sheets[key].fold_guides == before_sheets[key].fold_guides
        assert after_sheets[key].scene == before_sheets[key].scene
    assert original == initial_copy
    return project_path, loaded, selected, restored_parts, after_sheets


def _call_real_gui(monkeypatch, loaded, parts, root, *, mutate_at=None):
    import fold_designer_bridge as bridge

    designer = SimpleNamespace(
        _phase6_input_snapshot=loaded,
        designer_workspace=None,
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _flush_phase6_authoritative_state=lambda: None,
    )
    # Main GUI numeric widgets are independent from the designer's committed
    # snapshot until its next sync. The shipped button must witness both.
    live = {key: loaded[key] for key in ("w", "h", "d", "t")}
    host.get_float_values = lambda: deepcopy(live)
    received = []
    # This is only the GUI FinalScene reader seam: the returned parts are
    # pre-resolved by the genuine committed-CSV Engine above.
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda given: (
            SimpleNamespace(
                query_assembly_render_data=lambda: SimpleNamespace(
                    assembly_parts=parts,
                ),
            )
            if given is designer else pytest.fail("different GUI owner")
        ),
    )
    def askstring(title, *_args, **_kw):
        if mutate_at == "live_material" and "材質" in title:
            live["w"] += 1.
        if mutate_at == "live_process" and "製程" in title:
            live["d"] += 1.
        return "SPCC" if "材質" in title else "LASER"

    monkeypatch.setattr(simpledialog, "askstring", askstring)

    def quantity(*_args, **_kwargs):
        if mutate_at == "quantity":
            loaded["t"] = 3.0
        if mutate_at == "live_quantity":
            live["t"] = 3.0
        return 2

    def directory(**_kw):
        if mutate_at == "directory":
            loaded["t"] = 3.0
        if mutate_at == "live_directory":
            live["h"] += 1.
        return str(root)

    monkeypatch.setattr(simpledialog, "askinteger", quantity)
    monkeypatch.setattr(gui.filedialog, "askdirectory", directory)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: received.append(("error", title, detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: received.append(("success", title, detail)))
    result = gui.export_receiving_pad_base_part_only_dxf(host)
    return result, received


def test_real_gui_pad_base_button_from_persisted_set_bay_reopens_check_q(
    tmp_path, monkeypatch,
):
    path, loaded, selected, parts, after_sheets = _physical_gui_saved_source(tmp_path)
    before = deepcopy(loaded)
    result, events = _call_real_gui(
        monkeypatch, loaded, parts, tmp_path,
    )
    assert result is not None, events
    assert result.scope == "RECEIVING_PAD_BASE_PAIR_PART_ONLY_CHECK_Q"
    assert (result.pad_piece_count, result.base_piece_count) == (2, 2)
    assert len(result.files) == 2
    output = Path(result.output_directory)
    assert output.name.startswith(api.safe_dxf_part_stem(selected.version_id))
    assert output.is_dir()
    assert [event[0] for event in events] == ["success"]
    assert loaded == before
    assert path.is_file()
    receipt = json.loads(
        (output / "PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json").read_text(
            encoding="utf-8",
        )
    )
    assert receipt["version_id"] == selected.version_id
    assert receipt["box_count"] == 2
    assert receipt["pad_total"] == 2 and receipt["base_total"] == 2
    assert receipt["full_cabinet_manufacturing_released"] is False
    assert {part["physical_id"] for part in receipt["sources"]}
    assert len(tuple(output.glob("*.dxf"))) == len(result.files)
    for filename in result.files:
        drawing = ezdxf.readfile(output / filename)
        assert drawing.audit().errors == []
        assert any(item.dxf.layer == "CUTTING" for item in drawing.modelspace())
    assert len(after_sheets) == 2  # separate PAD and Base 2D FinalScenes


@pytest.mark.parametrize("mutate_at", ("quantity", "directory"))
def test_real_gui_pad_base_saved_source_drift_never_publishes_check_q(
    tmp_path, monkeypatch, mutate_at,
):
    project_path, loaded, _selected, parts, _after = (
        _physical_gui_saved_source(tmp_path)
    )
    original_disk = project_path.read_bytes()
    result, events = _call_real_gui(
        monkeypatch, loaded, parts, tmp_path, mutate_at=mutate_at,
    )
    assert result is None
    assert [event[0] for event in events] == ["error"]
    assert "DXF 出圖來源已變更" in events[0][2]
    assert not any(item.is_dir() for item in tmp_path.iterdir())
    assert not list(tmp_path.glob("*.dxf"))
    assert project_path.read_bytes() == original_disk


@pytest.mark.parametrize("mutate_at", (
    "live_material", "live_process", "live_quantity", "live_directory",
))
def test_saved_pad_base_gui_button_unsynced_main_numeric_edit_cannot_release_q(
    tmp_path, monkeypatch, mutate_at,
):
    # A real .p6fold project, actual Engine 2D PAD and BASE FinalScene
    # verified against signed 3D installation. Only main GUI numeric widgets
    # mutate mid-dialog; the authoritative saved source remains unchanged.
    path, loaded, _selected, actual_parts, actual_2d = (
        _physical_gui_saved_source(tmp_path)
    )
    disk = path.read_bytes()
    snapshot = deepcopy(loaded)
    assert len(actual_2d) == 2
    result, events = _call_real_gui(
        monkeypatch, loaded, actual_parts, tmp_path, mutate_at=mutate_at,
    )
    assert result is None
    assert [event[0] for event in events] == ["error"]
    assert "DXF 即時操作來源已變更" in events[0][2]
    assert path.read_bytes() == disk
    assert loaded == snapshot
    assert not list(tmp_path.glob("*.dxf"))
    assert not any(item.is_dir() for item in tmp_path.iterdir())


def test_pad_base_gui_live_numeric_reader_attached_during_modal_must_fail_closed(
    tmp_path, monkeypatch,
):
    # The reader itself is part of the source witness. Passing a headless
    # legacy host must not authorize a newly attached, unsynchronized widget.
    path, loaded, _selected, actual_parts, _ = _physical_gui_saved_source(tmp_path)
    saved = path.read_bytes()
    import fold_designer_bridge as bridge
    designer = SimpleNamespace(
        _phase6_input_snapshot=loaded, designer_workspace=None,
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _flush_phase6_authoritative_state=lambda: None,
    )
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda given: SimpleNamespace(
            query_assembly_render_data=lambda: SimpleNamespace(
                assembly_parts=actual_parts,
            )
        ) if given is designer else pytest.fail("wrong scene owner"),
    )
    monkeypatch.setattr(
        simpledialog, "askstring",
        lambda title, *_a, **_k: "SPCC" if "材質" in title else "LASER",
    )
    monkeypatch.setattr(simpledialog, "askinteger", lambda *_a, **_k: 2)

    def directory(**_kw):
        host.get_float_values = lambda: {
            key: loaded[key] for key in ("w", "h", "d", "t")
        }
        return str(tmp_path)

    monkeypatch.setattr(gui.filedialog, "askdirectory", directory)
    messages = []
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: messages.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: messages.append(("success", detail)))
    assert gui.export_receiving_pad_base_part_only_dxf(host) is None
    assert messages and messages[0][0] == "error"
    assert "DXF 即時操作來源已變更" in messages[0][1]
    assert not any(item.is_dir() for item in tmp_path.iterdir())
    assert path.read_bytes() == saved
