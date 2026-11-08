"""#2517: Head/Tail/Divider pair same flags are Engine canonical booleans."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import corner_state_transactions as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CrossCornerMode
from gui_modules.application import fold_designer_composition_settings as gui


def _source(part="head"):
    return {
        part: {
            "top_left": {"type_id": "C02"},
            "top_right": {"type_id": "C03"},
            "bottom_left": {"type_id": "C02"},
            "bottom_right": {"type_id": "C04"},
        }
    }


@pytest.mark.parametrize("part", ("head", "tail", "divider"))
@pytest.mark.parametrize("top,bottom,top_result,bottom_result", (
    ("false", "true", False, True),
    ("true", "false", True, False),
    ("off", "on", False, True),
    (0, 1, False, True),
    (False, True, False, True),
))
def test_public_engine_pair_projection_decodes_serialized_source_without_mutation(
    part, top, bottom, top_result, bottom_result
):
    raw = _source(part)
    pairs = {part: {"top": top, "bottom": bottom}}
    original = deepcopy((raw, pairs))
    result = api.ensure_corner_part(raw, pairs, part)
    assert result.corner_pair_same[part] == {
        "top": top_result, "bottom": bottom_result,
    }
    assert (raw, pairs) == original
    saved = json.loads(json.dumps({
        "corner_state": result.corner_state,
        "corner_pair_same": result.corner_pair_same,
    }))
    assert saved["corner_pair_same"][part] == {
        "top": top_result, "bottom": bottom_result,
    }
    reloaded = api.ensure_corner_part(
        saved["corner_state"], saved["corner_pair_same"], part
    )
    assert reloaded.corner_pair_same == result.corner_pair_same


@pytest.mark.parametrize("part", ("head", "tail"))
def test_engine_commit_false_string_must_not_copy_other_physical_corner(part):
    raw = _source(part)
    pairs = {part: {"top": "true", "bottom": "false"}}
    initial = deepcopy((raw, pairs))
    split = api.commit_corner_pair(raw, pairs, part, "top", "false")
    assert split.corner_pair_same[part]["top"] is False
    assert split.corner_state[part]["top_left"]["type_id"] == "C02"
    assert split.corner_state[part]["top_right"]["type_id"] == "C03"
    assert (raw, pairs) == initial
    joined = api.commit_corner_pair(
        split.corner_state, split.corner_pair_same, part, "top", "true",
    )
    assert joined.corner_pair_same[part]["top"] is True
    assert joined.corner_state[part]["top_right"] == joined.corner_state[part]["top_left"]
    assert split.corner_state[part]["top_right"]["type_id"] == "C03"
    assert (raw, pairs) == initial


@pytest.mark.parametrize("field,bad", (
    ("top", "maybe"), ("bottom", "2"), ("top", 2),
    ("bottom", None), ("top", float("nan")), ("bottom", []),
))
def test_malformed_saved_pair_rejected_before_changing_any_source(field, bad):
    raw = _source("tail")
    pairs = {"tail": {"top": "false", "bottom": "false"}}
    pairs["tail"][field] = bad
    before = deepcopy((raw, pairs))
    with pytest.raises(ValueError, match="布林值"):
        api.ensure_corner_part(raw, pairs, "tail")
    with pytest.raises(ValueError, match="布林值"):
        api.commit_corner_pair(raw, pairs, "tail", "top", True)
    assert (raw, pairs) == before


@pytest.mark.parametrize("bad", ("maybe", "2", None, 2, 1.25))
def test_invalid_new_pair_edit_rejected_by_engine_without_mutation(bad):
    raw = _source()
    pairs = {"head": {"top": False, "bottom": True}}
    before = deepcopy((raw, pairs))
    with pytest.raises(ValueError, match="布林值"):
        api.commit_corner_pair(raw, pairs, "head", "top", bad)
    assert (raw, pairs) == before


def _settings_projection(raw_state, raw_pairs, part, monkeypatch):
    app = SimpleNamespace(_phase6_input_snapshot={"model": "金庫型"})
    methods = {
        "ENDCAP_FW_PARTS": ("head", "tail"),
        "GLOBAL_CONTEXT": "global",
        "CrossCornerMode": CrossCornerMode,
        "_FIXED_CORNER_SUMMARIES": {},
        "_phase6_corner_type_editable": lambda *_: True,
        "_phase6_corner_parameters_unlocked": lambda *_: True,
        "_phase6_corner_parameters_editable": lambda *_: True,
        "_phase6_ensure_corner_part": lambda _app, key: (
            api.ensure_corner_part(raw_state, raw_pairs, key).corner_state[key],
            api.ensure_corner_part(raw_state, raw_pairs, key).corner_pair_same[key],
        ),
        "_CORNER_TYPE_LABEL_BY_ID": {
            key.value: key.value for key in CornerTypeId
        },
        "_CORNER_DIRECTION_LABEL": {},
        "_CORNER_MODE_LABEL": {},
        "_phase6_selection_from_raw": owner.selection_from_raw,
        "_phase6_corner_parameter_summary": lambda *_: "",
    }
    composer = SimpleNamespace(
        app=app, _required=lambda _namespace, name: methods[name]
    )
    monkeypatch.setattr(
        gui.manufacturing_api, "project_operator_receiving_base_plate_settings",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        gui.manufacturing_api, "operator_supports_bottom_wrap_controls",
        lambda *_a, **_k: False,
    )
    if part in ("head", "tail"):
        app._phase6_endcap_fw_state = api.normalize_endcap_fw_state({"fw": 25})
        app._phase6_input_snapshot["fw"] = 25
    return gui.settings_context_extension_projection(composer, None, part)


@pytest.mark.parametrize("part", ("head", "tail", "divider"))
def test_gui_settings_shows_distinct_real_corners_for_serialized_false(part, monkeypatch):
    raw = _source(part)
    pairs = {part: {"top": "false", "bottom": "true"}}
    before = deepcopy((raw, pairs))
    view = _settings_projection(raw, pairs, part, monkeypatch)
    rows = view["corner"]["pairs"]
    assert rows[0]["same"] is False
    assert tuple(row["target_key"] for row in rows[0]["targets"]) == (
        "top_left", "top_right"
    )
    assert tuple(row["type_kind"] for row in rows[0]["targets"]) == (
        "C02", "C03"
    )
    assert rows[1]["same"] is True
    assert len(rows[1]["targets"]) == 1
    assert (raw, pairs) == before


def test_public_engine_owns_all_saved_pair_flag_interpretation():
    assert api.ensure_corner_part is owner.ensure_corner_part
    assert api.commit_corner_pair is owner.commit_corner_pair
    for call in (owner.ensure_corner_part, owner.commit_corner_pair):
        code = inspect.getsource(call)
        assert "normalize_operator_settings_boolean(" in code
    assert "pairs[pair] = bool(enabled)" not in inspect.getsource(owner.commit_corner_pair)
