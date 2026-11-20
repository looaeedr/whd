"""#3317: existing corner GUI exposes a truthful V-miter CHECK source, not manufacture."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import CornerTypeId, Vec2
from gui_modules.parts.panels.assembly_corner import v_miter_check_source_summary


def _real_trial_source():
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    inputs = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=90,
        relief_mode="RELIEF_HOLE", relief_t_factor=1.5,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **inputs,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    outline = PolylinePrimitive(
        (Vec2(-100, a.y), Vec2(b.x, a.y),
         Vec2(b.x, 0), Vec2(30, 10),
         Vec2(30, 100), Vec2(-100, 100)),
        "CUTTING", closed=True,
    )
    return DrawingScene([outline, first, second]), first, second, inputs


def test_empty_gui_check_entry_never_invents_fold_angle_or_material():
    message = v_miter_check_source_summary({})
    assert "沒有已保存" in message
    assert "不會代填角度" in message
    assert "正式 CUTTING" in message


def test_real_saved_check_snapshot_is_read_only_and_is_not_manufacture():
    scene, first, second, inputs = _real_trial_source()
    saved = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **inputs,
    )
    source = {"v_miter_trial_preview": saved}
    before = repr(source)
    message = v_miter_check_source_summary(source)
    assert "90°" in message
    assert "20 / 30 mm" in message
    assert "圓形避裂孔" in message
    assert "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED" in message
    assert "未綁定目前選取的角落" in message
    assert repr(source) == before
    assert list(scene.primitives) == [scene.primitives[0], first, second]


def test_broken_saved_check_source_is_rejected_by_engine_not_hidden():
    with pytest.raises(ValueError):
        v_miter_check_source_summary({
            "v_miter_trial_preview": {
                "contract": "V_MITER_RELIEF_TRIAL_SOURCE_V1",
                "manufacturing_status": "CERTIFIED",
            },
        })


def test_v_miter_check_button_is_not_an_editable_manufacturing_corner_type():
    editable = manufacturing_api.project_operator_corner_selection_catalog(
        "自訂", ["自訂"],
    )
    assert all(type_id != "V_MITER" for type_id, _ in editable.labels)
    assert len(editable.labels) == 4
    assert "V_MITER" not in {item.value for item in CornerTypeId}
    source = Path(__file__).parents[1].joinpath(
        "gui_modules", "parts", "panels", "assembly_corner.py",
    ).read_text(encoding="utf-8")
    selector = source.split("def _build_corner_type_selector(", 1)[1].split(
        "def _build_corner_parameter_controls(", 1
    )[0]
    assert 'command=host.show_v_miter_check_source' in selector
    assert 'host.manual_corner_type_buttons[type_id] = rb' in selector
    check = selector.split("host.v_miter_check_source_button = tk.Button(", 1)[1]
    assert "tk.Radiobutton" not in check
    assert "set_manual_corner_type" not in check


def test_gui_check_route_only_uses_project_snapshot_and_engine_projection():
    source = Path(__file__).parents[1].joinpath("gui.py").read_text(encoding="utf-8")
    method = source.split("def show_v_miter_check_source(self):", 1)[1].split(
        "def create_corner_type_panel(", 1,
    )[0]
    assert "self._make_original_fold_designer_snapshot()" in method
    assert "_v_miter_check_source_summary_impl(snapshot)" in method
    assert "operator_apply_manual_corner_selection" not in method
    assert "save_part_render_data_dxf" not in method
