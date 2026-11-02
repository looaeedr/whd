"""#2517: GUI cannot decide BoxBody integral / multipart render factory."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec, ManufacturingContext
from gui_modules.application import fold_designer_manufacturing_projection as gui


def _body(structure=None):
    return BoxBodyPartSpec(
        width=800, height=1600, depth=350, thickness=2, frame_width=25,
        model_name="受電箱", structure_state=structure or {},
    )


@pytest.mark.parametrize("kind,expected", [
    ("integral", "single"),
    ("two_piece_w_split", "multipart"),
    ("three_piece_w_split", "multipart"),
    ("three_piece_side_back_split", "multipart"),
    ("unknown-legacy", "single"),
])
def test_engine_routes_canonical_box_body_structure_without_gui(monkeypatch, kind, expected):
    output = []
    monkeypatch.setattr(
        api, "build_part_render_data",
        lambda spec, ctx: output.append(("single", spec, ctx)) or "single",
    )
    monkeypatch.setattr(
        api, "build_box_body_structure_render_data",
        lambda spec, ctx: output.append(("multipart", spec, ctx)) or "multipart",
    )
    spec = _body({"active_type": kind})
    ctx = ManufacturingContext(draw_stock=True)
    assert api.build_operator_part_render_data(spec, ctx) == expected
    assert output == [(expected, spec, ctx)]


def test_other_physical_part_and_legacy_box_body_use_same_original_single_factory(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api, "build_part_render_data",
        lambda spec, ctx: calls.append((spec, ctx)) or object(),
    )
    monkeypatch.setattr(
        api, "build_box_body_structure_render_data",
        lambda *_args: pytest.fail("non-BoxBody must not become multipart"),
    )
    ctx = ManufacturingContext(draw_stock=False)
    endcap = EndCapPartSpec(width=800, depth=350, thickness=2,
                            frame_width=25, model_name="金庫型")
    first = api.build_operator_part_render_data(endcap, ctx)
    second = api.build_operator_part_render_data(_body(), ctx)
    assert first is not second
    assert calls == [(endcap, ctx), (_body(), ctx)]


def test_gui_calls_one_public_engine_api_without_structure_manufacturing(monkeypatch):
    calls = []
    marker = object()
    monkeypatch.setattr(
        api, "build_operator_part_render_data",
        lambda spec, context: calls.append((spec, context)) or marker,
    )
    host = SimpleNamespace(_phase6_input_snapshot={"model": "金庫型"})
    spec = _body({"active_type": "three_piece_side_back_split"})
    ctx = ManufacturingContext(draw_stock=False)
    assert gui._authoritative_render_data(host, spec, ctx) is marker
    assert calls == [(spec, ctx)]
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/fold_designer_manufacturing_projection.py"
              ).read_text(encoding="utf-8")
    section = source.split("def _authoritative_render_data(")[1].split(
        "def _require_verified_baseline_sources_for_manufacturing("
    )[0]
    assert "manufacturing_api.build_operator_part_render_data(spec, ctx)" in section
    assert "from phase6_box_body_structure" not in section
    assert "BoxBodyStructureType" not in section
    assert "build_box_body_structure_render_data(" not in section
    assert "build_part_render_data(spec, ctx)" not in section
