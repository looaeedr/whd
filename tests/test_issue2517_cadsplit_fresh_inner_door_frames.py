# -*- coding: utf-8 -*-
"""CADSplit fresh source must obtain the exact WHD GUI's three inner-door frames."""
from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import receiving


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)


def _confirmed(source=SOURCE, columns=COLUMNS):
    return manufacturing_api.build_receiving_factory_confirmed_inner_door_frames(
        source, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=columns,
    )


def test_source_frames_equal_whd_gui_family_derived_parts():
    from ae_engine.inner_door_frames import derive_all_inner_door_frames

    frames = _confirmed()
    gui_snapshot = receiving.apply_family_defaults({"model": "受電箱", **SOURCE})
    expected = derive_all_inner_door_frames(
        receiving.derive_inner_door_frame_sets(gui_snapshot)
    )
    assert frames == expected
    assert {frame.stable_id for frame in frames} == {
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
    }
    assert {frame.side: frame.span for frame in frames} == {
        "top": pytest.approx(696.0),
        "left": pytest.approx(1098.0),
        "right": pytest.approx(1098.0),
    }


def test_confirmed_source_frames_render_and_reopen_actual_dxf(tmp_path):
    frames = _confirmed()
    for frame in frames:
        render = manufacturing_api.build_inner_door_frame_render_data(frame)
        assert render.metadata["stable_id"] == frame.stable_id
        assert render.metadata["receiving_frame_source_tag"] == {
            "left": "A", "right": "B", "top": "D",
        }[frame.side]
        output = tmp_path / (frame.side + ".dxf")
        manufacturing_api.save_part_render_data_dxf(
            render, output, verify_reopen=True,
        )
        assert output.is_file()
        doc = ezdxf.readfile(output)
        assert not doc.audit().errors
        assert any(entity.dxf.layer == "CUTTING" for entity in doc.modelspace())


def test_source_dimensions_and_door_topology_cannot_be_invented():
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_FRESH_FAMILY_CONFIRMATION_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_frames(
            SOURCE, confirmed_door_layout_columns=COLUMNS,
        )
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_LAYOUT_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_frames(
            SOURCE, confirmation="fresh_family_confirmed",
        )
    with pytest.raises(ValueError):
        _confirmed({**SOURCE, "t": True})
    with pytest.raises(ValueError):
        _confirmed(SOURCE, ((800.0, (1100.0, 400.0)),))
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_FRAME_TOPOLOGY_UNRESOLVED"):
        _confirmed(SOURCE, ((800.0, (1600.0,)),))


def test_changed_confirmed_dimensions_rederive_instead_of_reusing_nominal_frame():
    source = {**SOURCE, "w": 900.0, "h": 1750.0}
    frames = _confirmed(source, ((900.0, (1200.0, 550.0)),))
    by_side = {frame.side: frame for frame in frames}
    assert by_side["top"].span == pytest.approx(796.0)
    assert by_side["left"].span == pytest.approx(1198.0)
    assert by_side["right"].span == pytest.approx(1198.0)



def test_lower_support_C_is_same_shared_divider_as_whd_gui():
    """The fourth visual member must be physical C, never a bottom_frame."""
    from ae_engine.door_dividers import derive_box_body_dividers

    shared = manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    )
    gui_snapshot = receiving.apply_family_defaults({"model": "受電箱", **SOURCE})
    (expected,) = derive_box_body_dividers(
        gui_snapshot["door_layout_columns"],
        depth=gui_snapshot["d"], thickness=gui_snapshot["t"],
        layout_scope=gui_snapshot["door_layout_scope"],
        handle_edges=gui_snapshot["door_handle_edges"],
        model_name="受電箱", frame_width=gui_snapshot["fw"],
    )
    assert shared == expected
    assert shared.axis == "HORIZONTAL"
    assert shared.adjacent_cells == ("0:0", "0:1")
    assert shared.blank_width == pytest.approx(158.0)
    assert shared.blank_height == pytest.approx(796.0)
    assert "divider" in shared.stable_id
    assert "bottom_frame" not in shared.stable_id
    assert not any(frame.side == "bottom" for frame in _confirmed())


def test_lower_shared_divider_C_renders_with_original_holes_and_reopens(tmp_path):
    shared = manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    )
    render = manufacturing_api.build_box_body_divider_render_data(shared)
    assert render.metadata["stable_id"] == shared.stable_id
    assert render.metadata["baseline_feature_model"] == "金庫型"
    assert render.metadata["baseline_divider_hole_count"] == 6
    path = tmp_path / "inner_door_lower_shared_divider_C.dxf"
    manufacturing_api.save_part_render_data_dxf(
        render, path, verify_reopen=True,
    )
    reopened = ezdxf.readfile(path)
    assert not reopened.audit().errors
    assert any(entity.dxf.layer == "CUTTING" for entity in reopened.modelspace())


def test_lower_support_C_is_sized_from_confirmed_family_grid():
    source = {**SOURCE, "w": 900.0, "h": 1750.0}
    shared = manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
        source, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=((900.0, (1200.0, 550.0)),),
    )
    assert shared.blank_height == pytest.approx(896.0)
    assert shared.blank_width == pytest.approx(158.0)


def test_lower_support_requires_real_confirmation_and_unambiguous_divider():
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_FRESH_FAMILY_CONFIRMATION_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
            SOURCE, confirmed_door_layout_columns=COLUMNS,
        )
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_LAYOUT_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
            SOURCE, confirmation="fresh_family_confirmed",
        )
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_FRAME_TOPOLOGY_UNRESOLVED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=((800.0, (1600.0,)),),
        )


def test_source_inner_panel_equals_whd_gui_and_exports_real_folded_blank(tmp_path):
    gui_snapshot = receiving.apply_family_defaults({"model": "受電箱", **SOURCE})
    expected = receiving.derive_inner_door_panels(gui_snapshot)
    panels = manufacturing_api.build_receiving_factory_confirmed_inner_door_panels(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    )
    assert panels == expected
    assert len(panels) == 1
    assert panels[0].stable_id == "inner_door:upper:panel"
    render = manufacturing_api.build_inner_door_panel_render_data(panels[0])
    assert render.metadata["inner_door_hole_feature_count"] == 0
    assert render.metadata["folds"] == (19.0, 19.0, 19.0, 19.0)
    output = tmp_path / "real_receiving_inner_door.dxf"
    manufacturing_api.save_part_render_data_dxf(
        render, output, verify_reopen=True,
    )
    reopened = ezdxf.readfile(output)
    assert not reopened.audit().errors
    assert any(e.dxf.layer == "BEND" for e in reopened.modelspace())
    assert any(e.dxf.layer == "CUTTING" for e in reopened.modelspace())


def test_source_inner_panel_is_not_invented_from_missing_topology():
    with pytest.raises(ValueError, match="FRESH_FAMILY_CONFIRMATION_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_panels(
            SOURCE, confirmed_door_layout_columns=COLUMNS,
        )
    with pytest.raises(ValueError):
        manufacturing_api.build_receiving_factory_confirmed_inner_door_panels(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=((800, (1600,)),),
        )


def test_shared_c_reexport_requires_certified_final_cross_not_raw_rectangle(tmp_path):
    from ae_engine.contracts import ManufacturingContext
    source_parts = dict(manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    ))
    body = manufacturing_api.build_operator_part_render_data(
        source_parts["box_body"], ManufacturingContext(),
    )
    shared = manufacturing_api.build_receiving_factory_confirmed_inner_door_lower_support(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    )
    raw = manufacturing_api.build_box_body_divider_render_data(shared)
    assert "divider_assembly_relief" not in raw.metadata
    certified = manufacturing_api.resolve_receiving_factory_confirmed_lower_divider_final_scene(
        SOURCE, box_body_render_data=body,
        confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
    )
    relief = certified.metadata["divider_assembly_relief"]
    assert relief["verified"] is True
    assert relief["candidate_status"] == "CERTIFIED_REGISTRY_VERIFIED"
    assert certified.metadata["divider_endcap_shared_6p4_datum"]
    assert certified.metadata["stable_id"] == shared.stable_id
    assert certified.material.area < raw.material.area
    output = tmp_path / "verified_C_cross.dxf"
    manufacturing_api.save_part_render_data_dxf(
        certified, output, verify_reopen=True,
    )
    assert not ezdxf.readfile(output).audit().errors


def test_shared_c_no_real_body_may_be_exported_as_certified():
    with pytest.raises(TypeError, match="CANONICAL_BODY_SOURCE_REQUIRED"):
        manufacturing_api.resolve_receiving_factory_confirmed_lower_divider_final_scene(
            SOURCE, box_body_render_data=None,
            confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=COLUMNS,
        )
