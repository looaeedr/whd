from pathlib import Path

import ezdxf
import pytest

from ae_engine.contracts import (
    BasePlatePartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    IndicatorBoxPartSpec,
    ManufacturingContext,
)
from ae_engine.manufacturing_api import generate_part
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, FourCornerTypePolicy


def _uniform(type_id, fw=25.0):
    selection = CornerTypeSelection(type_id)
    return FourCornerTypePolicy(selection, selection, selection, selection, fw=fw)


def _vault_endcap_shape():
    c03 = CornerTypeSelection(CornerTypeId.C03)
    c04 = CornerTypeSelection(CornerTypeId.C04)
    return FourCornerTypePolicy(c03, c03, c04, c04, fw=25.0)


@pytest.mark.parametrize(
    ("name", "spec", "expected_exporter", "expected_used_baseline"),
    [
        (
            "door",
            DoorPartSpec(
                500, 600, 2, 25, gap_w=3.5, gap_h=3.5,
                fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
                corner_policy=_uniform(CornerTypeId.C02),
            ),
            "export_unknown_door_dxf",
            False,
        ),
        (
            "head",
            EndCapPartSpec(
                500, 150, 2, 25, height=600,
                fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
                corner_policy=_vault_endcap_shape(),
            ),
            "final_scene_end_cap_export",
            False,
        ),
        (
            "tail",
            EndCapPartSpec(
                500, 150, 2, 25, height=600, is_tail=True,
                fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
                corner_policy=_vault_endcap_shape(),
            ),
            "final_scene_end_cap_export",
            False,
        ),
        (
            "base",
            BasePlatePartSpec(500, 600, 2, 55, 55, 55, 55, 15, corner_policy=_uniform(CornerTypeId.C01, 0.0)),
            "export_unknown_base_plate_dxf",
            False,
        ),
        (
            "indicator_box",
            IndicatorBoxPartSpec((2,), 2, corner_policy=_uniform(CornerTypeId.C02, 0.0)),
            "export_stretched_indicator_box_dxf",
            True,
        ),
    ],
)
def test_unknown_corner_specs_export_through_headless_api_and_round_trip(
    tmp_path: Path, name, spec, expected_exporter, expected_used_baseline
):
    path = tmp_path / f"{name}.dxf"
    result = generate_part(spec, path, ManufacturingContext())
    assert result.exporter_name == expected_exporter
    assert result.used_baseline is expected_used_baseline
    doc = ezdxf.readfile(path)
    assert any(entity.dxf.layer == "CUTTING" for entity in doc.modelspace())
