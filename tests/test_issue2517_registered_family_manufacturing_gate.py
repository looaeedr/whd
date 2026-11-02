# -*- coding: utf-8 -*-
"""#2517: a registered, unsupported Family cannot enter generic DXF exporters.

All emitters here are intentionally simulated; this is dispatch authorization
coverage, not physical DXF, factory readiness or complete assembly certification.
"""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types.policy import require_implemented_manufacturing_family
from ae_engine.contracts import (
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    IndicatorBoxPartSpec,
    ManufacturingContext,
)


def _spec(part_kind, model):
    if part_kind == "door":
        return DoorPartSpec(
            width=500, height=600, thickness=2, frame_width=25,
            model_name=model,
        )
    if part_kind == "box":
        return BoxBodyPartSpec(
            width=500, height=600, depth=200, thickness=2,
            frame_width=25, model_name=model,
        )
    if part_kind == "endcap":
        return EndCapPartSpec(
            width=500, depth=200, thickness=2, frame_width=25,
            model_name=model,
        )
    if part_kind == "base":
        return BasePlatePartSpec(
            width=500, height=600, thickness=2,
            shrink_top=12, shrink_bottom=12, shrink_left=12,
            shrink_right=12, bend=20, model_name=model,
        )
    if part_kind == "indicator":
        return IndicatorBoxPartSpec(layer_groups=(2, 3), thickness=2, model_name=model)
    raise AssertionError(f"unexpected part kind: {part_kind}")


def _must_not_export(*args, **kwargs):
    raise AssertionError("registered unimplemented Family entered manufacturing")


@pytest.mark.parametrize("family", ["RO", "ro", "落地盤", "  rO  "])
@pytest.mark.parametrize("kind", ["door", "box", "endcap", "base", "indicator"])
def test_registered_unimplemented_family_fails_before_any_dxf_write(
    family, kind, tmp_path, monkeypatch
):
    monkeypatch.setattr(manufacturing_api, "_export_to_temp", _must_not_export)
    target = tmp_path / "not_yet_created" / f"{kind}.dxf"

    with pytest.raises(ValueError, match="CABINET_FAMILY_NOT_IMPLEMENTED: RO"):
        manufacturing_api.generate_part(
            _spec(kind, family), target,
            ManufacturingContext(resource_root=tmp_path, overwrite=True),
        )
    assert not target.exists()
    assert not target.parent.exists()


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("金庫型", "金庫型"),
        ("VAULT", "金庫型"),
        ("vault", "金庫型"),
        ("受電箱", "受電箱"),
        ("RECEIVING", "受電箱"),
        ("receiving", "受電箱"),
        (None, None),
        ("工廠舊版未註冊型號", None),
    ],
)
def test_family_registry_guard_retains_existing_implemented_and_legacy_routes(
    family, expected, tmp_path, monkeypatch
):
    assert require_implemented_manufacturing_family(family) == expected
    seen = []

    def fake_emit(spec, temp_path, context):
        seen.append(spec)
        Path(temp_path).write_text("TEST_ROUTE_ONLY", encoding="utf-8")
        return "test_route_only", None, None

    monkeypatch.setattr(manufacturing_api, "_export_to_temp", fake_emit)
    target = tmp_path / "out" / "door.dxf"
    result = manufacturing_api.generate_part(
        _spec("door", family), target,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert len(seen) == 1
    assert result.exporter_name == "test_route_only"
    assert target.read_text(encoding="utf-8") == "TEST_ROUTE_ONLY"
