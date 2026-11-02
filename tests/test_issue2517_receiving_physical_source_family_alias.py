# -*- coding: utf-8 -*-
"""#2517 Receiving aliases must consume the SAME dedicated physical source DXFs.

These are real Engine FinalScene/baseline checks; no new formula or alternate
manufacturing adapter is permitted. Direct construction and resolver gates
must not be weaker than generate_part.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from ae_engine.contracts import (
    BoxBodyPartSpec, DoorPartSpec, ManufacturingContext,
)
from ae_engine.manufacturing_api import (
    build_box_body_structure_render_data, build_part_render_data,
    generate_box_body_structure_parts, resolve_manufacturing_request,
)
from ae_engine.manufacturing_contracts import ManufacturingResolveRequest
from tests.test_receiving_dedicated_panel_baselines import spec_for_mode


@pytest.mark.parametrize(
    "family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "],
)
def test_registered_receiving_aliases_load_all_three_real_source_baselines(family):
    render = build_box_body_structure_render_data(
        replace(spec_for_mode(), model_name=family),
    )
    source_files = {
        "left_side": "左側板.dxf",
        "back": "後面板.dxf",
        "right_side": "右側板.dxf",
    }
    assert {piece.role for piece in render.pieces} == set(source_files)
    for piece in render.pieces:
        meta = piece.render_data.metadata
        assert Path(meta["baseline_source_path"]).name == source_files[piece.role]
        assert Path(meta["baseline_source_path"]).parent.name == "受電箱"
        assert meta["baseline_source_status"] == "VERIFIED"
        assert len(meta["baseline_source_sha256"]) == 64
        assert meta["baseline_fit_error"] is None
        assert meta["baseline_source_sha256"]


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_alias_never_falls_back_when_dedicated_sources_missing(
    family, tmp_path
):
    spec = replace(spec_for_mode(), model_name=family)
    missing_root = tmp_path / "missing_factory"
    output_dir = tmp_path / "output"
    with pytest.raises(FileNotFoundError, match="受電箱板件專用基準檔不存在"):
        generate_box_body_structure_parts(
            spec, output_dir, ManufacturingContext(resource_root=missing_root),
        )
    assert not output_dir.exists()
    assert not list(tmp_path.rglob("*.dxf"))


@pytest.mark.parametrize("family", ["RO", "ro", "落地盤"])
def test_registered_unimplemented_family_cannot_create_direct_final_scene(
    family, tmp_path
):
    spec = replace(spec_for_mode(), model_name=family)
    with pytest.raises(ValueError, match="CABINET_FAMILY_NOT_IMPLEMENTED: RO"):
        build_box_body_structure_render_data(
            spec, ManufacturingContext(resource_root=tmp_path),
        )
    door = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25, model_name=family,
    )
    with pytest.raises(ValueError, match="CABINET_FAMILY_NOT_IMPLEMENTED: RO"):
        build_part_render_data(door, ManufacturingContext(resource_root=tmp_path))
    assert not list(tmp_path.rglob("*.dxf"))


@pytest.mark.parametrize("family", ["RO", "ro", "落地盤"])
def test_canonical_request_resolver_rejects_unimplemented_family_before_scene(
    family
):
    request = ManufacturingResolveRequest(
        input_snapshot={"model": family}, cabinet_model=family,
        canonical_part_keys=(),
    )
    with pytest.raises(ValueError, match="CABINET_FAMILY_NOT_IMPLEMENTED: RO"):
        resolve_manufacturing_request(request)


def test_canonical_request_resolver_rejects_unimplemented_snapshot_when_no_model():
    request = ManufacturingResolveRequest(
        input_snapshot={"model": "落地盤"}, cabinet_model="",
        canonical_part_keys=(),
    )
    with pytest.raises(ValueError, match="CABINET_FAMILY_NOT_IMPLEMENTED: RO"):
        resolve_manufacturing_request(request)


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving"])
def test_canonical_resolver_rehydrates_receiving_source_selectors_for_aliases(
    family, monkeypatch
):
    from ae_engine import receiving_nfb_manufacturing_transport

    observed = []
    def trace_restore(snapshot):
        observed.append(snapshot["model"])
        return snapshot
    monkeypatch.setattr(
        receiving_nfb_manufacturing_transport,
        "restore_receiving_nfb_dto_selectors",
        trace_restore,
    )
    request = ManufacturingResolveRequest(
        input_snapshot={"model": family}, cabinet_model=family,
        canonical_part_keys=(),
    )
    with pytest.raises(ValueError, match="no parts available"):
        resolve_manufacturing_request(request)
    assert observed == [family]
