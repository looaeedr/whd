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
