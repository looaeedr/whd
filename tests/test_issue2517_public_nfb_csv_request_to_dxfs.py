# -*- coding: utf-8 -*-
"""#2517 public, GUI-free NFB request -> canonical FinalScene -> verified DXF API.

Uses REAL existing CSV V5 manufacturing fixtures. No GUI-provided assembled
FinalScene and no CADSplit-owned manufacturing hole/placement calculation.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import export_receiving_committed_nfb_csv_from_request
from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.manufacturing_contracts import (
    ManufacturingPartInput, ManufacturingResolveRequest,
)
from tests.test_issue1502_current_csv_original_pair_dxf import _current
from tests.test_issue1502_current_csv_original_two_tier_dxf import _current_two_tiers
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_receiving_two_tier_physical_base_parts import _source


def _request(tiers=1, *, omit_base=False, snapshot=None):
    snap = snapshot if snapshot is not None else (
        _current() if tiers == 1 else _current_two_tiers()
    )
    panel = next(
        p for p in derive_inner_door_panels(snap)
        if str(p.cell_key).split(":")[-1] == "0"
    )
    door_render = api.build_inner_door_panel_render_data(panel)
    # Real original physical blank, BEFORE any NFB CSV applied to FinalScene.
    base = _make(snap) if tiers == 1 else _source(snap)
    source_parts = [
        ManufacturingPartInput(
            part_key=panel.stable_id, render_data=door_render,
        ),
    ]
    if not omit_base:
        source_parts.append(ManufacturingPartInput(
            part_key=base.part_key, render_data=base.render_data,
            x_profile=base.x_profile, y_profile=base.y_profile,
        ))
    return ManufacturingResolveRequest(
        input_snapshot=snap, settings={},
        cabinet_model="受電箱",
        canonical_part_keys=tuple(p.part_key for p in source_parts),
        parts=tuple(source_parts),
    )


@pytest.mark.parametrize("tiers", (1, 2))
def test_one_public_engine_call_resolves_and_emits_actual_csv_nfb_pair(
    tiers, tmp_path,
):
    request = _request(tiers)
    proof = api.export_receiving_committed_nfb_csv_from_request(
        request, output_directory=tmp_path,
    )
    assert export_receiving_committed_nfb_csv_from_request is (
        api.export_receiving_committed_nfb_csv_from_request
    )
    paths = (
        (proof.inner_door_path, proof.base_plate_path)
        if tiers == 1
        else (proof.inner_door_path, *proof.base_plate_paths)
    )
    assert len(paths) == tiers + 1
    assert set(Path(x) for x in paths) == set(tmp_path.glob("*.dxf"))
    for path in paths:
        assert Path(path).is_file()
        assert not ezdxf.readfile(path).audit().errors
    assert len(proof.source_hole_ids) >= tiers
    assert "PART_ONLY" in proof.scope


@pytest.mark.parametrize("tiers", (1, 2))
def test_source_only_candidate_without_confirmed_world_x_never_exports(
    tiers, tmp_path,
):
    snap = _current() if tiers == 1 else _current_two_tiers()
    for hole in snap["nfb_config"]["holes"]:
        hole["manual_x_state"] = "UNVERIFIED_BASIS"
        hole["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    with pytest.raises(ValueError, match="CONFIRMED_CSV_REQUIRED"):
        api.export_receiving_committed_nfb_csv_from_request(
            _request(tiers, snapshot=snap),
            output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("tiers", (1, 2))
def test_canonical_api_requires_original_base_source_to_make_real_pair(
    tiers, tmp_path,
):
    with pytest.raises(ValueError, match="REAL_BASE_PART_MISSING|SOURCE_BASE_PLATE_MISSING"):
        api.export_receiving_committed_nfb_csv_from_request(
            _request(tiers, omit_base=True),
            output_directory=tmp_path,
        )
    assert not list(tmp_path.iterdir())


def test_canonical_api_never_accepts_untyped_or_wrong_family_request(tmp_path):
    with pytest.raises(TypeError, match="MANUFACTURING_REQUEST_REQUIRED"):
        api.export_receiving_committed_nfb_csv_from_request(
            {"model": "受電箱"}, output_directory=tmp_path,
        )
    snap = _current()
    snap["model"] = "金庫型"
    with pytest.raises(ValueError, match="MANUFACTURING_FAMILY_INVALID"):
        api.export_receiving_committed_nfb_csv_from_request(
            ManufacturingResolveRequest(
                input_snapshot=snap, settings={}, cabinet_model="金庫型",
            ), output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []
