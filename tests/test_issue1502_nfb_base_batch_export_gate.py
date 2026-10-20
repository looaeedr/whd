# -*- coding: utf-8 -*-
"""#1502: trial NFB base geometry must not escape through production batch DXF."""
from types import MappingProxyType, SimpleNamespace

import pytest

from ae_engine.manufacturing_export import (
    save_resolved_manufacturing_geometry_batch_dxf,
    save_resolved_manufacturing_geometry_dxf,
)


def _part(part_id, metadata):
    return SimpleNamespace(
        part_key=part_id,
        render_data=SimpleNamespace(metadata=metadata),
    )


def _geometry(*parts):
    return SimpleNamespace(parts=parts)


def _serializer(calls):
    def save(render, path, *, overwrite):
        calls.append(str(path))
        with open(path, "wb") as out:
            out.write(b"DXF ROUNDTRIP PLACEHOLDER")
        return str(path)
    return save


@pytest.mark.parametrize("metadata", [
    {"nfb_base_process_status": "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED",
     "nfb_base_mfg2_release_approved": False},
    MappingProxyType({
        "nfb_base_process_status": "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED",
        "nfb_base_mfg2_release_approved": True,
        "receiving_base_ear_weld_z_verified": True,
    }),
])
def test_unreleased_nfb_composite_cannot_enter_single_manufacturing_batch(tmp_path, metadata):
    calls = []
    root = tmp_path / "production"
    with pytest.raises(ValueError, match="NFB_BASE_MFG2_NOT_RELEASED_FOR_BATCH_EXPORT"):
        save_resolved_manufacturing_geometry_dxf(
            _geometry(_part("base_plate", metadata)), root,
            save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),
        )
    assert calls == []
    assert not root.exists()


def test_one_unreleased_base_rejects_entire_multi_bay_export_before_io(tmp_path):
    calls = []
    root = tmp_path / "multi-bay"
    safe = _geometry(_part("inner_door", {"nfb_trial_export_approved": True}))
    blocked = _geometry(_part("base_plate", {
        "nfb_base_process_status": "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED"
    }))
    with pytest.raises(ValueError, match="NFB_BASE_MFG2_NOT_RELEASED_FOR_BATCH_EXPORT"):
        save_resolved_manufacturing_geometry_batch_dxf(
            (("setA__bay1", safe), ("setA__bay2", blocked)), root,
            save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),
        )
    assert calls == []
    assert not root.exists()


def test_unrelated_and_unconfigured_parts_keep_their_valid_export_path(tmp_path):
    calls = []
    root = tmp_path / "unrelated"
    result = save_resolved_manufacturing_geometry_dxf(
        _geometry(
            _part("inner_door", {"nfb_trial_export_approved": True}),
            _part("base_plate", {"receiving_nfb_base_mfg2_release_approved": False}),
        ),
        root, save_part_render_data_dxf=_serializer(calls),
        box_body_physical_piece_roles=(),
    )
    assert set(result) == {"inner_door", "base_plate"}
    assert len(calls) == 2
    assert all((root / (part + ".dxf")).is_file() for part in result)


@pytest.mark.parametrize("metadata", [
    {"nfb_base_process_status": "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED",
     "stable_id": "base_plate", "nfb_base_mfg2_release_approved": True},
    MappingProxyType({
        "nfb_base_process_status": "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED",
        "stable_id": "base_plate", "nfb_base_mfg2_release_approved": True,
        "receiving_base_ear_weld_z_verified": True,
    }),
])
def test_part_only_rejects_approval_flags_without_real_scene(tmp_path, metadata):
    calls = []
    root = tmp_path / "unverified"
    with pytest.raises(ValueError, match="NFB_BASE_PART_CUTTING_EVIDENCE_MISSING"):
        save_resolved_manufacturing_geometry_dxf(
            _geometry(_part("base_plate", metadata)), root,
            save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),
            part_only=True,
        )
    assert calls == []
    assert not root.exists()



def test_unverified_real_tier_finalscene_stays_visible_but_never_exports_dxf(tmp_path):
    """#1502: 2D/3D evidence cannot accidentally become manufacturing release."""
    from dataclasses import replace

    from ae_engine.manufacturing_api import (
        save_part_render_data_dxf as save_direct,
        save_resolved_manufacturing_geometry_dxf as save_batch,
    )
    from ae_engine.receiving_nfb_layer_physical_parts import (
        expand_receiving_nfb_layer_parts,
    )
    from tests.test_receiving_two_tier_physical_base_parts import (
        _two_tier, _source,
    )

    snapshot = _two_tier()
    tiers = expand_receiving_nfb_layer_parts(snapshot, (_source(snapshot),))
    assert len(tiers) == 2
    for tier in tiers:
        assert tier.part_key.startswith("base_plate:nfb_layer:")
        assert tier.render_data.material.area > 0
        assert tier.render_data.metadata["manufacturing_ready"] is False
        output = tmp_path / (tier.part_key.replace(":", "_") + ".dxf")
        with pytest.raises(ValueError, match="RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"):
            save_direct(tier.render_data, output)
        assert not output.exists()

        # A forged ready flag or marker removal is not a manufacturing receipt.
        forged = replace(tier.render_data, metadata={
            **tier.render_data.metadata, "manufacturing_ready": True,
            "nfb_layer_manufacturing_status": "RELEASED",
        })
        with pytest.raises(ValueError, match="RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"):
            save_direct(forged, output)
        assert not output.exists()

    # The old generic generate_part BasePlate branch must not bypass the
    # shared FinalScene export guard either.
    from ae_engine.manufacturing_api import generate_part
    from ae_engine.receiving_nfb_layer_physical_parts import (
        source_receiving_nfb_tier_base_specs,
    )
    for spec in source_receiving_nfb_tier_base_specs(snapshot).values():
        path = tmp_path / (spec.physical_id.replace(":", "_") + "_generic.dxf")
        with pytest.raises(ValueError, match="RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"):
            generate_part(spec, path)
        assert not path.exists()

    # The preflight must fail atomically, before creating a destination dir.
    destination = tmp_path / "batch"
    with pytest.raises(ValueError, match="RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"):
        save_batch(SimpleNamespace(parts=tiers), destination)
    assert not destination.exists()


def test_tier_output_id_cannot_be_renamed_to_escape_preflight(tmp_path):
    """An exporter must inspect the physical scene identity, not just filename."""
    from ae_engine.manufacturing_export import save_resolved_manufacturing_geometry_dxf

    calls = []
    source = _part("export_alias", {
        "stable_id": "base_plate:nfb_layer:0",
        "nfb_layer_manufacturing_status": "NFB_TIER_BASE_EAR_AND_HOLES_UNVERIFIED",
        "manufacturing_ready": True,
    })
    root = tmp_path / "renamed"
    with pytest.raises(ValueError, match="RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"):
        save_resolved_manufacturing_geometry_dxf(
            _geometry(source), root,
            save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),
        )
    assert calls == []
    assert not root.exists()
