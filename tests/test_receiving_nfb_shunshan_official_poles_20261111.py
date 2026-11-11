# -*- coding: utf-8 -*-
"""Directly sourced Shunshan 2024.02 catalog: pole-specific a/b cannot imply cuts."""
import csv
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_numeric_panel_projection import (
    NfbPanelDatum, project_nfb_v5_to_panel,
)

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "基準檔" / "開孔" / "NFB" / "型錄來源" / "順山_NF原廠型錄外型尺寸_202402.csv"


def test_all_27_official_pole_variants_retained_in_engine_exactly():
    with SHEET.open("r", encoding="utf-8-sig", newline="") as fp:
        records = tuple(csv.DictReader(fp))
    assert len(records) == 27
    names = {row["型號_含極數"] for row in records}
    assert len(names) == 27
    choices = set(api.list_receiving_nfb_model_refs("順山"))
    assert len(choices) == 44
    for row in records:
        model = row["型號_含極數"]
        spec = model_spec("順山", model)
        assert spec is not None
        assert spec.model == model
        assert spec.width_mm == float(row["a_寬_mm"])
        assert spec.height_mm == float(row["b_高_mm"])
        assert spec.depth_mm is None
        assert spec.opening_mm is None
        assert spec.screw_pitch_mm is None
        assert spec.screw_diameter_mm is None
        assert not spec.dimensionally_complete
        assert spec.status == "NFB_V5_NUMERIC_SOURCE_UNVERIFIED"
        assert f"nfbv5:順山:{model}" in choices
        assert row["原廠型錄版本"] == "2024.02"
        assert row["原廠型錄印刷頁次"] in ("03", "04")
        assert row["原廠PDF來源URL"] == (
            "https://www.cleswitch.com.tw/uploads/files/1713249984.pdf"
        )


@pytest.mark.parametrize("model,width,height", (
    ("NF50-HS 2P", 51, 132),
    ("NF50-HS 3P", 76, 132),
    ("NF100-HS 2P", 61, 156.5),
    ("NF100-HS 3P", 91, 156.5),
    ("NF125-SW 2P", 60.5, 131),
    ("NF125-SW 3P", 90, 131),
    ("NF250-HS 3P", 106.5, 167.5),
    ("NF400-HS 3P", 140.5, 258.5),
    ("NF400-KS 4P", 184.5, 258.5),
    ("NF800-SS 4P", 280.5, 276),
    ("NF1600-SS 3P", 210.5, 407),
    ("NF1600-SS 4P", 280.5, 407),
))
def test_outer_dimensions_are_independent_by_pole(model, width, height):
    spec = api.resolve_receiving_nfb_model_spec("順山", f"nfbv5:順山:{model}")
    assert (spec.width_mm, spec.height_mm) == (width, height)


def test_pdf_raw_c_and_ca_cannot_be_silently_mapped_to_engine_depth():
    with SHEET.open("r", encoding="utf-8-sig", newline="") as fp:
        raw = {r["型號_含極數"]: r for r in csv.DictReader(fp)}
    row = raw["NF400-HS 3P"]
    assert (float(row["c_側視_mm"]), float(row["ca_側視_mm"])) == (104, 153.5)
    # c and ca differ. The engineered depth datum has not been certified.
    assert model_spec("順山", "NF400-HS 3P").depth_mm is None


@pytest.mark.parametrize("model", ("NF50-HS 2P", "NF50-HS 3P", "NF400-KS 4P"))
def test_new_outer_dimensions_do_not_authorize_cutting(model):
    datum = NfbPanelDatum(
        part_id="real:receiving:inner:door", role="inner-door",
        uv_centre_mm=(100, 100), uv_axis_x=(1, 0), uv_axis_y=(0, 1),
    )
    with pytest.raises(ValueError, match="開孔尺寸缺失"):
        project_nfb_v5_to_panel("順山", model, datum, feature="both")


def test_unverified_dwgs_and_non_identical_model_names_do_not_automap():
    assert model_spec("順山", "NF400HS").width_mm is None
    assert model_spec("順山", "NF800-CP").height_mm is None
    assert model_spec("順山", "NF100-HP").height_mm is None
    assert model_spec("順山", "NF400-HS").width_mm is None  # needs 3P identity
