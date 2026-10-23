# -*- coding: utf-8 -*-
"""#1502: real SOURCE JOINT-X MARKING can cross an EAR footprint.

Do not erase either mark or turn CUTTING/BEND overlap into legal machining.
The production-only permission requires already independently verified
world-to-SIDE-UV physical receipts, not a mutable preview-ready flag.
"""
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon

from ae_engine.receiving_fixed_plate_side_mark_preview import (
    _check_source_conflicts,
)
from ae_engine.sheetmetal_drawing import DrawingScene


def _side_scene(start, finish, layer):
    scene=DrawingScene()
    scene.add_line(start,finish,layer=layer)
    return SimpleNamespace(
        scene=scene,
        material=Polygon(((0.,0.),(20.,0.),(20.,20.),(0.,20.))),
        fold_guides=(),
    )


def test_real_joint_x_crosses_ear_area_without_overwriting_source_marking():
    patch=Polygon(((5.,5.),(10.,5.),(10.,15.),(5.,15.)))
    source=_side_scene((4.,4.),(8.,8.),"MARKING")
    with pytest.raises(ValueError,match="EXISTING_MARKING_CONFLICT"):
        _check_source_conflicts(patch,source)
    _check_source_conflicts(
        patch,source,permit_independent_source_marking_crossing=True,
    )
    assert len(source.scene.primitives)==1


@pytest.mark.parametrize("start,finish,layer,reason",(
    ((5.,5.),(5.,15.),"MARKING","EXISTING_MARKING_CONFLICT"),
    ((4.,4.),(8.,8.),"CUTTING","EXISTING_CUTTING_CONFLICT"),
    ((4.,4.),(8.,8.),"BEND","EXISTING_BEND_CONFLICT"),
))
def test_scoped_source_marking_permission_never_approves_a_coincident_ear_or_cut(
    start,finish,layer,reason,
):
    patch=Polygon(((5.,5.),(10.,5.),(10.,15.),(5.,15.)))
    source=_side_scene(start,finish,layer)
    with pytest.raises(ValueError,match=reason):
        _check_source_conflicts(
            patch,source,permit_independent_source_marking_crossing=True,
        )
