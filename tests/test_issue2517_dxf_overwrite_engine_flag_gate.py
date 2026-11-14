"""#2517 an invalid raw overwrite flag must not replace a physical DXF."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import BoxBodyPartSpec, DoorPartSpec, ManufacturingContext
from ae_engine import manufacturing_export as sink
from ae_engine.manufacturing_scene_orchestration import (
    generate_box_body_structure_parts,
)
from gui_modules.application.fold_designer_manufacturing_projection import (
    _export_authoritative_part,
)


@pytest.mark.parametrize("bad", [
    "false", "true", "0", "", False if False else 0, 1, 1.0,
    None, [], {},
])
@pytest.mark.parametrize("verify_reopen", [False, True])
def test_public_final_scene_sink_rejects_non_boolean_before_any_output_change(
    tmp_path, bad, verify_reopen,
):
    target = tmp_path / "approved.dxf"
    target.write_bytes(b"ORIGINAL ACCEPTED DXF")
    render = SimpleNamespace(metadata={}, scene=object())
    with pytest.raises(TypeError, match="DXF_OVERWRITE_BOOL_REQUIRED"):
        api.save_part_render_data_dxf(
            render, target, overwrite=bad, verify_reopen=verify_reopen,
        )
    assert target.read_bytes() == b"ORIGINAL ACCEPTED DXF"
    assert sorted(x.name for x in tmp_path.iterdir()) == ["approved.dxf"]


def test_explicit_false_keeps_existing_single_part_output(tmp_path):
    target = tmp_path / "approved.dxf"
    target.write_bytes(b"OLD")
    render = SimpleNamespace(metadata={}, scene=object())
    with pytest.raises(FileExistsError):
        api.save_part_render_data_dxf(render, target, overwrite=False)
    assert target.read_bytes() == b"OLD"


@pytest.mark.parametrize("bad", ["false", "true", 0, 1, None])
def test_generate_part_rejects_invalid_context_before_export_or_path_change(
    tmp_path, bad,
):
    out = tmp_path / "new" / "door.dxf"
    spec = DoorPartSpec(width=500, height=600, thickness=2, frame_width=25)
    with pytest.raises(TypeError, match="DXF_OVERWRITE_BOOL_REQUIRED"):
        api.generate_part(spec, out, ManufacturingContext(overwrite=bad))
    assert not out.parent.exists()


@pytest.mark.parametrize("verify_reopen", [False, True])
def test_multipart_engine_rejects_context_before_render_or_directory(
    tmp_path, verify_reopen,
):
    out = tmp_path / "multi"
    spec = BoxBodyPartSpec(
        width=600, height=800, depth=350, thickness=2, frame_width=25,
    )
    with pytest.raises(TypeError, match="DXF_OVERWRITE_BOOL_REQUIRED"):
        generate_box_body_structure_parts(
            spec, out, ManufacturingContext(overwrite="false"),
            verify_reopen=verify_reopen,
        )
    assert not out.exists()


def test_atomic_batch_writer_rejects_untrusted_overwrite_before_stage(tmp_path):
    directory = tmp_path / "batch"
    with pytest.raises(TypeError, match="DXF_OVERWRITE_BOOL_REQUIRED"):
        sink._save_resolved_rows_atomic(
            (), directory, save_part_render_data_dxf=lambda *args, **kwargs: None,
            overwrite="false",
        )
    assert not directory.exists()


def test_composed_panel_public_boundary_uses_same_flag_guard(tmp_path):
    target = tmp_path / "composed.dxf"
    with pytest.raises(TypeError, match="DXF_OVERWRITE_BOOL_REQUIRED"):
        api.save_composed_panel_dxf(
            (), target, pre_commit_guard=lambda: None, overwrite="false",
        )
    assert not target.exists()


def test_gui_forwards_raw_context_to_original_engine_dxf_save(monkeypatch, tmp_path):
    ctx = SimpleNamespace(overwrite="false")
    calls = []
    render = SimpleNamespace(pieces=None, metadata={}, scene=object())
    host = SimpleNamespace(
        workspace_controller=None,
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda spec, context: render,
    )
    def record(data, filepath, *, overwrite, verify_reopen):
        calls.append((data, Path(filepath), overwrite, verify_reopen))
        return "simulated-output"
    monkeypatch.setattr(api, "save_part_render_data_dxf", record)
    target = tmp_path / "approved.dxf"
    assert _export_authoritative_part(host, "part", target, context=ctx) == "simulated-output"
    assert calls == [(render, target, "false", True)]
    assert "overwrite=bool(" not in inspect.getsource(_export_authoritative_part)
