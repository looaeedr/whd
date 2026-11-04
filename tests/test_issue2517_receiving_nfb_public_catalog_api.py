# -*- coding: utf-8 -*-
"""#2517: GUI and CADSplit share the read-only WHD NFB V5 model catalog.

The existing per-brand numeric CSV is authoritative. This public lookup
must never transform a selectable model into manufacturing authorization.
"""
import csv
from dataclasses import FrozenInstanceError

import pytest

from ae_engine import (
    manufacturing_api, list_receiving_nfb_model_refs,
    resolve_receiving_nfb_model_spec,
)
from ae_engine import receiving_nfb_numeric_catalog as numeric_catalog


def test_public_nfb_list_uses_exact_brand_qualified_v5_identities():
    assert list_receiving_nfb_model_refs is manufacturing_api.list_receiving_nfb_model_refs
    assert resolve_receiving_nfb_model_spec is manufacturing_api.resolve_receiving_nfb_model_spec
    assert "nfbv5:士林:2P125SN" in list_receiving_nfb_model_refs("士林")
    assert "nfbv5:東元:2P125SN" in list_receiving_nfb_model_refs("東元")
    assert "nfbv5:伍菱:2P125SN" in list_receiving_nfb_model_refs("伍菱")
    for brand, expected_count in (("士林", 12), ("東元", 9), ("伍菱", 12)):
        choices = list_receiving_nfb_model_refs(brand)
        assert len(choices) == expected_count == len(set(choices))
        assert all(ref.startswith(f"nfbv5:{brand}:") for ref in choices)
        assert all(not ref.casefold().endswith(".dxf") for ref in choices)
    assert list_receiving_nfb_model_refs("三菱") == ()


def test_public_spec_reuses_csv_dimensions_but_never_confers_approval():
    spec = resolve_receiving_nfb_model_spec("士林", "nfbv5:士林:2P125SN")
    assert (spec.brand, spec.model) == ("士林", "2P125SN")
    assert (spec.width_mm, spec.height_mm, spec.depth_mm) == (75, 130, 68)
    assert spec.opening_mm == (28, 58)
    assert spec.screw_pitch_mm == (25, 111)
    assert spec.screw_diameter_mm == 3.2
    assert spec.status == "NFB_V5_NUMERIC_SOURCE_UNVERIFIED"
    assert spec.dimensionally_complete is True
    with pytest.raises(FrozenInstanceError):
        spec.width_mm = 999

    incomplete = resolve_receiving_nfb_model_spec("士林", "nfbv5:士林:1PBH")
    assert incomplete.opening_mm is None
    assert incomplete.depth_mm is None
    assert not incomplete.dimensionally_complete
    assert "NFB深_mm" in incomplete.missing_fields


@pytest.mark.parametrize("brand,ref", (
    ("士林", "nfbv5:東元:2P125SN"),
    ("東元", "nfbv5:士林:2P125SN"),
    ("士林", "nfbv5:士林:NONEXISTENT"),
    ("士林", "BH_25X95.dxf"),
    ("三菱", "nfbv5:三菱:2P125SN"),
    ("士林", "../escape.dxf"),
    ("士林", ""),
))
def test_public_nfb_lookup_rejects_wrong_brand_legacy_or_unknown_ref(brand, ref):
    assert resolve_receiving_nfb_model_spec(brand, ref) is None


def _write_numeric_csv(tmp_path, model, width):
    path = (
        tmp_path / "基準檔" / "開孔" / "NFB" / "數值規格"
        / "士林" / "NFB數值規格.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(numeric_catalog.HEADER)
        writer.writerow((model, width, 130, 68, "28X58",
                         "25X111", 3.2, "", ""))
    return path


def test_public_nfb_catalog_tracks_live_csv_and_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(numeric_catalog, "PROJECT_ROOT", tmp_path)
    path = _write_numeric_csv(tmp_path, "MODEL-A", 75)
    assert list_receiving_nfb_model_refs("士林") == ("nfbv5:士林:MODEL-A",)
    assert resolve_receiving_nfb_model_spec(
        "士林", "nfbv5:士林:MODEL-A",
    ).width_mm == 75

    _write_numeric_csv(tmp_path, "MODEL-B", 82)
    assert list_receiving_nfb_model_refs("士林") == ("nfbv5:士林:MODEL-B",)
    assert resolve_receiving_nfb_model_spec("士林", "nfbv5:士林:MODEL-A") is None
    assert resolve_receiving_nfb_model_spec(
        "士林", "nfbv5:士林:MODEL-B",
    ).width_mm == 82

    path.write_text("bad,columns\nMODEL-C,1\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="欄位"):
        list_receiving_nfb_model_refs("士林")
    with pytest.raises(ValueError, match="欄位"):
        resolve_receiving_nfb_model_spec("士林", "nfbv5:士林:MODEL-B")
