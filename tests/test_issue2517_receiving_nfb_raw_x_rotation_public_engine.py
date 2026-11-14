"""#2517 NFB draft GUI must preserve original X and rotation sources to Engine."""
import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_nfb_ui1a_edits import (
    set_nfb_manual_x, set_nfb_layer_rotation, set_nfb_slot_rotation,
)


_GUI = Path(__file__).resolve().parents[1] / (
    "gui_modules/application/fold_designer_composition_receiving.py"
)
MODEL = "400_140X257_107.dxf"


def _draft():
    return api.normalize_receiving_nfb_editable_draft(
        api.new_receiving_nfb_draft(
            set_brand="士林", layer_count=2, model_layers=([MODEL], ""),
        )
    )


def _slot(draft):
    return draft["layers"][0]["slots"][0]


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Assigned:
    def curselection(self):
        return (0,)


class _Warning:
    def __init__(self):
        self.messages = []

    def set(self, value):
        self.messages.append(value)


def _gui_callback(name, *, x="0", angle="90", unit_angle="90"):
    source = ast.parse(_GUI.read_text(encoding="utf-8"))
    matches = [
        node for node in ast.walk(source)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    state = {"draft": _draft()}
    warning = _Warning()
    updates, resets = [], []
    row = {
        "assigned": _Assigned(),
        "manual_x_var": _Var(x),
        "layer_rotation_var": _Var(angle),
        "unit_rotation_var": _Var(unit_angle),
    }
    namespace = {
        "deepcopy": deepcopy,
        "set_nfb_manual_x": api.set_receiving_nfb_draft_manual_x,
        "set_nfb_layer_rotation": api.set_receiving_nfb_draft_layer_rotation,
        "set_nfb_slot_rotation": api.set_receiving_nfb_draft_slot_rotation,
        "INHERIT": api.RECEIVING_NFB_DRAFT_INHERIT,
        "OVERRIDE": api.RECEIVING_NFB_DRAFT_OVERRIDE,
        "layer_rows": [row],
        "draft_state": state,
        "warning": warning,
        "paint_draft_preview": lambda: updates.append("paint"),
        "show_x_clear_impact": lambda *a: resets.append(a),
    }
    exec(compile(ast.Module(body=matches, type_ignores=[]), str(_GUI), "exec"),
         namespace)
    return namespace[name], state, warning, updates, resets


def test_existing_facade_transactions_are_exact_canonical_owners():
    assert api.set_receiving_nfb_draft_manual_x is set_nfb_manual_x
    assert api.set_receiving_nfb_draft_layer_rotation is set_nfb_layer_rotation
    assert api.set_receiving_nfb_draft_slot_rotation is set_nfb_slot_rotation


@pytest.mark.parametrize("raw,expected", (
    ("12.375", 12.375), ("-4.25", -4.25), ("0", 0.0),
    (" 8.5 ", 8.5), ("1e2", 100.0), (12.375, 12.375),
    (-4, -4.0),
))
def test_valid_draft_manual_x_original_tk_source_parity_and_json_reload(raw, expected):
    original = _draft()
    before = deepcopy(original)
    actual = api.set_receiving_nfb_draft_manual_x(original, 0, 0, raw)
    direct = set_nfb_manual_x(original, 0, 0, expected)
    assert _slot(actual) == _slot(direct)
    assert _slot(actual)["manual_x_mm"] == pytest.approx(expected)
    assert _slot(actual)["manual_x_state"] == "UNVERIFIED_BASIS"
    assert original == before
    assert json.loads(json.dumps(actual)) == actual


@pytest.mark.parametrize("raw", (None, "", "  ", "\t"))
def test_blank_draft_x_is_engine_reset_and_not_an_implicit_zero(raw):
    original = set_nfb_manual_x(_draft(), 0, 0, 3.25, datum={"old": "datum"})
    expected = set_nfb_manual_x(original, 0, 0, None)
    actual = api.set_receiving_nfb_draft_manual_x(original, 0, 0, raw)
    assert actual == expected and original != actual
    assert _slot(actual)["manual_x_mm"] is None
    assert _slot(actual)["manual_x_state"] == "NONE"
    assert _slot(actual)["datum_snapshot"] is None


@pytest.mark.parametrize("bad", (
    True, False, "nan", "inf", "-inf", "1e999", "bad", "-bad",
    [], {}, [12], 1e308 * 10,
))
def test_invalid_raw_x_rejected_before_any_draft_transaction(bad):
    original = _draft()
    before = deepcopy(original)
    with pytest.raises(ValueError, match="finite"):
        api.set_receiving_nfb_draft_manual_x(original, 0, 0, bad)
    assert original == before
    session = api.ReceivingNfbDraftEditSession(original)
    with pytest.raises(ValueError):
        session.apply("INVALID_X", api.set_receiving_nfb_draft_manual_x, 0, 0, bad)
    assert session.current == before and not session.dirty


@pytest.mark.parametrize("raw,expected", (
    ("0", 0), ("90", 90), ("180", 180), ("270", 270),
    (0, 0), (90, 90), (180, 180), (270, 270),
))
def test_valid_original_quarter_turn_selection_matches_numeric_engine(raw, expected):
    original = _draft()
    a = api.set_receiving_nfb_draft_layer_rotation(original, 0, raw)
    b = set_nfb_layer_rotation(original, 0, expected)
    assert a == b
    c = api.set_receiving_nfb_draft_slot_rotation(
        original, 0, 0, mode=api.RECEIVING_NFB_DRAFT_OVERRIDE, value=raw,
    )
    d = set_nfb_slot_rotation(
        original, 0, 0, mode=api.RECEIVING_NFB_DRAFT_OVERRIDE, value=expected,
    )
    assert c == d and _slot(c)["rotation"]["value"] == expected


@pytest.mark.parametrize("bad", (
    True, False, "090", "00", "90.0", " 90", "90 ", 90.0,
    -90, 45, 360, "true", None, [], {},
))
def test_invalid_quarter_turn_original_source_rejected_in_both_engine_routes(bad):
    original = _draft()
    before = deepcopy(original)
    with pytest.raises(ValueError):
        api.set_receiving_nfb_draft_layer_rotation(original, 0, bad)
    with pytest.raises(ValueError):
        api.set_receiving_nfb_draft_slot_rotation(
            original, 0, 0, mode=api.RECEIVING_NFB_DRAFT_OVERRIDE, value=bad,
        )
    assert original == before


def test_raw_rotation_still_revokes_stale_x_datum_without_approving_cutting():
    original = set_nfb_manual_x(_draft(), 0, 0, 15.5, datum={"old": "basis"})
    updated = api.set_receiving_nfb_draft_layer_rotation(original, 0, "90")
    assert _slot(updated)["manual_x_mm"] == 15.5
    assert _slot(updated)["datum_snapshot"] is None
    assert _slot(updated)["manual_x_state"] == "UNVERIFIED_BASIS"
    assert _slot(original)["datum_snapshot"] == {"old": "basis"}
    assert json.loads(json.dumps(updated)) == updated


def test_actual_gui_manual_x_callback_passes_raw_and_reset_visibility_uses_engine():
    callback, holder, warning, paints, resets = _gui_callback("set_x_in_draft", x="-12.5")
    callback(0)
    assert _slot(holder["draft"])["manual_x_mm"] == -12.5
    assert paints == ["paint"] and resets == []
    assert warning.messages == ["X 位移保留為未驗證草稿，不是絕對製造座標"]

    callback, holder, warning, paints, resets = _gui_callback("set_x_in_draft", x=True)
    before = deepcopy(holder["draft"])
    callback(0)
    assert holder["draft"] == before and not paints and not resets
    assert len(warning.messages) == 1

    callback, holder, warning, paints, resets = _gui_callback("set_x_in_draft", x=" ")
    callback(0)
    assert _slot(holder["draft"])["manual_x_mm"] is None
    assert paints == ["paint"] and len(resets) == 1


@pytest.mark.parametrize("bad", ("090", "90.0", True))
def test_actual_gui_rotation_callback_does_not_cast_invalid_choices(bad):
    for unit in (False, True):
        callback, holder, warning, paints, _ = _gui_callback(
            "set_rotation_in_draft", angle=bad, unit_angle=bad,
        )
        before = deepcopy(holder["draft"])
        callback(0, unit=unit)
        assert holder["draft"] == before
        assert len(warning.messages) == 1
        assert paints == []


def test_actual_gui_valid_rotation_and_explicit_inherit_keep_one_engine_owner():
    callback, holder, warning, paints, _ = _gui_callback(
        "set_rotation_in_draft", angle="90", unit_angle="180",
    )
    callback(0)
    callback(0, unit=True)
    assert holder["draft"]["layers"][0]["rotation_deg"] == 90
    assert _slot(holder["draft"])["rotation"] == {
        "mode": api.RECEIVING_NFB_DRAFT_OVERRIDE, "value": 180,
    }
    assert len(paints) == 2
    assert not warning.messages or all("角度僅保存草稿" in msg for msg in warning.messages)

    callback, holder, _, paints, _ = _gui_callback(
        "set_rotation_in_draft", unit_angle="跟隨本層",
    )
    callback(0, unit=True)
    assert _slot(holder["draft"])["rotation"] == {
        "mode": api.RECEIVING_NFB_DRAFT_INHERIT, "value": None,
    }
    assert paints == ["paint"]


def test_gui_nfb_draft_has_no_numeric_preparser_or_private_engine_owner():
    source = _GUI.read_text(encoding="utf-8")
    segment = source.split("        def set_rotation_in_draft(", 1)[1].split(
        "        editor_body = ttk.Frame(", 1,
    )[0]
    for forbidden in (
        "int(text)", 'int(row["layer_rotation_var"].get())',
        "float(typed)", 'row["manual_x_var"].get().strip()',
    ):
        assert forbidden not in segment
    assert "set_nfb_manual_x(" in segment
    assert "set_nfb_layer_rotation(" in segment
    assert "set_nfb_slot_rotation(" in segment
