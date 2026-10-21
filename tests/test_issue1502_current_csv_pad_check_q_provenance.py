# -*- coding: utf-8 -*-
"""#1502 current CSV CHECK/Q accepts only true source-verified PAD square cuts.

The actual selected Flat Base can contain common PAD locator squares in
addition to its original outer+four EAR contours and V5 numeric screw holes.
"""
from dataclasses import replace

import pytest

from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
from ae_engine.receiving_nfb_committed_final_scene import (
    _submitted_csv_holes, _existing_source_specs,
    _without_derived_csv_door_features,
)
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_live_base_preview import (
    preview_v5_on_existing_receiving_base,
)
from ae_engine.receiving_nfb_v5_check_q_preview import (
    CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
)
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from tests.test_issue1502_current_csv_multi_bay_once import _multi


def _current_flat_trial():
    raw = _multi()
    snap = project_receiving_bay_legacy_aliases(
        raw, set_index=0, bay_index=0,
    )
    inner_id, holes = _submitted_csv_holes(snap)
    door = trial_configured_nfb_v5_inner_door_render_data(
        _without_derived_csv_door_features(snap, inner_id),
        inner_id, holes=holes,
    )
    specs = _existing_source_specs(snap, holes)
    assert set(specs) == {0}
    spec = specs[0]
    assert spec.receiving_bend_pattern == "LEFT_FLAT_SIDE"
    trial = preview_v5_on_existing_receiving_base(
        snap, inner_id, door=door, configured_holes=holes,
        base_spec=spec, tier_slot_index=None,
        existing_render_data=build_part_render_data(spec),
    )
    demand = CsvV5BaseCheckDemand(
        "real-current-bay", trial, 1,
        ManufacturingParameters("UNSPECIFIED_SHEET", float(snap["t"]), "CUTTING_DXF"),
    )
    return demand


def test_csv_v5_check_q_recounts_actual_current_pad_squares_not_stale_five():
    demand = _current_flat_trial()
    meta = demand.part.render_data.metadata
    assert tuple(meta["nfb_v5_pad_square_owners"])
    assert tuple(x[1] for x in meta["nfb_v5_pad_square_owners"]) == (4,)
    native = tuple(p for p in demand.part.render_data.scene.primitives
                   if isinstance(p, PolylinePrimitive) and p.closed
                   and p.layer == "CUTTING")
    assert len(native) == 5 + sum(x[1] for x in meta["nfb_v5_pad_square_owners"])
    source = demand.part.render_data
    result = check_csv_v5_base_part_only_groups((demand,))
    assert result.physical_part_ids == (demand.part.part_id,)
    assert result.manufacturing_ready is False
    assert source == demand.part.render_data


def test_csv_v5_check_q_rejects_forged_pad_owner_or_duplicate_cutting():
    demand = _current_flat_trial()
    source = demand.part.render_data
    forged = replace(source, metadata={
        **source.metadata, "nfb_v5_pad_square_owners": (),
    })
    with pytest.raises(ValueError, match="PAD 方孔來源所有權"):
        check_csv_v5_base_part_only_groups((
            replace(demand, part=replace(demand.part, render_data=forged)),
        ))

    # Repeating one genuine square is not a fifth certified locator. A
    # metadata count and material area alone cannot authorize extra CUTTING.
    square = tuple(source.scene.primitives)[-1]
    assert isinstance(square, PolylinePrimitive) and square.closed
    altered = replace(source, scene=DrawingScene(
        [*source.scene.primitives, square],
    ))
    with pytest.raises(ValueError, match="PAD_BASE_FOUR_LOCATOR_SQUARES_NOT_REAL_CUTTING"):
        check_csv_v5_base_part_only_groups((
            replace(demand, part=replace(demand.part, render_data=altered)),
        ))
