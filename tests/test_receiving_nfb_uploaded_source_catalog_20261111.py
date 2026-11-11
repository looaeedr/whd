# -*- coding: utf-8 -*-
"""2026-11-11 NFB source ingestion: model identity is not manufacturing proof."""
import csv
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_model_identity import (
    numeric_model_ref, parse_numeric_model_ref,
)
from ae_engine.receiving_nfb_numeric_catalog import (
    BRANDS, NUMERIC_ONLY_UNVERIFIED, brand_csv_path,
    brand_max_depth_mm, model_spec, read_numeric_specs,
)
from ae_engine.receiving_nfb_numeric_panel_projection import (
    NfbPanelDatum, project_nfb_v5_to_panel,
)


def _source_records(filename):
    root = Path(__file__).resolve().parents[1]
    path = root / "基準檔" / "開孔" / "NFB" / "型錄來源" / filename
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return tuple(csv.DictReader(source))


def test_new_source_rows_keep_original_wuling_records_and_exact_pole_identity():
    rows = read_numeric_specs("伍菱")
    assert len(rows) == 68
    new_rows = _source_records("伍菱_NF外型觀察.csv")
    assert len(new_rows) == 56
    assert {r["型號"] for r in new_rows} <= {r.model for r in rows}
    two = model_spec("伍菱", "NF400-WE 2P")
    three = model_spec("伍菱", "NF400-WE 3P")
    assert (two.width_mm, two.height_mm) == (140, 257)
    assert (three.width_mm, three.height_mm) == (140, 257)
    assert two.model != three.model
    for spec in rows[12:]:
        assert spec.opening_mm is None
        assert spec.screw_pitch_mm is None
        assert spec.screw_diameter_mm is None
        assert spec.depth_mm is None
        assert not spec.dimensionally_complete
        assert spec.status == NUMERIC_ONLY_UNVERIFIED
    assert model_spec("伍菱", "NF400-WE") is None
    assert numeric_model_ref("伍菱", "NF400-WE 2P") == "nfbv5:伍菱:NF400-WE 2P"


def test_shunshan_is_explicit_source_only_brand_with_no_guessed_geometry():
    assert "順山" in BRANDS
    rows = read_numeric_specs("順山")
    assert len(rows) == 44
    assert len({r.model for r in rows}) == 17
    evidence = _source_records("順山_DWG來源索引.csv")
    assert {r.model for r in rows[:17]} <= {r["型號_依檔名"] for r in evidence}
    assert len({r["原始DWG檔名"] for r in evidence}) == 11
    for spec in rows[:17]:
        assert not spec.dimensionally_complete
        assert spec.width_mm is spec.height_mm is spec.depth_mm is None
        assert spec.opening_mm is spec.screw_pitch_mm is None
        assert spec.screw_diameter_mm is None
        assert spec.status == NUMERIC_ONLY_UNVERIFIED
    for spec in rows[17:]:
        assert spec.width_mm is not None and spec.height_mm is not None
        assert spec.depth_mm is None and spec.opening_mm is None
        assert spec.screw_pitch_mm is None and spec.screw_diameter_mm is None
        assert not spec.dimensionally_complete
    assert numeric_model_ref("順山", "NF50-HS") == "nfbv5:順山:NF50-HS"
    assert parse_numeric_model_ref("nfbv5:順山:NF50-HS") == ("順山", "NF50-HS")
    refs = manufacturing_api.list_receiving_nfb_model_refs("順山")
    assert len(refs) == 44 and "nfbv5:順山:NF50-HS" in refs
    assert manufacturing_api.project_receiving_nfb_v5_model_catalog_snapshot(
        "順山"
    ).manufacturing_ready is False
    with pytest.raises(ValueError, match="RECEIVING_EAR_BRAND_MAX_DEPTH_MISSING"):
        brand_max_depth_mm("順山")


@pytest.mark.parametrize("brand,model", (
    ("順山", "NF50-HS"),
    ("順山", "NF1600-SS"),
    ("伍菱", "NF400-WE 2P"),
))
def test_new_catalogue_entries_cannot_become_cutting_from_filename_or_outline(
    brand, model,
):
    datum = NfbPanelDatum(
        part_id="receiving:inner-door:1",
        role="inner-door",
        uv_centre_mm=(200, 200),
        uv_axis_x=(1, 0), uv_axis_y=(0, 1),
    )
    with pytest.raises(ValueError, match="開孔尺寸缺失"):
        project_nfb_v5_to_panel(brand, model, datum, feature="both")


def test_shunshan_remains_separate_from_legacy_dxf_index_and_other_breakers():
    from ae_engine.receiving_switch_model_catalog import model_filenames
    assert model_filenames("順山") == ()
    assert brand_csv_path("順山").is_file()
    assert all("ELB" not in row.model and "ELCB" not in row.model
               for row in read_numeric_specs("順山"))
