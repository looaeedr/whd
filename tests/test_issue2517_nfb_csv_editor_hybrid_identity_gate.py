# -*- coding: utf-8 -*-
"""#2517: native NFB source identity is a conjunction, not an either/or alias.

Two legacy committed formats are permitted: (layer, slot) or physical hole_id.
When the operator source records both, they must refer to the SAME hole.
A mixed hybrid may never borrow another slot's world X for FinalScene/DXF.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine.receiving_nfb_committed_final_scene import (
    _source_world_x_from_committed_editor_feature,
    apply_committed_csv_v5_to_canonical_parts,
)
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_issue2517_nfb_original_editor_contour_physical_source import (
    _physical_saved_editor,
)


def _world_x(snapshot, panel):
    return _source_world_x_from_committed_editor_feature(
        snapshot, panel, snapshot["nfb_config"]["holes"][0],
        brand="士林", model="2P400",
    )


def _set_first_source(snapshot, panel, features, *, hole_id, layer=0, slot=0):
    first = features[0]
    params = tuple((k, v) for k, v in first.source_params
                   if k not in ("hole_id", "layer_index", "slot_index"))
    params += (("hole_id", hole_id),)
    if layer is not None:
        params += (("layer_index", layer),)
    if slot is not None:
        params += (("slot_index", slot),)
    snapshot["part_features"] = {
        panel.stable_id: (replace(first, source_params=params),) + features[1:],
    }


def test_valid_legacy_slot_and_hole_id_only_and_consistent_hybrid_remain_usable():
    snapshot, panel, features, _proof = _physical_saved_editor()
    original = _world_x(snapshot, panel)
    assert original == pytest.approx(-150.0)
    owner = snapshot["nfb_config"]["holes"][0]["physical_hole_id"]

    _set_first_source(snapshot, panel, features, hole_id=owner, layer=None, slot=None)
    assert _world_x(snapshot, panel) == pytest.approx(original)

    _set_first_source(snapshot, panel, features, hole_id=owner, layer=0, slot=0)
    assert _world_x(snapshot, panel) == pytest.approx(original)


@pytest.mark.parametrize("hole_owner,layer,slot", (
    ("same", 0, 1),       # A matched hole ID cannot borrow slot 1.
    ("other", 0, 0),      # A matched slot cannot borrow another hole ID.
    ("same", None, 0),    # Partial tier identity is not a valid hybrid.
    ("same", False, 0),   # Boolean 0 is not a physical tier integer.
    ("same", 0, False),   # Boolean 0 is not a physical slot integer.
))
def test_conflicting_saved_source_identity_refuses_world_x_and_finalscene(
    hole_owner, layer, slot, tmp_path,
):
    snapshot, panel, features, _proof = _physical_saved_editor()
    owner = snapshot["nfb_config"]["holes"][
        0 if hole_owner == "same" else 1
    ]["physical_hole_id"]
    _set_first_source(
        snapshot, panel, features,
        hole_id=owner, layer=layer, slot=slot,
    )
    original = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_PHYSICAL_SLOT_IDENTITY_CONFLICT"):
        _world_x(snapshot, panel)
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_PHYSICAL_SLOT_IDENTITY_CONFLICT"):
        apply_committed_csv_v5_to_canonical_parts(snapshot, (_make(snapshot),))
    assert snapshot == original
    assert list(tmp_path.glob("*.dxf")) == []
