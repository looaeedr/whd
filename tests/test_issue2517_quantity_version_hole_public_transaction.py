"""#2517 Quantity Head/Tail hole edits use one public Engine source transaction."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
from phase6_receiving_modes import fresh_receiving_mode


def _source(family):
    if family == "受電箱":
        snapshot = fresh_receiving_mode(
            "quantity", {"w": 800, "h": 1600, "d": 350}, thickness=2,
        )
    else:
        snapshot = {
            "model": family, "active_mode": "quantity",
            "w": 800, "h": 1600, "d": 350, "t": 2,
            "quantity": QuantityModel().snapshot(),
        }
    return snapshot, QuantityModel.from_payload(snapshot["quantity"])


def _circle(x=10):
    return CircleFeature(
        diameter=8, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(x, 0),
    )


def _commit(snapshot, model, version_id, features, role="head"):
    return api.commit_operator_quantity_version_holes(
        snapshot, model, version_id=version_id, role=role, features=features,
    )


def test_root_and_facade_are_the_same_public_transaction():
    assert ae_engine.commit_operator_quantity_version_holes is (
        api.commit_operator_quantity_version_holes
    )
    assert "commit_operator_quantity_version_holes" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_modeless_editor_commits_captured_version_without_changing_selection(family):
    snapshot, model = _source(family)
    first = model.selected_version_id
    second = model.add_version()
    snapshot["quantity"] = model.snapshot()
    original = deepcopy(snapshot)
    staged = [_circle()]
    assert _commit(snapshot, model, first, staged) is True
    assert snapshot == original
    assert model.selected_version_id == second
    assert model.features_for("head") == []
    assert model.features_for_version(first, "head") == [_circle()]
    assert model.features_for_version(second, "head") == []
    staged.clear()
    assert model.features_for_version(first, "head") == [_circle()]
    # A second no-op does not notify or recompute the GUI.
    assert _commit({**snapshot, "quantity": model.snapshot()},
                   model, first, [_circle()]) is False


def test_all_versions_are_validated_against_real_finished_face_before_write():
    snapshot, model = _source("受電箱")
    first = model.selected_version_id
    second = model.add_version()
    snapshot["quantity"] = model.snapshot()
    original = deepcopy((snapshot, model.snapshot()))
    with pytest.raises(ValueError, match="越界|失效"):
        _commit(snapshot, model, first, [_circle(1000)])
    assert (snapshot, model.snapshot()) == original
    assert model.selected_version_id == second
    assert model.features_for_version(first, "head") == []


@pytest.mark.parametrize("fault", (
    "not-quantity", "missing-source", "version-drift", "bad-role",
    "bad-version", "bad-feature-type",
))
def test_invalid_source_or_editor_cannot_partially_commit(fault):
    snapshot, model = _source("金庫型")
    values = {"version_id": model.selected_version_id, "role": "tail",
              "features": [_circle()]}
    if fault == "not-quantity":
        snapshot["active_mode"] = "set_bay"
    elif fault == "missing-source":
        snapshot.pop("quantity")
    elif fault == "version-drift":
        snapshot["quantity"]["versions"][0]["piece_count"] = 2
    elif fault == "bad-role":
        values["role"] = "door"
    elif fault == "bad-version":
        values["version_id"] = "quantity-v999"
    else:
        values["features"] = ["not-a-physical-hole"]
    previous = deepcopy((snapshot, model.snapshot(), values))
    with pytest.raises((ValueError, TypeError, AttributeError)):
        api.commit_operator_quantity_version_holes(snapshot, model, **values)
    assert (snapshot, model.snapshot(), values) == previous


def test_notification_failure_restores_live_version_without_second_notification():
    snapshot, _ = _source("受電箱")
    calls = []
    def notify():
        calls.append(model.features_for("head"))
        raise RuntimeError("UI notification rejected")
    model = QuantityModel.from_payload(snapshot["quantity"], on_change=notify)
    original_snapshot, original_model = deepcopy(snapshot), model.snapshot()
    with pytest.raises(RuntimeError, match="UI notification rejected"):
        _commit(snapshot, model, model.selected_version_id, [_circle()])
    assert len(calls) == 1 and calls[0] == [_circle()]
    assert snapshot == original_snapshot
    assert model.snapshot() == original_model


def test_committed_versions_survive_real_project_save_reload(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, write_project, read_project
    snapshot, model = _source("受電箱")
    first = model.selected_version_id
    second = model.add_version()
    model.set_piece_count(3)
    snapshot["quantity"] = model.snapshot()
    assert _commit(snapshot, model, first, [_circle(25)], role="tail")
    persisted = deepcopy(snapshot)
    persisted["quantity"] = model.snapshot()
    target = write_project(tmp_path / "quantity-version-holes.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": persisted,
    })
    restored = QuantityModel.from_payload(read_project(target)["snapshot"]["quantity"])
    assert restored.selected_version_id == second
    assert restored.features_for_version(first, "tail") == [_circle(25)]
    assert restored.features_for_version(second, "tail") == []
    assert restored.total_piece_count == 4


def test_real_gui_port_contains_only_one_public_engine_hole_transaction():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/quantity_version_ports.py").read_text(
                  encoding="utf-8",
              )
    block = source.split("        def commit():", 1)[1].split(
        "        win = host._open_unified_hole_editor(", 1,
    )[0]
    assert "manufacturing_api.commit_operator_quantity_version_holes(" in block
    assert "QuantityModel.from_payload(" not in block
    assert 'current["quantity"] =' not in block
    assert "require_valid_operator_quantity_features(" not in block
    assert "owner.set_version_features(" not in block
    assert 'version_id == model().selected_version_id' in block


def test_live_modeless_gui_port_retains_inactive_version_and_refresh_boundary(monkeypatch):
    from gui_modules.application.quantity_version_ports import quantity_ports

    snapshot, model = _source("受電箱")
    first = model.selected_version_id
    model.add_version()
    snapshot["quantity"] = model.snapshot()
    class Editor:
        def _open_unified_hole_editor(self, *args, **kwargs):
            self.kwargs = kwargs
            return self
        def scene_query(self):
            return None
    editor = Editor()
    intents, publishes = [], []
    workspace = SimpleNamespace(
        quantity_model=model, active_part="head",
        snapshot=lambda: {"active_mode": "quantity", "quantity": model.snapshot(),
                          "receiving_quantity_box": snapshot["receiving_quantity_box"]},
    )
    app = SimpleNamespace(
        designer_workspace=workspace, _phase6_input_snapshot=deepcopy(snapshot),
        _settings_values={}, _phase6_box_whd={"w": 800, "h": 1600, "d": 350},
        baseline_model_var=SimpleNamespace(get=lambda: "受電箱"),
        _scene_query_callback=editor.scene_query,
        _load_part_holes=lambda part: None,
        submit_update_intent=lambda *a, **kw: intents.append((a, kw)),
    )
    composition = SimpleNamespace(
        app=app, publish_live_state=lambda *a, **kw: publishes.append((a, kw)),
    )
    monkeypatch.setattr(
        api, "project_operator_quantity_endcap_hole_editor_geometry",
        lambda *a, **kw: SimpleNamespace(
            width=800, height=350, surface=object(), reference_guide=object(),
        ),
    )
    ports = quantity_ports(composition, None)
    ports["select"](first)
    ports["holes"]("head")
    staged = editor.kwargs["feature_list_override"]
    staged[:] = [_circle(12)]
    # Select another version while the editor stays open.
    second = next(x["version_id"] for x in model.snapshot()["versions"]
                  if x["version_id"] != first)
    ports["select"](second)
    intents.clear()
    editor.kwargs["sync_callback"]()
    assert model.selected_version_id == second
    assert model.features_for_version(first, "head") == [_circle(12)]
    assert model.features_for_version(second, "head") == []
    assert not intents  # Inactive version needs no immediate geometry rebuild.
    assert publishes  # Normal working-state publication still takes place.
