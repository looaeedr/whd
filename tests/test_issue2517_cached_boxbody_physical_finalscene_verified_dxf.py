"""#2517 multi-piece GUI export consumes cached Engine FinalScene sheets."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
from gui_modules.application import fold_designer_manufacturing_projection as gui
from tests.test_issue2517_confirmed_receiving_box_body_three_physical_dxf import (
    REPO, _three_piece_spec,
)


def _real():
    spec = _three_piece_spec()
    ctx = ManufacturingContext(resource_root=REPO, draw_stock=False)
    render_data = manufacturing_api.build_operator_part_render_data(spec, ctx)
    assert len(render_data.pieces) == 3
    return spec, ctx, render_data


def test_real_cached_three_piece_engine_saves_all_original_finalscenes_without_rebuild(
    tmp_path, monkeypatch,
):
    import ae_engine.manufacturing_scene_orchestration as factory

    spec, ctx, render = _real()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("must not rebuild GUI's cached FinalScene")
    monkeypatch.setattr(factory, "build_box_body_structure_render_data", forbidden)

    results = manufacturing_api.generate_box_body_structure_parts(
        spec, tmp_path, ctx, resolved_render_data=render, verify_reopen=True,
    )
    assert len(results) == 3
    assert {Path(x.output_path).name for x in results} == {
        "左側板.dxf", "後面板.dxf", "右側板.dxf",
    }
    for piece, result in zip(render.pieces, results):
        assert result.part_kind == piece.key
        assert ezdxf.readfile(result.output_path).audit().errors == []
        assert verify_saved_part_render_data_dxf(
            piece.render_data, result.output_path,
        ).ok
    assert not list(tmp_path.glob(".whd-dxf-stage-*"))


def test_failed_one_physical_sheet_does_not_publish_or_overwrite_any_sheet(
    tmp_path, monkeypatch,
):
    import ae_engine.manufacturing_verification as verification

    spec, ctx, render = _real()
    keep = tmp_path / "左側板.dxf"
    keep.write_bytes(b"PRIOR_ACCEPTED")
    calls = []
    def fail_second(*_args, **_kwargs):
        calls.append(None)
        return SimpleNamespace(ok=len(calls) != 2)
    monkeypatch.setattr(
        verification, "verify_saved_part_render_data_dxf", fail_second,
    )
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        manufacturing_api.generate_box_body_structure_parts(
            spec, tmp_path,
            ManufacturingContext(resource_root=REPO, draw_stock=False, overwrite=True),
            resolved_render_data=render, verify_reopen=True,
        )
    assert keep.read_bytes() == b"PRIOR_ACCEPTED"
    assert not (tmp_path / "後面板.dxf").exists()
    assert not (tmp_path / "右側板.dxf").exists()
    assert not list(tmp_path.glob(".whd-dxf-stage-*"))


def test_gui_multi_piece_calls_same_engine_factory_with_cached_physical_data(
    monkeypatch, tmp_path,
):
    spec, ctx, render = object(), ManufacturingContext(), SimpleNamespace(
        pieces=(object(), object()),
    )
    calls = []
    result = (object(), object())
    def dispatch(*args, **kwargs):
        calls.append((args, kwargs))
        return result
    monkeypatch.setattr(manufacturing_api, "generate_box_body_structure_parts", dispatch)
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda given_spec, given_ctx: (
            render if given_spec is spec and given_ctx is ctx else None
        ),
    )
    target = tmp_path / "箱身.dxf"
    assert gui._export_authoritative_part(host, spec, target, ctx) is result
    assert calls == [((spec, target.parent, ctx), {
        "resolved_render_data": render, "verify_reopen": True,
    })]


@pytest.mark.parametrize("bad", [1, None, "yes"])
def test_invalid_reopen_option_is_fail_closed(tmp_path, bad):
    spec, ctx, render = _real()
    with pytest.raises(TypeError, match="verify_reopen must be bool"):
        manufacturing_api.generate_box_body_structure_parts(
            spec, tmp_path, ctx, resolved_render_data=render,
            verify_reopen=bad,
        )
    assert not list(tmp_path.iterdir())
