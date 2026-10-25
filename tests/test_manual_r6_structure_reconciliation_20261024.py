"""R6 readback of current physical Box Body structure and EndCap inputs."""
from copy import deepcopy
import pytest
import phase6_box_body_structure as body
from gui_modules.parts.panels.endcap import setup_tab_endcap_ui


def test_r6_saved_boolean_lock_false_zero_and_true_strings():
    for raw in ("false", "0", "off", "no", "", False, 0):
        state = body.normalize_box_body_structure_state({"locked": raw})
        assert state["locked"] is False
        assert body.set_structure_locked({}, raw)["locked"] is False
    for raw in ("true", "1", "on", "yes", True, 1):
        assert body.normalize_box_body_structure_state({"locked": raw})["locked"] is True
    assert body.normalize_box_body_structure_state({})["locked"] is True


def test_r6_malformed_saved_piece_profiles_discarded_without_changing_other_config():
    kind = body.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    state = body.normalize_box_body_structure_state({"configs": {
        kind: {"piece_profiles": "invalid_not_a_dict", "side_rear_bend": 18.0}
    }})
    cfg = state["configs"][kind]
    assert cfg["piece_profiles"] == {}
    assert cfg["side_rear_bend"] == 18.0
    good = {"left_side": [{"len": 15.0, "angle": 90.0}]}
    state = body.normalize_box_body_structure_state({"configs": {kind: {"piece_profiles": good}}})
    assert state["configs"][kind]["piece_profiles"] == good
    state["configs"][kind]["piece_profiles"]["left_side"][0]["len"] = 100.
    assert good["left_side"][0]["len"] == 15.


def _partial(**values):
    kind = body.BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
    return {"configs": {kind: values}}


def test_r6_three_part_explicit_conflict_is_rejected_not_silently_overwritten():
    for config in (
        {"left_w": 150., "middle_w": 200., "right_w": None},
        {"left_w": 150., "middle_w": 300., "right_w": 180.},
        {"left_w": 150., "middle_w": 400., "right_w": 150.},
    ):
        with pytest.raises(ValueError, match="不一致"):
            body.resolve_three_piece_widths(_partial(**config), 600.)


def test_r6_three_part_valid_partial_and_standard_preserve_outside_width():
    assert body.resolve_three_piece_widths({}, 600.) == (50., 500., 50.)
    assert body.resolve_three_piece_widths(_partial(left_w=150., right_w=None), 600.) == (150., 300., 150.)
    assert body.resolve_three_piece_widths(_partial(middle_w=300.), 600.) == (150., 300., 150.)
    assert body.resolve_three_piece_widths(_partial(left_w=150., middle_w=300., right_w=None), 600.) == (150., 300., 150.)
    assert body.resolve_three_piece_widths(_partial(left_w=150., right_w=150.), 600.) == (150., 300., 150.)
    state = body.set_three_piece_width({}, 1200., "middle", 1000)
    assert body.resolve_three_piece_widths(state,1200.) == (100.,1000.,100.)
    for bad in (True,float("nan"),float("inf")):
        with pytest.raises(ValueError):
            body.resolve_three_piece_widths({},bad)


def test_r6_endcap_tab_rejects_unsupported_key_before_widget_mutation():
    with pytest.raises(ValueError, match="Unsupported endcap tab key"):
        setup_tab_endcap_ui(object(),object(),"invalid_key")


@pytest.mark.parametrize("saved_driver", [None, "left", "default"])
def test_r6_two_piece_partial_right_only_remains_the_driver_across_width_edits(saved_driver):
    """A real saved right-side outside width is not a disposable left fallback."""
    kind = body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    original = {
        "active_type": kind,
        "configs": {kind: {"left_w": None, "right_w": 200., "driver": saved_driver}},
    }
    untouched = deepcopy(original)
    first = body.reconcile_box_body_structure_for_total_w_change(original, 800.)
    assert first["configs"][kind]["left_w"] == 600.
    assert first["configs"][kind]["right_w"] == 200.
    assert first["configs"][kind]["driver"] == "right"
    second = body.reconcile_box_body_structure_for_total_w_change(first, 900.)
    assert second["configs"][kind]["left_w"] == 700.
    assert second["configs"][kind]["right_w"] == 200.
    assert second["configs"][kind]["driver"] == "right"
    assert original == untouched


def test_r6_two_piece_complete_default_still_rebalances_on_total_width_edit():
    kind = body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    original = {
        "active_type": kind,
        "configs": {kind: {"left_w": 400., "right_w": 400., "driver": "default"}},
    }
    changed = body.reconcile_box_body_structure_for_total_w_change(original, 1000.)
    assert changed["configs"][kind]["left_w"] == 500.
    assert changed["configs"][kind]["right_w"] == 500.
    assert changed["configs"][kind]["driver"] == "default"


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), 10 ** 400])
def test_r6_transaction_width_must_preserve_raw_input_for_physical_guard(bad):
    """The UI transaction must not turn bool into 1 mm or leak JSON overflow."""
    from phase6_settings_transitions import reconcile_width_structure
    saved = body.default_box_body_structure_state()
    untouched = deepcopy(saved)
    with pytest.raises(ValueError, match="箱身總寬"):
        reconcile_width_structure(saved, bad)
    assert saved == untouched
    valid = reconcile_width_structure(saved, 800.)
    assert valid == body.reconcile_box_body_structure_for_total_w_change(saved, 800.)


@pytest.mark.parametrize("invalid_width", [0, 0.0, -1.0, -800.0])
def test_r6_operator_total_width_must_be_positive_even_without_active_split(invalid_width):
    """Unsplit/empty saved structures cannot authorize zero or negative box W."""
    from phase6_settings_transitions import reconcile_width_structure
    for active in (
        body.BoxBodyStructureType.INTEGRAL.value,
        body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value,
    ):
        saved = body.default_box_body_structure_state()
        saved["active_type"] = active
        before = deepcopy(saved)
        with pytest.raises(ValueError, match="箱身總寬"):
            reconcile_width_structure(saved, invalid_width)
        assert saved == before
    good = body.default_box_body_structure_state()
    assert reconcile_width_structure(good, 800.) == (
        body.reconcile_box_body_structure_for_total_w_change(good, 800.)
    )


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("0", False), ("off", False), ("no", False),
    ("true", True), ("1", True), ("on", True), ("yes", True),
])
def test_r6_legacy_structure_lock_fallback_uses_same_saved_boolean_parser(raw, expected):
    """Non-empty partial structures must not turn legacy "false" into True."""
    for value in (None, {}, {"configs": {}}, {"active_type": body.DEFAULT_STRUCTURE_TYPE.value}):
        normalized = body.normalize_box_body_structure_state(value, legacy_locked=raw)
        assert normalized["locked"] is expected
    explicit = body.normalize_box_body_structure_state(
        {"locked": False}, legacy_locked="true",
    )
    assert explicit["locked"] is False
