"""GUI must not manufacture selected physical DXF: Engine owns this route."""
import inspect
from pathlib import Path

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    ResolvedManufacturingGeometry, ResolvedManufacturingPart,
)
from gui_modules.project import export_actions


def test_headless_engine_exports_selected_resolved_part_via_public_api(monkeypatch, tmp_path):
    calls = []
    path = tmp_path / "physical_door.dxf"

    def fake_save(geometry, output_dir, *, overwrite):
        calls.append((geometry, output_dir, overwrite))
        return {"door": str(path)}

    monkeypatch.setattr(
        manufacturing_api, "save_resolved_manufacturing_geometry_dxf",
        fake_save,
    )
    original = object()
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(part_key="door", render_data=original),
        ResolvedManufacturingPart(part_key="box_body", render_data=object()),
    ))
    written = manufacturing_api.save_selected_resolved_manufacturing_dxf(
        {"model": "金庫型"}, geometry, {"door": True}, str(tmp_path),
    )
    assert written == {"door": str(path)}
    assert len(calls) == 1
    selected, target, overwrite = calls[0]
    assert target == str(tmp_path) and overwrite is True
    assert len(selected.parts) == 1
    assert selected.parts[0].part_key == "door"
    assert selected.parts[0].render_data is original


def test_empty_selected_part_never_writes_dxf(monkeypatch, tmp_path):
    def must_not_save(*_args, **_kwargs):
        raise AssertionError("Engine must not export an unselected part")

    monkeypatch.setattr(
        manufacturing_api, "save_resolved_manufacturing_geometry_dxf",
        must_not_save,
    )
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(part_key="box_body", render_data=object()),
    ))
    assert manufacturing_api.save_selected_resolved_manufacturing_dxf(
        {"model": "金庫型"}, geometry, {"door": True}, str(tmp_path),
    ) == {}


def test_gui_selected_export_only_passes_resolved_source_and_intent_to_engine():
    gui_source = inspect.getsource(export_actions._export_selected_resolved_parts)
    engine_source = inspect.getsource(manufacturing_api.save_selected_resolved_manufacturing_dxf)
    assert "save_selected_resolved_manufacturing_dxf(" in gui_source
    for forbidden in (
        "save_verified_receiving_formed_fixing_plate_bundle(",
        "with_verified_receiving_ear_side_markings(",
        "save_verified_receiving_csv_selected_sheets(",
        "verify_saved_part_render_data_dxf(",
        "_readback_marking_lines(",
    ):
        assert forbidden not in gui_source
        assert forbidden in engine_source

def test_engine_policy_is_source_owned_and_gui_only_uses_classification_api():
    engine_source = inspect.getsource(
        manufacturing_api.selected_export_manufacturing_policy
    )
    gui_source = inspect.getsource(export_actions._export_selected_resolved_parts)
    assert 'nfb_config_submitted' in engine_source
    assert 'selected_export_manufacturing_policy(' in gui_source
    assert 'from ae_engine.receiving_nfb_committed_final_scene import' not in gui_source
    assert manufacturing_api.selected_export_manufacturing_policy(
        {"model": "金庫型", "nfb_config_submitted": True},
        {"box_body": True},
    ) == (False, ())
