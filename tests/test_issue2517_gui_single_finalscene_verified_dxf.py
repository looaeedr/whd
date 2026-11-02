"""#2517 GUI single-part FinalScene DXF must be reloaded before publication."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
from gui_modules.application import fold_designer_manufacturing_projection as gui


def _render():
    spec = DoorPartSpec(
        width=500, height=600, thickness=2,
        frame_width=25, model_name="金庫型",
    )
    context = ManufacturingContext(
        resource_root=Path(__file__).resolve().parents[1],
        draw_stock=False,
    )
    return manufacturing_api.build_operator_part_render_data(spec, context)


def test_single_part_finalscene_stages_reopens_and_matches_actual_dxf(tmp_path):
    render = _render()
    destination = tmp_path / "門-展開.dxf"
    actual = manufacturing_api.save_part_render_data_dxf(
        render, destination, verify_reopen=True,
    )
    assert Path(actual) == destination
    assert destination.is_file()
    assert ezdxf.readfile(destination).audit().errors == []
    assert verify_saved_part_render_data_dxf(render, destination).ok
    assert not list(tmp_path.glob(".whd-dxf-stage-*"))


def test_failed_canonical_reopen_keeps_previous_valid_output(tmp_path, monkeypatch):
    import ae_engine.manufacturing_verification as verification

    render = _render()
    destination = tmp_path / "door.dxf"
    destination.write_bytes(b"PREVIOUS_APPROVED_DXF")
    monkeypatch.setattr(
        verification, "verify_saved_part_render_data_dxf",
        lambda *_args, **_kwargs: SimpleNamespace(ok=False),
    )
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        manufacturing_api.save_part_render_data_dxf(
            render, destination, overwrite=True, verify_reopen=True,
        )
    assert destination.read_bytes() == b"PREVIOUS_APPROVED_DXF"
    assert not list(tmp_path.glob(".whd-dxf-stage-*"))


def test_gui_single_part_exports_cached_engine_finalscene_with_verification(monkeypatch, tmp_path):
    render = SimpleNamespace(pieces=(), scene=object())
    spec, ctx = object(), ManufacturingContext()
    calls = []
    def sink(data, path, **kwargs):
        calls.append((data, Path(path), kwargs))
        return str(path)
    monkeypatch.setattr(manufacturing_api, "save_part_render_data_dxf", sink)
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda given_spec, given_ctx: (
            render if (given_spec is spec and given_ctx is ctx) else None
        ),
    )
    destination = tmp_path / "door.dxf"
    actual = gui._export_authoritative_part(host, spec, destination, ctx)
    assert actual == str(destination)
    assert calls == [(render, destination, {
        "overwrite": ctx.overwrite, "verify_reopen": True,
    })]


@pytest.mark.parametrize("bad", [0, 1, None, "true"])
def test_verified_flag_requires_explicit_boolean(tmp_path, bad):
    with pytest.raises(TypeError, match="verify_reopen must be bool"):
        manufacturing_api.save_part_render_data_dxf(
            _render(), tmp_path / "door.dxf", verify_reopen=bad,
        )
    assert not (tmp_path / "door.dxf").exists()
