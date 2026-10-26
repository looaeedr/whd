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


@pytest.mark.parametrize("malformed", [
    "inner-door-v1", {"stable_id": "inner-door-v1"},
    [None], [True], [42], ["inner-door-v1"],
    [{"stable_id": "valid"}, None],
])
def test_r5_91_inner_door_entries_reject_non_record_persisted_sources(malformed):
    """Project open must not turn text/maps into a false physical door inventory."""
    saved = {"inner_doors": malformed}
    with pytest.raises(ValueError, match="invalid inner doors"):
        _normalize_authoritative_door_state(saved)
    assert saved["inner_doors"] == malformed


@pytest.mark.parametrize("malformed_role", [True, 42, "not-a-mapping", ["divider-id"]])
def test_r5_91_malformed_inner_door_lower_role_fails_without_rebinding(malformed_role):
    saved = {
        "model": "標準型",
        "door_layout_columns": [[400., [500., 500.]]],
        "multi_door_enabled": True,
        "inner_doors": [{
            "stable_id": "inner-door-v1",
            "lower_frame_role": malformed_role,
        }],
        "d": 350., "t": 2.,
    }
    with pytest.raises(ValueError, match="invalid inner-door lower_frame_role"):
        _normalize_authoritative_door_state(saved)
    assert saved["inner_doors"][0]["lower_frame_role"] is malformed_role


@pytest.mark.parametrize("field", ["stable_id", "cell_key"])
@pytest.mark.parametrize("bad", [True, False])
def test_r5_91_saved_inner_door_bool_identity_never_becomes_project_authority(field, bad):
    saved = {"inner_doors": [{"stable_id": "upper", "cell_key": "0:0"}]}
    saved["inner_doors"][0][field] = bad
    with pytest.raises(ValueError, match="invalid inner-door identity"):
        _normalize_authoritative_door_state(saved)
    assert saved["inner_doors"][0][field] is bad


@pytest.mark.parametrize("bad_cell", [
    True, False, 42, float("nan"), float("inf"),
    {"col": 0, "row": 0}, ["0:0"],
])
def test_r5_91_physical_inner_door_panel_cell_identity_must_be_saved_text(bad_cell):
    """No boolean/NaN/object alias may become a physical 2D/3D door cell."""
    from ae_engine.inner_door_panels import derive_inner_door_panel

    with pytest.raises(ValueError, match="inner-door panel cell_key"):
        derive_inner_door_panel(
            "upper", cell_key=bad_cell, width=689., height=900., thickness=2.,
        )
    legitimate = derive_inner_door_panel(
        "upper", cell_key="0:0", width=689., height=900., thickness=2.,
    )
    assert legitimate.cell_key == "0:0"
    assert legitimate.stable_id == "inner_door:upper:panel"
    assert legitimate.unfolded_width == pytest.approx(723.)


@pytest.mark.parametrize("bad_id", [float("nan"), float("inf"), {}, ["upper"]])
def test_r5_91_physical_inner_door_stable_id_must_be_real_source_identity(bad_id):
    """NaN/object identities cannot own hole features or a manufactured panel."""
    from ae_engine.inner_door_panels import derive_inner_door_panel
    with pytest.raises(ValueError, match="inner_door_id"):
        derive_inner_door_panel(
            bad_id, cell_key="0:0", width=689., height=900., thickness=2.,
        )
    legacy_id = derive_inner_door_panel(
        1, cell_key="0:0", width=689., height=900., thickness=2.,
    )
    assert legacy_id.stable_id == "inner_door:1:panel"


@pytest.mark.parametrize("field", ["door_layout_columns", "door_handle_edges"])
@pytest.mark.parametrize("corrupt", [False, 0, "", {}])
def test_r5_91_explicit_falsy_nonsequence_door_authority_cannot_disappear(field, corrupt):
    """Project reopen must not turn invalid saved topology/handles into empty data."""
    saved = {field: corrupt}
    with pytest.raises(ValueError, match="invalid door"):
        _normalize_authoritative_door_state(saved)
    assert saved[field] == corrupt


def test_r5_91_legacy_empty_sequences_and_handle_pairs_still_reopen():
    assert _normalize_authoritative_door_state({
        "door_layout_columns": [],
        "door_handle_edges": [],
    })["door_handle_edges"] == {}
    valid = _normalize_authoritative_door_state({
        "door_layout_columns": [[800., [1600.]]],
        "door_handle_edges": [("0:0", "LEFT")],
    })
    assert valid["door_handle_edges"] == {"0:0": "LEFT"}
