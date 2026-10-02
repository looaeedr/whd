# -*- coding: utf-8 -*-
from types import SimpleNamespace
from pathlib import Path

from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.sheetmetal_drawing import DrawingScene


def test_resolved_dxf_export_uses_exact_canonical_render_data_without_rebuilding(monkeypatch, tmp_path):
    import ae_engine.manufacturing_api as api
    head_render = SimpleNamespace(scene=DrawingScene(), material=object(), fold_guides=())
    body_render = SimpleNamespace(scene=DrawingScene(), material=object(), fold_guides=())
    resolved = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", body_render),
        ResolvedManufacturingPart("head", head_render),
    ))
    seen = []
    monkeypatch.setattr(api, "save_part_render_data_dxf", lambda render, path, overwrite=False: seen.append((render, Path(path).name)) or str(path))
    result = api.save_resolved_manufacturing_geometry_dxf(resolved, tmp_path, overwrite=True)
    assert [name for _render, name in seen] == ["box_body.dxf", "head.dxf"]
    assert seen[0][0] is body_render
    assert seen[1][0] is head_render
    assert set(result) == {"box_body", "head"}


def test_nc_export_capability_is_explicit_instead_of_rebuilding_geometry():
    import ae_engine.manufacturing_api as api
    status = api.resolved_manufacturing_nc_capability()
    assert status["available"] is False
    assert "production NC" in status["reason"]
