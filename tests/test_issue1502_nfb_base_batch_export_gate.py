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
