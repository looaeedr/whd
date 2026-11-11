"""#2517: original PAD/Base paired CHECK/Q DXF cannot publish stale GUI source."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_pad_pair_manufacturing as owner
from gui_modules.project import export_actions as gui
from tests.test_receiving_nfb_pad_delivery import installed_pair


def _real_source():
    snap, installed = installed_pair()
    return snap, installed


def _export(snapshot, installed, target, *, guard=None):
    kwargs = {"pre_commit_guard": guard} if guard is not None else {}
    return api.export_verified_pad_base_part_only(
        snapshot, installed, target,
        version_id="source-verified-pad-pair", box_count=2,
        parameters=api.ManufacturingParameters("SPCC", 2.0, "LASER"),
        **kwargs,
    )


def test_real_pad_base_2d_3d_qualified_check_q_dxf_reopens_with_source_witness(
    tmp_path,
):
    snapshot, installed = _real_source()
    source_before = deepcopy(snapshot)
    checks = []
    def guard():
        checks.append("current")
        assert snapshot == source_before

    target = tmp_path / "verified-pad-base-check-q"
    result = _export(snapshot, installed, target, guard=guard)
    assert result.scope == "RECEIVING_PAD_BASE_PAIR_PART_ONLY_CHECK_Q"
    assert result.pad_piece_count == 2
    assert result.base_piece_count == 2
    assert len(result.files) == 2
    assert len(checks) >= 4  # before real 3D, before Stage, before & after publish
    manifest = json.loads(
        (target / "PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json").read_text(
            encoding="utf-8",
        )
    )
    assert manifest["full_cabinet_manufacturing_released"] is False
    assert manifest["pad_total"] == 2 and manifest["base_total"] == 2
    assert snapshot == source_before
    for name in result.files:
        assert (target / name).is_file()
        doc = ezdxf.readfile(target / name)
        assert any(x.dxf.layer == "CUTTING" for x in doc.modelspace())
    assert not list(tmp_path.glob(".pad-pair-mfg-*"))


def test_noncallable_public_pad_pair_source_guard_rejects_before_physical_geometry(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(
        owner, "verified_pad_base_physical_sheets",
        lambda *_a, **_k: pytest.fail("invalid witness reached real geometry"),
    )
    target = tmp_path / "untrusted"
    with pytest.raises(TypeError, match="PAD_PAIR_SOURCE_GUARD_INVALID"):
        api.export_verified_pad_base_part_only(
            {}, (), target, version_id="version", box_count=1,
            parameters=api.ManufacturingParameters("SPCC", 2.0, "LASER"),
            pre_commit_guard="not-callable",
        )
    assert not target.exists()


def test_real_verified_pad_source_drift_after_3d_recheck_never_creates_dxf(
    tmp_path, monkeypatch,
):
    snapshot, installed = _real_source()
    token = {"rev": 0}
    calls = []
    original = owner.verified_pad_base_physical_sheets
    def resolve_and_drift(*args, **kw):
        actual = original(*args, **kw)
        token["rev"] += 1  # committed Workspace changed during solve
        return actual
    monkeypatch.setattr(owner, "verified_pad_base_physical_sheets", resolve_and_drift)
    def guard():
        calls.append(token["rev"])
        if token["rev"]:
            raise ValueError("PAD_SOURCE_CHANGED")
    folder = tmp_path / "no-stale"
    with pytest.raises(ValueError, match="PAD_SOURCE_CHANGED"):
        _export(snapshot, installed, folder, guard=guard)
    assert calls == [0, 1]
    assert not folder.exists()
    assert not list(tmp_path.glob(".pad-pair-mfg-*"))


def test_drift_after_real_dxf_reopen_rolls_back_unpublished_stage(
    tmp_path, monkeypatch,
):
    from ae_engine import dxf_serialization
    snapshot, installed = _real_source()
    source = {"rev": 0}
    real = dxf_serialization.verify_quantity_check_dxf
    def reopen_then_drift(*args, **kw):
        result = real(*args, **kw)
        source["rev"] = 1
        return result
    monkeypatch.setattr(
        dxf_serialization, "verify_quantity_check_dxf", reopen_then_drift,
    )
    def guard():
        if source["rev"]:
            raise ValueError("PAD_STALE_AFTER_DXF_REOPEN")
    target = tmp_path / "not-published"
    with pytest.raises(ValueError, match="PAD_STALE_AFTER_DXF_REOPEN"):
        _export(snapshot, installed, target, guard=guard)
    assert not target.exists()
    assert not list(tmp_path.glob(".pad-pair-mfg-*"))


def test_drift_inside_atomic_publish_removes_only_new_pad_pair_folder(
    tmp_path, monkeypatch,
):
    snapshot, installed = _real_source()
    source = {"rev": 0}
    actual_replace = owner.os.replace
    old = tmp_path / "original-unrelated.dxf"
    old.write_bytes(b"PREEXISTING-USER-OUTPUT")
    def publish_then_drift(src, dst):
        actual_replace(src, dst)
        source["rev"] = 1  # simulate source change at publish boundary
    monkeypatch.setattr(owner.os, "replace", publish_then_drift)
    def guard():
        if source["rev"]:
            raise ValueError("PAD_SOURCE_MOVED_DURING_PUBLISH")
    target = tmp_path / "new-check-q"
    with pytest.raises(ValueError, match="PAD_SOURCE_MOVED_DURING_PUBLISH"):
        _export(snapshot, installed, target, guard=guard)
    assert not target.exists()
    assert old.read_bytes() == b"PREEXISTING-USER-OUTPUT"
    assert not list(tmp_path.glob(".pad-pair-mfg-*"))


def _gui_host_and_stubs(monkeypatch, tmp_path):
    import fold_designer_bridge as bridge
    from tkinter import simpledialog

    snapshot = {"model": "受電箱", "nfb_config_submitted": True, "t": 2.0}
    workspace_data = {"part_features": {"base_plate": [{"hole": "current"}]}}
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        designer_workspace=SimpleNamespace(snapshot=lambda: deepcopy(workspace_data)),
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _flush_phase6_authoritative_state=lambda: None,
    )
    events = []
    monkeypatch.setattr(api, "committed_nfb_pad_draft_parts",
                        lambda _: ("verified-current-pad",))
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda _: SimpleNamespace(
            query_assembly_render_data=lambda: SimpleNamespace(
                assembly_parts=("actual-3d-base",),
            ),
        ),
    )
    monkeypatch.setattr(
        api, "resolve_receiving_pad_base_export_source",
        lambda s: SimpleNamespace(snapshot=deepcopy(s), version_id="current-v1"),
    )
    monkeypatch.setattr(simpledialog, "askstring",
                        lambda title, _prompt: "SPCC" if "材質" in title else "LASER")
    monkeypatch.setattr(simpledialog, "askinteger", lambda *_a, **_kw: 2)
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_k: str(tmp_path))
    def export(*args, **kwargs):
        events.append(("export", args, kwargs))
        kwargs["pre_commit_guard"]()
        return SimpleNamespace(pad_piece_count=2, base_piece_count=2,
                               output_directory=str(tmp_path))
    monkeypatch.setattr(api, "export_verified_pad_base_part_only", export)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *args: events.append(("error", args)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda *args: events.append(("success", args)))
    return host, snapshot, workspace_data, events


@pytest.mark.parametrize("change", ("snapshot", "workspace"))
def test_gui_modal_project_or_hole_editor_change_cannot_export_stale_dxf(
    tmp_path, monkeypatch, change,
):
    from tkinter import simpledialog
    host, snapshot, workspace, events = _gui_host_and_stubs(
        monkeypatch, tmp_path,
    )
    def edit_during_modal(*_a, **_kw):
        if change == "snapshot":
            snapshot["t"] = 3.0
        else:
            workspace["part_features"]["base_plate"].append({"hole": "edited"})
        return 2
    monkeypatch.setattr(simpledialog, "askinteger", edit_during_modal)
    assert gui.export_receiving_pad_base_part_only_dxf(host) is None
    assert [e[0] for e in events] == ["error"]
    assert "DXF" in str(events[0][1])
    assert not list(tmp_path.iterdir())


def test_gui_unchanged_source_passes_callable_witness_to_public_engine(
    tmp_path, monkeypatch,
):
    host, snapshot, workspace, events = _gui_host_and_stubs(
        monkeypatch, tmp_path,
    )
    before = deepcopy((snapshot, workspace))
    result = gui.export_receiving_pad_base_part_only_dxf(host)
    assert result.pad_piece_count == 2
    assert [e[0] for e in events] == ["export", "success"]
    args, kwargs = events[0][1:]
    assert args[1] == ("actual-3d-base",)
    assert kwargs["box_count"] == 2
    guard = kwargs["pre_commit_guard"]
    assert callable(guard)
    guard()
    assert (snapshot, workspace) == before
    workspace["part_features"]["base_plate"].append({"hole": "late"})
    with pytest.raises(ValueError, match="DXF"):
        guard()
