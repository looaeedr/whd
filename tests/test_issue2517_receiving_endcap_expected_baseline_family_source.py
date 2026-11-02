"""#2517: WHD Engine, not CADSplit, selects the Receiving EndCap source DXF.

The fixed-hole source is the certified Vault *feature* file.  Receiving
material/Corner geometry always stays on its own 2T Family implementation.
"""
from pathlib import Path

import ezdxf

from ae_engine import manufacturing_api
from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
from tests.test_issue2517_receiving_p1_authoritative_fold_manufacturing import (
    _endcap, _p1_factory_snapshot,
)

REPO = Path(__file__).resolve().parents[1]


def test_receiving_head_tail_public_baseline_path_is_engine_family_source(tmp_path):
    context = ManufacturingContext(resource_root=REPO)
    shared = REPO / "基準檔" / "金庫型" / "封頭尾.dxf"
    assert shared.is_file()
    for is_tail in (False, True):
        spec = _endcap(_p1_factory_snapshot(), tail=is_tail)
        assert spec.depth_comp_t == 2.0
        assert manufacturing_api.expected_baseline_path_for(spec, context) == shared

        output = tmp_path / ("tail.dxf" if is_tail else "head.dxf")
        result = manufacturing_api.generate_part(spec, output, context)
        assert result.output_path == str(output)
        assert result.exporter_name == "final_scene_end_cap_export"
        assert result.used_baseline is True
        assert result.baseline_path == str(shared)
        assert result.expected_baseline_path == str(shared)
        reopened = ezdxf.readfile(output)
        layers = {p.dxf.layer for p in reopened.modelspace()}
        assert "CUTTING" in layers and "BEND" in layers
        expected_render = manufacturing_api.build_part_render_data(spec, context)
        assert manufacturing_api.verify_saved_part_render_data_dxf(
            expected_render, output
        ).ok


def test_missing_receiving_shared_source_is_visible_to_engine(tmp_path):
    spec = _endcap(_p1_factory_snapshot(), tail=False)
    context = ManufacturingContext(resource_root=tmp_path)
    assert manufacturing_api.expected_baseline_path_for(
        spec, context
    ) == tmp_path / "基準檔" / "金庫型" / "封頭尾.dxf"


def test_vault_endcap_keeps_its_original_geometry_baseline_contract(tmp_path):
    ctx = ManufacturingContext(resource_root=tmp_path)
    spec = EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=25.0,
        model_name="金庫型",
    )
    assert manufacturing_api.expected_baseline_path_for(
        spec, ctx
    ) == tmp_path / "基準檔" / "金庫型" / "封頭尾.dxf"
