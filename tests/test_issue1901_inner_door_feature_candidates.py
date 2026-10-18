"""#1901: candidate Hole Editor features must not leak into live Receiving Bays."""
from copy import deepcopy

import pytest

from ae_engine.receiving_inner_door_candidates import (
    create_inner_candidate, inner_config, update_inner_candidate,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_shared_settings import setting_value
from ae_engine.sheetmetal_features import (
    FeatureAnchor, RectFeature, Vec2,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from phase6_project_file import _encode, _decode


PART = "inner_door:upper:panel"


def _opening(x=250.0):
    return RectFeature(
        width=25.0, height=111.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, 300.0),
        source_type="NFB", layer="CUTTING",
    )


def test_candidate_only_becomes_one_real_bay_hole_after_explicit_apply():
    adapter = ReceivingSetBayAdapter(new_receiving_layout(
        width=800, height=1600, depth=350,
    ))
    adapter.set_bay_count(2)
    first = _opening()
    library, version = create_inner_candidate(None, {
        "layers": 1, "models": ["", ""],
        "features": {PART: [first]},
    })
    before = adapter.layout
    # Merely editing a candidate must not affect either physical Bay.
    newer = _opening(300.0)
    edited = update_inner_candidate(library, version, {
        "layers": 1, "models": ["", ""],
        "features": {PART: [newer]},
    })
    assert adapter.layout == before
    assert inner_config(library, version)["features"][PART] == [first]
    assert inner_config(edited, version)["features"][PART] == [newer]

    adapter.apply_inner_door_candidate_to_bays(
        inner_config(edited, version), 0, (1,), version_id=version,
    )
    row = adapter.layout["sets"][0]
    assert setting_value(row, 0, "inner_door_features") == {}
    assert setting_value(row, 1, "inner_door_features") == {PART: [newer]}
    assert setting_value(row, 1, "inner_door_version_id") == version
    projected = project_receiving_bay_legacy_aliases({
        "cabinet_type": "受電箱", "receiving_layout": adapter.layout,
    }, set_index=0, bay_index=1, validate_common=False)
    assert projected["part_features"][PART] == [newer]


def test_candidate_hole_feature_round_trip_and_old_empty_versions():
    feature = _opening()
    library, version = create_inner_candidate(None, {
        "layers": 1, "models": ["", ""],
        "features": {PART: [feature]},
    })
    restored = _decode(_encode(deepcopy(library)))
    assert inner_config(restored, version)["features"][PART] == [feature]
    legacy, old_version = create_inner_candidate(None, {
        "layers": 1, "models": ["", ""],
    })
    assert inner_config(legacy, old_version)["features"] == {}
    with pytest.raises(ValueError):
        create_inner_candidate(None, {
            "layers": 1, "models": ["", ""],
            "features": {"head": [feature]},
        })
