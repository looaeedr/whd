"""#2517 real Receiving Set/Bay Assembly world placement is Engine-only."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_bay_preview_source import (
    ReceivingBayWorldAssemblyProjection,
    project_receiving_bay_preview_assembly_members,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays,
    update_receiving_bay, receiving_bay_assembly_offsets,
)
from phase6_final_scene_contracts import AssemblyScenePart


def _layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=4,
    )


def _part(key, offset=(0.0, 0.0, 0.0), placement="box_body"):
    return SimpleNamespace(part_key=key, offset=offset, placement=placement,
                           render_data=object(), x_profile=(), y_profile=())


@pytest.mark.parametrize("bay", [0, 1, 2, 3])
def test_engine_projects_actual_joint_world_offsets_per_bay(bay):
    layout = _layout()
    before = deepcopy(layout)
    source = (_part("box_body", (5.0, -2.0, 3.0)),
              _part("custom:1", (7.0, 0.0, 0.0), "standalone"),
              _part("head", (0.0, 0.0, 0.0), "head"))
    projected = api.project_receiving_bay_preview_assembly_members(
        layout, source, set_index=0, bay_index=bay,
    )
    assert isinstance(projected, ReceivingBayWorldAssemblyProjection)
    assert projected == project_receiving_bay_preview_assembly_members(
        layout, source, set_index=0, bay_index=bay,
    )
    origin = receiving_bay_assembly_offsets(layout, set_index=0)[bay]
    assert projected.bay_offset == origin
    assert tuple(part.part_key for part, _ in projected.part_placements) == (
        "box_body", "head",
    )
    assert projected.part_placements[0][1] == tuple(a+b for a,b in zip(
        (5., -2., 3.), origin,
    ))
    assert projected.part_placements[1][1] == origin
    assert source[0].offset == (5.0, -2.0, 3.0) and layout == before
    for part, world_offset in projected.part_placements:
        view = AssemblyScenePart(
            part_key=part.part_key, render_data=part.render_data,
            x_profile=part.x_profile, y_profile=part.y_profile,
            placement=part.placement, offset=world_offset,
        )
        assert view.offset == world_offset


def test_real_nonuniform_bay_dimensions_keep_joint_alignment_from_engine():
    layout = update_receiving_bay(
        _layout(), set_index=0, bay_index=1,
        width=900, height=1700, depth=410,
    )
    origin = receiving_bay_assembly_offsets(layout, set_index=0)[1]
    projected = api.project_receiving_bay_preview_assembly_members(
        layout, (_part("box_body"),), set_index=0, bay_index=1,
    )
    assert projected.bay_offset == origin
    assert origin[0] == pytest.approx(850.)
    assert projected.part_placements[0][1] == origin


@pytest.mark.parametrize("offset", [
    (1., 2.), (1., 2., 3., 4.), (0., float("nan"), 2.),
    (0., 0., float("inf")), (True, 0., 0.), "0,0,0", None,
])
def test_invalid_part_world_offsets_fail_closed(offset):
    with pytest.raises(ValueError, match="RECEIVING_BAY_PART_WORLD_OFFSET_INVALID"):
        api.project_receiving_bay_preview_assembly_members(
            _layout(), (_part("head", offset, placement="head"),),
            set_index=0, bay_index=0,
        )


@pytest.mark.parametrize("bad", [True, -1, 4, 9])
def test_invalid_bay_identity_cannot_grant_world_assembly_offset(bad):
    with pytest.raises((ValueError, IndexError)):
        api.project_receiving_bay_preview_assembly_members(
            _layout(), (_part("head", placement="head"),),
            set_index=0, bay_index=bad,
        )


def test_untyped_part_placement_cannot_become_assembled_sheet():
    with pytest.raises(ValueError, match="PLACEMENT_MISSING"):
        api.project_receiving_bay_preview_assembly_members(
            _layout(), (_part("head", placement=None),),
            set_index=0, bay_index=1,
        )


def test_gui_preserves_finalscene_display_only_and_does_not_add_world_offsets():
    root = Path(__file__).resolve().parents[1]
    gui = (root /
        "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    body = gui.split("def receiving_bay_preview_request(", 1)[1].split(
        "def receiving_layer_preview_payload(", 1,
    )[0]
    assert "manufacturing_api.project_receiving_bay_preview_assembly_members(" in body
    assert 'for part in resolved.parts if part.placement != "standalone"' not in body
    assert "tuple(a + b for a, b in zip(part.offset, bay_offset))" not in body
    assert "offset=world_offset" in body
    engine = (root / "ae_engine/receiving_bay_preview_source.py"
    ).read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine
