"""#2517 STOCK DXF output flag: raw GUI source uses public Engine bool rules."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_composition_state import commit_output_draw_stock
from phase6_project_controller import Phase6ProjectController


@pytest.mark.parametrize(
    ("raw", "expected"), [
        (True, True), (False, False),
        ("true", True), ("false", False),
        ("on", True), ("off", False),
        (1, True), (0, False),
        (1.0, True), (0.0, False),
    ],
)
def test_project_stock_commits_exact_public_engine_boolean(raw, expected):
    staged = []
    assert Phase6ProjectController.commit_output_stock(
        raw, lambda key, value: staged.append((key, value))
    ) is expected
    assert staged == [("draw_stock", expected)]
    values = {"draw_stock": raw}
    transition = api.commit_operator_settings_state(
        {"draw_stock": False}, {"draw_stock": False}, {}, values,
    )
    assert transition.committed["draw_stock"] is expected
    assert values["draw_stock"] == raw


@pytest.mark.parametrize("bad", ["no-such-flag", 2, -1, None, float("nan"), float("inf"), object()])
def test_project_stock_rejects_invalid_source_before_stage(bad):
    staged = []
    with pytest.raises(ValueError, match="布林"):
        Phase6ProjectController.commit_output_stock(
            bad, lambda key, value: staged.append((key, value))
        )
    assert staged == []


def _gui_call(raw):
    app = SimpleNamespace(output_draw_stock_var=SimpleNamespace(get=lambda: raw))
    staged = []
    owner = SimpleNamespace(
        app=app,
        _required=lambda _namespace, _name: lambda received_app, key, value: (
            staged.append((received_app, key, value))
        ),
    )
    result = commit_output_draw_stock(owner, {})
    return result, staged, app


@pytest.mark.parametrize(("saved", "expected"), [
    ("false", False), ("true", True), ("off", False), ("on", True),
])
def test_gui_stock_reloaded_source_matches_headless_engine(saved, expected):
    serialized = json.loads(json.dumps({"draw_stock": saved}))
    actual, staged, app = _gui_call(serialized["draw_stock"])
    assert actual is expected
    assert staged == [(app, "draw_stock", expected)]
    assert serialized["draw_stock"] == saved
    assert api.normalize_operator_settings_boolean(saved) is expected


def test_gui_stock_invalid_value_is_atomic_and_uses_raw_engine_route():
    staged = []
    app = SimpleNamespace(
        output_draw_stock_var=SimpleNamespace(get=lambda: "invalid"),
    )
    owner = SimpleNamespace(
        app=app,
        _required=lambda _ns, _name: lambda _app, key, value: staged.append((key, value)),
    )
    with pytest.raises(ValueError, match="布林"):
        commit_output_draw_stock(owner, {})
    assert staged == []
    assert "bool(app.output_draw_stock_var.get())" not in inspect.getsource(
        commit_output_draw_stock
    )
    assert "manufacturing_api.normalize_operator_settings_boolean" in inspect.getsource(
        Phase6ProjectController.commit_output_stock
    )
