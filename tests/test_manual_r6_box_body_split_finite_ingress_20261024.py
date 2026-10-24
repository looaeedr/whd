"""Manual source audit: physical Box Body W widths and fold lengths are finite."""
import pytest

import phase6_box_body_structure as body


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, False, "NaN", "Infinity"])
@pytest.mark.parametrize("fn", [
    lambda bad: body.resolve_two_piece_widths({}, bad),
    lambda bad: body.set_two_piece_width({}, 800, "left", bad, manual=False),
    lambda bad: body.set_two_piece_width({}, bad, "left", 200, manual=False),
    lambda bad: body.set_three_piece_width({}, 800, "middle", bad, manual=False),
    lambda bad: body.set_three_piece_width({}, bad, "left", 100, manual=False),
    lambda bad: body.reconcile_box_body_structure_for_total_w_change({}, bad),
    lambda bad: body.set_join_seam_bend({}, body.BoxBodyStructureType.TWO_PIECE_W_SPLIT, bad),
    lambda bad: body.set_side_back_piece_profile({}, "left_side", [{"len": bad, "core": "D"}]),
])
def test_r6_nonfinite_and_bool_never_enter_physical_w_or_fold_configuration(bad, fn):
    with pytest.raises(ValueError):
        fn(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, False])
def test_r6_corrupt_saved_two_piece_width_is_rejected_before_geometry(bad):
    good = body.set_two_piece_width({}, 800, "left", 300)
    good["configs"][body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]["left_w"] = bad
    with pytest.raises(ValueError):
        body.resolve_two_piece_widths(good, 800)


def test_r6_good_split_widths_and_operator_drivers_remain_unchanged():
    two = body.set_two_piece_width({}, 800, "left", 300)
    assert body.resolve_two_piece_widths(two, 800) == (300.0, 500.0)
    three = body.set_three_piece_width({}, 800, "middle", 400)
    assert body.resolve_three_piece_widths(three, 800) == (200.0, 400.0, 200.0)
    assert body.reconcile_box_body_structure_for_total_w_change(two, 900)[
        "configs"
    ][body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]["left_w"] == 300.0


def test_r6_valid_join_bend_and_side_fold_lengths_still_pass():
    updated = body.set_join_seam_bend(
        {}, body.BoxBodyStructureType.TWO_PIECE_W_SPLIT, 12.0
    )
    assert updated["configs"][body.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]["seam_bend"] == 12.0
    record = body.set_side_back_piece_profile(
        {}, "left_side", [{"len": 100.0, "core": "D"}],
    )
    assert record["configs"][
        body.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    ]["piece_profiles"]["left_side"][0]["len"] == 100.0
