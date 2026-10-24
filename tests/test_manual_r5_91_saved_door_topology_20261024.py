"""R5 #91: persisted door topology is numeric authority, not UI entry text."""
from copy import deepcopy
import pytest
from phase6_project_file import _normalize_authoritative_door_state


@pytest.mark.parametrize("bad", [True, False, "500", "NaN", float("nan"), float("inf")])
def test_r5_91_non_numeric_or_non_finite_saved_door_width_is_rejected(bad):
    saved = {"door_layout_columns": [[bad, [700.0]]]}
    before = deepcopy(saved)
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state(saved)
    assert saved == before or (
        str(saved["door_layout_columns"][0][0]) == str(before["door_layout_columns"][0][0])
    )


@pytest.mark.parametrize("bad", [True, False, "500", "NaN", float("nan"), float("-inf")])
def test_r5_91_non_numeric_or_non_finite_saved_door_height_is_rejected(bad):
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state(
            {"door_layout_columns": [[400.0, [bad]]]}
        )


def test_r5_91_valid_numeric_door_topology_survives_save_reopen_normalization():
    saved = {
        "door_layout_columns": [[400, [500, 700.5]], [300.25, [600, 600.5]]],
        "door_handle_edges": {"0:0": "LEFT", "1:1": "RIGHT"},
    }
    normalized = _normalize_authoritative_door_state(saved)
    assert normalized["door_layout_columns"] == [
        [400.0, [500.0, 700.5]], [300.25, [600.0, 600.5]],
    ]
    normalized_again = _normalize_authoritative_door_state(normalized)
    assert normalized_again == normalized
    assert saved["door_layout_columns"][0][0] == 400
