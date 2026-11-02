# -*- coding: utf-8 -*-
"""#2517: shared BasePlate manufacture must honor registered Family aliases.

This is a routing/negative-capability test. Fake emitters exercise the shared
Python dispatcher; they do not assert that a real DXF has been certified.
"""
from pathlib import Path

import pytest

from ae_engine.cabinet_types.policy import base_plate_requires_explicit_bend_pattern
from ae_engine.contracts import BasePlatePartSpec, ManufacturingContext
from ae_engine import manufacturing_api


def _base_plate(family, *, pattern=None):
    return BasePlatePartSpec(
        width=500.0,
        height=600.0,
        thickness=2.0,
        shrink_top=55.0,
        shrink_bottom=55.0,
        shrink_left=55.0,
        shrink_right=55.0,
        bend=15.0,
        model_name=family,
        receiving_bend_pattern=pattern,
    )


def _must_not_run(*args, **kwargs):
    raise AssertionError("an unapproved manufacturing route was entered")


@pytest.mark.parametrize(
    "model_name",
    ["受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "],
)
def test_receiving_family_alias_fails_closed_before_any_base_plate_export(
    model_name, tmp_path, monkeypatch
):
    assert base_plate_requires_explicit_bend_pattern(model_name) is True
    monkeypatch.setattr(manufacturing_api, "build_part_render_data", _must_not_run)
    monkeypatch.setattr(manufacturing_api.ae, "export_base_plate_dxf", _must_not_run)
    monkeypatch.setattr(manufacturing_api.ae, "export_unknown_base_plate_dxf", _must_not_run)

    output = tmp_path / "receiving_base.dxf"
    with pytest.raises(
        ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING"
    ):
        manufacturing_api.generate_part(
            _base_plate(model_name),
            output,
            ManufacturingContext(resource_root=tmp_path),
        )
    assert not output.exists()
    assert list(tmp_path.glob(".*.tmp-*.dxf")) == []


@pytest.mark.parametrize("model_name", ["受電箱", "receiving", "RECEIVING"])
def test_confirmed_receiving_pattern_routes_through_same_guarded_final_scene(
    model_name, tmp_path, monkeypatch
):
    assert base_plate_requires_explicit_bend_pattern(model_name) is True

    scene_token = object()
    seen = []

    def fake_build(spec, context):
        seen.append(("build", spec))
        return scene_token

    def fake_save(render, path, *, overwrite=False):
        assert render is scene_token
        assert overwrite is True
        seen.append(("save", Path(path).name))
        Path(path).write_text("SCENE_ROUTE_ONLY", encoding="utf-8")

    monkeypatch.setattr(manufacturing_api, "build_part_render_data", fake_build)
    monkeypatch.setattr(manufacturing_api, "save_part_render_data_dxf", fake_save)
    monkeypatch.setattr(manufacturing_api.ae, "export_base_plate_dxf", _must_not_run)
    monkeypatch.setattr(manufacturing_api.ae, "export_unknown_base_plate_dxf", _must_not_run)

    output = tmp_path / "confirmed_base.dxf"
    result = manufacturing_api.generate_part(
        _base_plate(model_name, pattern="SOURCE_CONFIRMED_TEST_PATTERN"),
        output,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert result.exporter_name == "final_scene_base_plate_structure_export"
    assert result.part_kind == "base_plate"
    assert [name for name, _ in seen] == ["build", "save"]
    assert output.read_text(encoding="utf-8") == "SCENE_ROUTE_ONLY"


@pytest.mark.parametrize("model_name", ["金庫型", "VAULT", "vault", None])
def test_vault_and_legacy_base_plate_still_use_shared_generic_exporter(
    model_name, tmp_path, monkeypatch
):
    assert base_plate_requires_explicit_bend_pattern(model_name) is False

    def fake_legacy_export(path, *args, **kwargs):
        assert kwargs["W_val"] == 500.0
        Path(path).write_text("LEGACY_ROUTE_ONLY", encoding="utf-8")

    monkeypatch.setattr(manufacturing_api, "build_part_render_data", _must_not_run)
    monkeypatch.setattr(manufacturing_api.ae, "export_base_plate_dxf", fake_legacy_export)

    output = tmp_path / "vault_base.dxf"
    result = manufacturing_api.generate_part(
        _base_plate(model_name),
        output,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert result.exporter_name == "export_base_plate_dxf"
    assert output.read_text(encoding="utf-8") == "LEGACY_ROUTE_ONLY"
