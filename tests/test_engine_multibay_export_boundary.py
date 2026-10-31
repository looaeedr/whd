"""Manufacturing export ownership: Engine must not depend on GUI."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import receiving_bay_assembly_offsets
from tests.test_issue1502_current_csv_multi_bay_once import _multi

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("part_key,intention", [
    ("box_body:left_side", "box_body"), ("box_body:back", "box_body"),
    ("head", "head"), ("tail", "tail"), ("inner_door:7:panel", "door"),
    ("base_plate:nfb_layer:2", "base_plate"),
    ("indicator_box", "indicator_box"), ("indicator_door", "indicator_door"),
    ("custom:1", None),
])
def test_physical_export_selection_identity_is_engine_owned(part_key, intention):
    assert manufacturing_api.resolved_export_intention_key(part_key) == intention


def test_engine_removes_bay_world_anchor_but_keeps_actual_source_part():
    layout = _multi()["receiving_layout"]
    anchor = receiving_bay_assembly_offsets(layout, set_index=0)[1]
    original = object()
    part = SimpleNamespace(
        part_key="box_body", render_data=original,
        x_profile=(), y_profile=(), placement="back",
        offset=tuple(a + d for a, d in zip(anchor, (10.0, 5.0, 2.0))),
    )
    geometry = manufacturing_api.resolve_receiving_bay_local_export_geometry(
        (part,), layout, set_index=0, bay_index=1,
    )
    assert len(geometry.parts) == 1
    assert geometry.parts[0].render_data is original
    assert geometry.parts[0].offset == pytest.approx((10.0, 5.0, 2.0))


def test_engine_rejects_standalone_preview_as_multibay_source():
    layout = _multi()["receiving_layout"]
    part = SimpleNamespace(
        part_key="box_body", render_data=object(),
        x_profile=(), y_profile=(), placement="standalone",
        offset=(0.0, 0.0, 0.0),
    )
    with pytest.raises(ValueError, match="多連出圖禁止"):
        manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (part,), layout, set_index=0, bay_index=1,
        )


def test_multibay_manufacturing_never_reverse_imports_gui():
    engine = (ROOT / "ae_engine" / "receiving_csv_multibay_manufacturing.py").read_text(encoding="utf-8")
    gui = (ROOT / "gui_modules" / "project" / "export_actions.py").read_text(encoding="utf-8")
    assert "from gui_modules.project.export_actions import" not in engine
    assert "receiving_bay_assembly_offsets(" not in gui
    assert "ResolvedManufacturingPart(" not in gui
    assert "resolve_receiving_bay_local_export_geometry(" in gui
