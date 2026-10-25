"""R5 #91: persisted door topology is numeric authority, not UI entry text."""
import pytest
from phase6_project_file import _normalize_authoritative_door_state


@pytest.mark.parametrize("bad", [True, False, "500", "NaN", float("nan"), float("inf")])
def test_r5_91_non_numeric_or_non_finite_saved_door_width_is_rejected(bad):
    saved = {"door_layout_columns": [[bad, [700.0]]]}
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state(saved)
    # A rejected project must not mutate caller-owned source data.
    assert saved["door_layout_columns"][0][0] is bad
    assert saved["door_layout_columns"][0][1] == [700.0]


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


@pytest.mark.parametrize("field,bad", [
    ("d", True), ("t", False),
    ("d", float("nan")), ("t", float("inf")),
    ("d", 10 ** 400), ("t", -1),
])
def test_r5_91_inner_door_saved_depth_thickness_never_coerce_corrupt_sources(field, bad):
    """Reload must reject invalid physical d/t before divider and inner-door roles."""
    saved = {
        "model": "標準型",
        "door_layout_columns": [[400., [500., 500.]]],
        "multi_door_enabled": True,
        "inner_doors": [{"stable_id": "inner-door-test"}],
        "d": 350.,
        "t": 2.,
    }
    saved[field] = bad
    with pytest.raises(ValueError, match="inner-door shared role"):
        _normalize_authoritative_door_state(saved)
    assert saved[field] is bad


def test_r5_91_inner_door_valid_numeric_or_legacy_numeric_string_dt_stays_supported():
    saved = {
        "model": "標準型",
        "door_layout_columns": [[400., [500., 500.]]],
        "multi_door_enabled": True,
        "inner_doors": [{"stable_id": "inner-door-test"}],
        "d": "350",
        "t": "2",
    }
    result = _normalize_authoritative_door_state(saved)
    assert result["d"] == "350" and result["t"] == "2"
    assert result["door_layout_columns"] == [[400., [500., 500.]]]


@pytest.mark.parametrize("field, malformed", [
    ("door_layout_columns", 42),
    ("door_layout_columns", True),
    ("door_handle_edges", 42),
    ("door_handle_edges", True),
    ("inner_doors", 42),
    ("inner_doors", True),
])
def test_r5_91_corrupt_persisted_door_collections_fail_as_project_value_errors(field, malformed):
    """Top-level saved layout collections may never crash GUI project reopen."""
    saved = {field: malformed}
    with pytest.raises(ValueError, match="invalid .* (?:columns|edges|doors)"):
        _normalize_authoritative_door_state(saved)
    assert saved[field] is malformed


def test_r5_91_legacy_sequence_and_mapping_door_state_preserves_normalization():
    saved = {
        "door_layout_columns": ((400., (500., 500.)),),
        "door_handle_edges": {"0:0": "LEFT"},
        "inner_doors": ({"stable_id": "inner-v1", "frame_spans": (3.,)},),
    }
    normalized = _normalize_authoritative_door_state(saved)
    assert normalized["door_layout_columns"] == [[400., [500., 500.]]]
    assert normalized["door_handle_edges"] == {"0:0": "LEFT"}
    assert normalized["inner_doors"] == [{"stable_id": "inner-v1"}]
