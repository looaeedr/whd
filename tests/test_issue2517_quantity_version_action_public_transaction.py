"""#2517: Version add/delete/select/count use one public Engine transaction."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
from phase6_receiving_modes import fresh_receiving_mode


def _source(family="金庫型"):
    if family == "受電箱":
        source = fresh_receiving_mode("quantity", {"w": 800, "h": 1600, "d": 350}, thickness=2)
    else:
        source = {"model": "金庫型", "active_mode": "quantity", "w": 800, "h": 1600,
                  "d": 350, "t": 2, "quantity": QuantityModel().snapshot()}
    return source, QuantityModel.from_payload(source["quantity"])


def _current(source, model):
    return {**source, "quantity": model.snapshot()}


def _act(source, model, action, version_id=None, **kw):
    return api.commit_operator_quantity_version_action(
        source, model, action=action,
        version_id=model.selected_version_id if version_id is None else version_id,
        **kw,
    )


def test_root_facade_are_identical():
    assert ae_engine.commit_operator_quantity_version_action is api.commit_operator_quantity_version_action
    assert "commit_operator_quantity_version_action" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_all_four_actions_preserve_source_and_original_model_rules(family):
    source, model = _source(family)
    before = deepcopy(source)
    first = model.selected_version_id
    second = _act(source, model, "add")
    assert second != first and model.selected_version_id == second
    assert _act(_current(source, model), model, "count", piece_count="3") is None
    assert model.total_piece_count == 4
    assert _act(_current(source, model), model, "select", version_id=first) is None
    assert model.selected_version_id == first
    assert _act(_current(source, model), model, "select", version_id=second) is None
    frozen = _current(source, model)
    assert _act(frozen, model, "delete", confirmed=False) is False
    assert frozen["quantity"] == model.snapshot()
    assert _act(frozen, model, "delete", confirmed=True) is True
    assert model.total_piece_count == 1 and model.selected_version_id == first
    assert source == before


@pytest.mark.parametrize("fault", (
    "mode", "missing", "stale-source", "owner", "action", "version",
    "zero", "float", "confirmation",
))
def test_bad_actions_fail_without_writing_source(fault):
    source, model = _source("金庫型")
    args = {"action": "add", "version_id": model.selected_version_id}
    if fault == "mode":
        source["active_mode"] = "set_bay"
    elif fault == "missing":
        source.pop("quantity")
    elif fault == "stale-source":
        source["quantity"]["versions"][0]["piece_count"] = 2
    elif fault == "owner":
        model = None
    elif fault == "action":
        args["action"] = "unknown"
    elif fault == "version":
        args["version_id"] = "quantity-v99"
    elif fault == "zero":
        args.update(action="count", piece_count=0)
    elif fault == "float":
        args.update(action="count", piece_count=1.5)
    else:
        args.update(action="delete", confirmed="yes")
    before = deepcopy(source)
    prior = model.snapshot() if model else None
    with pytest.raises((ValueError, TypeError)):
        api.commit_operator_quantity_version_action(source, model, **args)
    assert source == before
    if model:
        assert model.snapshot() == prior


def test_invalid_finished_hole_cannot_be_replicated_but_selection_allows_repair():
    source, model = _source("受電箱")
    hole = CircleFeature(diameter=8, anchor=FeatureAnchor.PANEL_CENTER,
                         offset=Vec2(2000, 0))
    model.set_features("head", [hole])
    source["quantity"] = model.snapshot()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="越界|失效"):
        _act(source, model, "add")
    assert source == before and model.snapshot() == before["quantity"]
    second = model.add_version()
    source["quantity"] = model.snapshot()
    first = source["quantity"]["versions"][0]["version_id"]
    _act(source, model, "select", version_id=first)
    assert model.selected_version_id == first and second != first


def test_notifier_failure_rolls_back_without_second_callback():
    source, _ = _source("受電箱")
    calls = []
    def notify():
        calls.append(model.snapshot())
        raise RuntimeError("notification failed")
    model = QuantityModel.from_payload(source["quantity"], on_change=notify)
    before = model.snapshot()
    with pytest.raises(RuntimeError, match="notification failed"):
        _act(source, model, "add")
    assert len(calls) == 1 and calls[0] != before
    assert model.snapshot() == before


def test_noop_count_and_unconfirmed_delete_send_no_change_event():
    source, _ = _source()
    calls = []
    model = QuantityModel.from_payload(source["quantity"], on_change=lambda: calls.append(1))
    assert _act(source, model, "count", piece_count="1") is None
    assert _act(source, model, "delete", confirmed=False) is False
    assert calls == []


def test_real_project_save_reload_persists_new_version_count(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
    source, model = _source("受電箱")
    _act(source, model, "add")
    _act(_current(source, model), model, "count", piece_count=7)
    target = write_project(tmp_path / "quantity-version-action.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": _current(source, model),
    })
    restored = QuantityModel.from_payload(read_project(target)["snapshot"]["quantity"])
    assert restored.version_count == 2 and restored.selected_piece_count == 7
    assert restored.total_piece_count == 8


def test_live_gui_version_ports_only_delegate_and_publish_after_commit():
    from gui_modules.application.quantity_version_ports import quantity_ports
    text = inspect.getsource(quantity_ports)
    assert "manufacturing_api.commit_operator_quantity_version_action(" in text
    assert not any(s in text for s in ("owner.select(", "owner.add_version(",
                                  "owner.delete_selected(", "owner.set_piece_count("))
    source, model = _source("金庫型")
    publications = []
    workspace = SimpleNamespace(
        quantity_model=model, active_part="box_body",
        snapshot=lambda: {"quantity": model.snapshot(), "active_mode": "quantity"},
    )
    app = SimpleNamespace(
        designer_workspace=workspace, _phase6_input_snapshot=deepcopy(source),
        _settings_values={}, _phase6_box_whd={"w": 800, "h": 1600, "d": 350},
        baseline_model_var=SimpleNamespace(get=lambda: "金庫型"),
    )
    comp = SimpleNamespace(app=app, publish_live_state=lambda *a, **kw: publications.append(1))
    ports = quantity_ports(comp, None)
    first = model.selected_version_id
    second = ports["add"]()
    ports["count"]("5")
    ports["select"](first)
    ports["select"](second)
    assert ports["delete"](True) is True
    assert model.total_piece_count == 1
    assert len(publications) == 5
