# -*- coding: utf-8 -*-
"""#1901: V5 GUI uses the real #1502 Assembly tier PartSpec, not renamed copies."""
from copy import deepcopy

import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_scene_orchestration import build_part_render_data
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
    source_receiving_nfb_tier_base_specs,
)
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from gui_modules.application.receiving_nfb_v5_scene_preview import (
    preview_v5_real_receiving_base_sources,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _current_csv_tiers():
    snap = _two_tier()
    models = ("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")
    holes = (
        NfbV5ConfiguredInnerDoorHole(
            physical_hole_id=f"nfb:csv:tier:{i}",
            brand="士林", model_ref=models[i],
            world_x_mm=(-100., 100.)[i],
            layer_count=2, slot_index=i,
        ) for i in range(2)
    )
    holes = tuple(holes)
    for i, row in enumerate(snap["nfb_config"]["holes"]):
        row.update(source_brand="士林", model_filename=models[i])
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    trial = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    values = receiving_base_plate_values(snap)
    root = BasePlatePartSpec(
        width=float(snap["w"]), height=float(values["h"]),
        thickness=float(snap["t"]),
        shrink_top=float(values["base_plate_shrink_top"]),
        shrink_bottom=float(values["base_plate_shrink_bottom"]),
        shrink_left=float(values["base_plate_shrink_left"]),
        shrink_right=float(values["base_plate_shrink_right"]),
        bend=float(values["base_plate_bend"]),
        model_name="受電箱",
        receiving_bend_pattern=values["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=values["receiving_nfb_depth_pair_mm"],
        physical_id="base_plate",
    )
    return snap, holes, trial, root


def test_multi_csv_gui_receives_exact_two_real_assembly_source_variants():
    snap, holes, trial, root = _current_csv_tiers()
    specs = source_receiving_nfb_tier_base_specs(snap)
    assert set(specs) == {0, 1}
    assert [specs[i].physical_id for i in (0,1)] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert specs[0] is not specs[1] and all(
        x.physical_id != root.physical_id for x in specs.values()
    )
    assembled = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    for i, part in enumerate(assembled):
        original = build_part_render_data(specs[i])
        assert part.render_data.unfolded_topology == original.unfolded_topology
        assert part.render_data.material.equals_exact(original.material, 1e-6)
        assert part.render_data.scene.primitives == original.scene.primitives
    shown = preview_v5_real_receiving_base_sources(
        snap, "upper", door=trial, configured_holes=holes, root_base_spec=root,
    )
    assert [p.part_id for p in shown] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert [p.hole_ids for p in shown] == [
        ("nfb:csv:tier:0",), ("nfb:csv:tier:1",),
    ]
    assert all(not p.manufacturing_ready for p in shown)
    assert all(p.render_data.metadata["nfb_trial_export_approved"] is False
               for p in shown)


def test_v5_gui_cannot_invent_tier_from_unsubmitted_or_wrong_root_sheet():
    snap, holes, trial, root = _current_csv_tiers()
    invalid = deepcopy(snap)
    invalid["nfb_config_submitted"] = False
    with pytest.raises(ValueError, match="SUBMITTED_PHYSICAL_BAY"):
        preview_v5_real_receiving_base_sources(
            invalid, "upper", door=trial,
            configured_holes=holes, root_base_spec=root,
        )
    from dataclasses import replace
    with pytest.raises(ValueError, match="不同步"):
        preview_v5_real_receiving_base_sources(
            snap, "upper", door=trial, configured_holes=holes,
            root_base_spec=replace(root, physical_id="base_plate:nfb_layer:0"),
        )


def test_submitted_tier_source_stale_bay_identity_rejected_before_display():
    snap, holes, trial, root = _current_csv_tiers()
    snap["_receiving_runtime_selection"]["bay_id"] = "obsolete"
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        preview_v5_real_receiving_base_sources(
            snap, "upper", door=trial, configured_holes=holes,
            root_base_spec=root,
        )
