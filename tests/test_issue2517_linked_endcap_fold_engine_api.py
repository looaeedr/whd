"""#2517: arbitrary BoxBody mating Fold belongs to headless public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine import build_linked_endcap_xy_fold_profiles
from phase6_fold_profiles import (
    build_linked_endcap_xy_profiles as gui_linked,
    _phase6_box_mating_front_chain as gui_mating,
)
from tests.test_phase6_linked_fold_chain_and_parts import _box_profile, _segment


SNAPSHOT = {
    "w": 400, "d": 250, "t": 2, "fw": 25,
    "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
}


@pytest.mark.parametrize("segments", (5, 20))
def test_engine_owns_linked_head_tail_fold_with_real_arbitrary_source_turns(segments):
    extras = [_segment(6 + i, 45 if i % 2 else -90) for i in range(segments - 5)]
    box = _box_profile(extra_left=extras)
    original = deepcopy(box)
    result = build_linked_endcap_xy_fold_profiles(SNAPSHOT, box)
    assert build_linked_endcap_xy_fold_profiles is manufacturing_api.build_linked_endcap_xy_fold_profiles
    assert box == original  # manufacturing projection never mutates the signed input
    assert result == gui_linked(SNAPSHOT, box)
    head, tail = result["head"]["Y"], result["tail"]["Y"]
    assert len(head) == len(tail) == segments - 2
    assert [row["phase6_key"] for row in head] == [
        *[f"box_mating:extra:{i}" for i in range(segments-5)],
        "fw", "endcap_d_core", "ybottom1",
    ]
    assert [row["phase6_key"] for row in tail] == list(reversed(
        [row["phase6_key"] for row in head]
    ))
    assert head[-2]["len"] == tail[1]["len"] == 244
    assert "angle" not in head[-1] and "angle" not in tail[-1]
    assert len([r for r in head if "angle" in r]) == segments - 3
    assert [r.get("angle") for r in head[:-2]] == [
        *[float(row["angle"]) for row in extras],
        -90.0,
    ]


def test_engine_rejects_missing_d_w_d_mating_core():
    invalid = [_segment(25, -90, key="fw_left"), _segment(200, -90, core="D"),
               _segment(25, None, key="fw_right")]
    with pytest.raises(ValueError, match="D-W-D"):
        manufacturing_api.build_linked_endcap_xy_fold_profiles(SNAPSHOT, invalid)
    with pytest.raises(ValueError, match="D-W-D"):
        manufacturing_api.box_body_front_mating_fold_chain(invalid)


def test_existing_family_canonical_box_fold_uses_engine_default_endcap():
    snapshot = {**SNAPSHOT, "model": "受電箱"}
    box = manufacturing_api.build_box_body_fold_profile(snapshot)
    assert manufacturing_api.is_canonical_box_body_mating_profile(box, snapshot)
    linked = manufacturing_api.build_linked_endcap_xy_fold_profiles(snapshot, box)
    assert linked["head"] == manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key="head")
    assert linked["tail"] == manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key="tail")


def test_phase6_mating_entry_points_only_call_engine_public_api():
    source = inspect.getsource(gui_linked) + inspect.getsource(gui_mating)
    assert "manufacturing_api.build_linked_endcap_xy_fold_profiles(" in source
    assert "manufacturing_api.box_body_front_mating_fold_chain(" in source
    assert "allocate_integer_budget(" not in source
    engine_source = inspect.getsource(manufacturing_api.build_linked_endcap_xy_fold_profiles)
    assert "from phase6_" not in engine_source
    assert "import tkinter" not in engine_source
