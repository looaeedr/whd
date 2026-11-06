# -*- coding: utf-8 -*-
"""#2517: one headless manufacturing Request resolves current Receiving NFB DXFs.

No Tk, CADSplit geometry construction, stale 3D cache, fabricated world X or
source-only CLI. The original Engine resolver owns every physical FinalScene.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types.policy import derive_inner_door_panels
from tests.test_issue1502_current_csv_original_pair_dxf import _current
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _current_two_tiers,
)
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_receiving_two_tier_physical_base_parts import _source


def _original_request(snapshot, *, tiers):
    panel = next(
        part for part in derive_inner_door_panels(snapshot)
        if str(part.cell_key).split(":")[-1] == "0"
    )
    # These are ORIGINAL physical blanks, not already CSV-cut scenes.
    original_door = api.build_inner_door_panel_render_data(panel)
    original_base = _source(snapshot) if tiers == 2 else _make(snapshot)
    keys = (panel.stable_id, "base_plate")
    request = api.ManufacturingResolveRequest(
        input_snapshot=deepcopy(snapshot),
        settings={"t": snapshot["t"]},
        canonical_part_keys=keys,
        parts=(
            api.ManufacturingPartInput(
                part_key=panel.stable_id,
                render_data=original_door,
            ),
            api.ManufacturingPartInput(
                part_key="base_plate",
                render_data=original_base.render_data,
                x_profile=original_base.x_profile,
                y_profile=original_base.y_profile,
            ),
        ),
        cabinet_model="受電箱",
    )
    return request


@pytest.mark.parametrize("tiers", (1, 2))
def test_real_original_request_resolves_and_reopens_every_physical_nfb_dxf(
    tiers, tmp_path,
):
    snapshot = _current() if tiers == 1 else _current_two_tiers()
    request = _original_request(snapshot, tiers=tiers)
    import ae_engine

    assert (ae_engine.export_current_csv_nfb_pair_from_request
            is api.export_current_csv_nfb_pair_from_request)
    # This is the ONLY submitted source. No caller assembly_parts are passed.
    resolved = api.resolve_manufacturing_request(request)
    expected = (
        {part.part_key for part in resolved.geometry.parts}
        & {part.part_key for part in resolved.geometry.parts
           if part.part_key.startswith("base_plate")}
    )
    assert len(expected) == tiers
    result = api.export_current_csv_nfb_pair_from_request(
        request, output_directory=tmp_path,
    )
    paths = (result.inner_door_path,) + (
        result.base_plate_paths if tiers == 2 else (result.base_plate_path,)
    )
    assert len(paths) == tiers + 1
    assert set(map(Path, paths)) == set(tmp_path.glob("*.dxf"))
    for path in paths:
        assert ezdxf.readfile(path).audit().errors == []
    assert len(result.source_hole_ids) >= tiers


@pytest.mark.parametrize("tiers", (1, 2))
def test_headless_request_missing_real_base_fails_without_partial_files(
    tiers, tmp_path,
):
    snapshot = _current() if tiers == 1 else _current_two_tiers()
    request = _original_request(snapshot, tiers=tiers)
    from dataclasses import replace
    without_base = replace(
        request,
        canonical_part_keys=(request.parts[0].part_key,),
        parts=(request.parts[0],),
    )
    with pytest.raises(ValueError):
        api.export_current_csv_nfb_pair_from_request(
            without_base, output_directory=tmp_path,
        )
    assert not list(tmp_path.glob("*.dxf"))


def test_unsubmitted_or_wrong_family_cannot_be_promoted_to_nfb_manufacture(
    tmp_path,
):
    snapshot = _current()
    request = _original_request(snapshot, tiers=1)
    with pytest.raises(TypeError, match="CSV_PAIR_MANUFACTURING_REQUEST_REQUIRED"):
        api.export_current_csv_nfb_pair_from_request(
            snapshot, output_directory=tmp_path,
        )
    # A caller may not forge a valid physical ManufacturingResolveRequest
    # but remove the committed source: no implicit CSV/model fallback.
    from dataclasses import replace
    missing = deepcopy(snapshot)
    missing["nfb_config_submitted"] = False
    missing.pop("nfb_config", None)
    missing["receiving_layout"]["sets"][0]["bays"][0]["nfb_config_submitted"] = False
    missing["receiving_layout"]["sets"][0]["bays"][0].pop("nfb_config", None)
    with pytest.raises(ValueError, match="CSV_PAIR_CURRENT_SUBMITTED_SOURCE_UNAVAILABLE"):
        api.export_current_csv_nfb_pair_from_request(
            replace(request, input_snapshot=missing),
            output_directory=tmp_path,
        )
    wrong = deepcopy(snapshot)
    wrong["model"] = "金庫型"
    with pytest.raises(ValueError, match="CSV_PAIR_RECEIVING_SOURCE_REQUIRED"):
        api.export_current_csv_nfb_pair_from_request(
            replace(request, input_snapshot=wrong),
            output_directory=tmp_path,
        )
    assert not list(tmp_path.glob("*.dxf"))
