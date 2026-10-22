# -*- coding: utf-8 -*-
"""Receiving root BasePlate is source-owned; stale four-flange editor state is not."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine.receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
from gui_modules.application.fold_designer_part_session import (
    Phase6PartSessionOwner,
    _activation_profiles_from_authoritative_source,
)
from phase6_manufacturing_adapter import read_standard_part_profiles
from phase6_settings_profile_projection import build_standard_part_profiles
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _old_generic():
    return {
        "X": [
            {"phase6_key": "base_bend_l", "len": 20.0},
            {"phase6_key": "base_face_w", "len": 600.0},
            {"phase6_key": "base_bend_r", "len": 20.0},
        ],
        "Y": [
            {"phase6_key": "base_bend_b", "len": 20.0},
            {"phase6_key": "base_face_h", "len": 250.0},
            {"phase6_key": "base_bend_t", "len": 20.0},
        ],
    }


def test_submitted_receiving_base_activation_replaces_stale_generic_workspace():
    snapshot = _assembled()
    assert snapshot["model"] == "受電箱"
    assert snapshot["nfb_config_submitted"] is True
    actual = build_standard_part_profiles(snapshot, "base_plate")
    assert actual == receiving_base_plate_3d_profiles(snapshot)
    assert len(actual["X"]) == 5  # four source BENDs, NOT four equal edge flanges
    assert [p["phase6_key"] for p in actual["X"]][:2] == [
        "receiving_left_first_40", "receiving_left_second",
    ]
    assert len(actual["Y"]) == 3
    selected, refresh = _activation_profiles_from_authoritative_source(
        "base_plate", snapshot, _old_generic(), actual,
    )
    assert refresh is True
    assert selected == actual
    assert not any(p.get("phase6_key") == "base_bend_l" for p in selected["X"])


@pytest.mark.parametrize("pattern,expected_x", (
    ("CENTER_DOUBLE_SIDE_FOLD", 5),
    ("LEFT_FLAT_SIDE", 1),
    ("RIGHT_FLAT_SIDE", 1),
))
def test_receiving_source_stays_the_only_authority_for_center_or_flat(pattern, expected_x):
    from tests.test_receiving_base_3d_profile_source_bends import _snap

    snapshot = _snap(pattern)
    current = build_standard_part_profiles(snapshot, "base_plate")
    assert len(current["X"]) == expected_x
    result, fresh = _activation_profiles_from_authoritative_source(
        "base_plate", snapshot, _old_generic(), current,
    )
    assert fresh and result == current
    # The physical panel may carry different X/Y fold counts and stations.
    # It must NEVER be translated into generic base_plate_bend.
    assert read_standard_part_profiles("base_plate", current, snapshot) == {}
    assert read_standard_part_profiles("base_plate", _old_generic(), snapshot) == {}


def test_real_submitted_source_never_reverse_maps_to_generic_even_from_old_cache():
    snapshot = _assembled()
    old = deepcopy(snapshot)
    physical = receiving_base_plate_3d_profiles(snapshot)
    assert read_standard_part_profiles("base_plate", physical, snapshot) == {}
    assert read_standard_part_profiles("base_plate", _old_generic(), snapshot) == {}
    assert snapshot == old, "read-only source projection must not alter NFB or bends"


def test_unconfigured_legacy_or_other_family_retains_previous_editable_selection():
    from tests.test_receiving_base_3d_profile_source_bends import _snap

    snapshot = _snap()
    snapshot.pop("receiving_base_plate")
    legacy = _old_generic()
    defaults = build_standard_part_profiles(snapshot, "base_plate")
    assert len(defaults["X"]) == 3
    selected, fresh = _activation_profiles_from_authoritative_source(
        "base_plate", snapshot, legacy, defaults,
    )
    assert selected is legacy and fresh is False
    another, fresh = _activation_profiles_from_authoritative_source(
        "base_plate", {**snapshot, "model": "金庫型"}, legacy, defaults,
    )
    assert another is legacy and fresh is False


def test_other_family_still_rejects_four_different_generic_base_folds():
    profiles = _old_generic()
    profiles["X"][0]["len"] = 24.0
    with pytest.raises(ValueError, match="底板四邊折彎"):
        read_standard_part_profiles(
            "base_plate", profiles,
            {"model": "金庫型", "base_plate_bend": 20},
        )


def test_real_part_session_save_switch_does_not_rewrite_received_base_as_generic(
    monkeypatch,
):
    """Exercise the same save_current_part owner invoked by activate_part."""
    import fold_designer_bridge as bridge

    source = _assembled()
    incoming = _old_generic()
    saved = {}
    actions = []

    def stash(part, profiles):
        saved[part] = deepcopy(profiles)

    app = SimpleNamespace(
        _phase6_input_snapshot=source,
        _phase6_box_whd={"w": 800., "h": 1600., "d": 350.},
        designer_workspace=SimpleNamespace(
            switching=False, active_part="base_plate",
            custom_part=lambda _key: None,
            stash_profiles=stash,
        ),
        bend_ui=SimpleNamespace(save=lambda: actions.append("bend_ui.save")),
        state=SimpleNamespace(profiles=incoming),
        v_w=SimpleNamespace(get=lambda: "800"),
        v_h=SimpleNamespace(get=lambda: "1600"),
        v_d=SimpleNamespace(get=lambda: "350"),
    )
    monkeypatch.setattr(
        bridge, "_phase6_store_editor_values",
        lambda *args, **kwargs: actions.append("legacy_store"),
    )
    original = deepcopy(source)
    Phase6PartSessionOwner().bind_application(app).save_current_part()
    assert saved["base_plate"] == receiving_base_plate_3d_profiles(original)
    assert actions == ["bend_ui.save"]
    assert source == original
    assert not any(p["phase6_key"].startswith("base_bend")
                   for p in saved["base_plate"]["X"])
