"""#2517: Settings corner readback resolves physical pair identity via public Engine."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode,
)
from gui_modules.application import fold_designer_composition_settings as gui


def _make_composition(pair_same):
    state = {
        "top_left": CornerTypeSelection(CornerTypeId.C02),
        "top_right": CornerTypeSelection(CornerTypeId.CROSS),
        "bottom_left": CornerTypeSelection(CornerTypeId.C02),
        "bottom_right": CornerTypeSelection(CornerTypeId.CROSS),
    }
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型"},
        _settings_values={},
    )
    methods = {
        "ENDCAP_FW_PARTS": ("head", "tail"),
        "GLOBAL_CONTEXT": "global",
        "CrossCornerMode": CrossCornerMode,
        "_FIXED_CORNER_SUMMARIES": {},
        "_phase6_corner_type_editable": lambda *_: True,
        "_phase6_corner_parameters_unlocked": lambda *_: True,
        "_phase6_corner_parameters_editable": lambda *_: True,
        "_phase6_ensure_corner_part": lambda *_: (state, pair_same),
        "_CORNER_TYPE_LABEL_BY_ID": {
            kind.value: kind.value for kind in CornerTypeId
        },
        "_CORNER_DIRECTION_LABEL": {},
        "_CORNER_MODE_LABEL": {},
        "_phase6_selection_from_raw": lambda raw: raw,
        "_phase6_corner_parameter_summary": lambda raw: "",
    }
    composition = SimpleNamespace(
        app=app, _required=lambda _namespace, key: methods[key],
    )
    return composition, state


@pytest.mark.parametrize("top_same,bottom_same", (
    (True, True), (False, True), (True, False), (False, False),
))
def test_corner_settings_returns_same_physical_parts_as_engine(top_same, bottom_same, monkeypatch):
    monkeypatch.setattr(
        gui.manufacturing_api, "project_operator_receiving_base_plate_settings",
        lambda *args, **kwargs: None,
    )
    composer, raw = _make_composition({
        "top": top_same, "bottom": bottom_same,
    })
    before = deepcopy(raw)
    view = gui.settings_context_extension_projection(composer, None, "divider")
    assert view["corner"]["mode"] == "editable"
    pairs = {row["pair_key"]: row for row in view["corner"]["pairs"]}
    for pair, is_same in (("top", top_same), ("bottom", bottom_same)):
        targets = pairs[pair]["targets"]
        expected = (
            (pair,) if is_same else api.project_operator_corner_pair_members(pair)
        )
        assert tuple(row["target_key"] for row in targets) == expected
        for row in targets:
            physical = api.project_operator_corner_selection_target(row["target_key"])
            assert row["type_kind"] == raw[physical].type_id.name
    assert raw == before


def test_corner_settings_head_tail_context_identifies_only_engine_pair_members(monkeypatch):
    # This test covers physical identity without changing top Head/Tail
    # assembly type or saved manufacturing corner state.
    monkeypatch.setattr(
        gui.manufacturing_api, "project_operator_receiving_base_plate_settings",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        gui.manufacturing_api, "operator_supports_bottom_wrap_controls",
        lambda *args, **kwargs: False,
    )
    composer, raw = _make_composition({"top": True, "bottom": False})
    composer.app._phase6_endcap_fw_state = api.normalize_endcap_fw_state({"fw": 25})
    composer.app._phase6_input_snapshot["fw"] = 25
    view = gui.settings_context_extension_projection(composer, None, "head")
    assert view["corner"]["pairs"][0]["targets"][0]["target_key"] == "top"
    assert view["corner"]["pairs"][0]["targets"][0]["type_kind"] == raw["top_left"].type_id.name
    assert tuple(row["target_key"] for row in view["corner"]["pairs"][1]["targets"]) == (
        "bottom_left", "bottom_right"
    )


def test_settings_corner_mapping_no_longer_uses_private_gui_pair_table():
    code = inspect.getsource(gui.settings_context_extension_projection)
    assert 'required("_CORNER_PAIR_KEYS")' not in code
    assert "pair_keys[" not in code
    assert "manufacturing_api.project_operator_corner_pair_members(" in code
    assert "manufacturing_api.project_operator_corner_selection_target(" in code
