"""#2517 Quantity EndCap editor and commit must share the manufacturing T source."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.quantity_version_ports import quantity_ports


def _source(*, thickness="1.6"):
    model = QuantityModel()
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "t": thickness, "w": 990, "h": 1850, "d": 490,
        "receiving_quantity_box": {"w": 920, "h": 1800, "d": 430},
        "quantity": model.snapshot(),
    }
    return snapshot, model


def test_public_engine_quantity_editor_uses_same_confirmed_t_after_save_reload(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

    snapshot, _ = _source()
    settings = {"t": 2.5, "w": 700, "d": 300}
    working = {"w": 850, "d": 370}
    before = deepcopy((snapshot, settings, working))
    canonical = api.project_operator_manufacturing_request_snapshot(
        snapshot, settings, working,
    )
    assert canonical["t"] == 1.6
    projected = api.project_operator_quantity_endcap_hole_editor_geometry(
        canonical, role="head",
    )
    expected = api.project_operator_hole_editor_endcap(
        "head", width=920, depth=430, thickness=1.6,
    )
    assert projected == expected
    target = write_project(tmp_path / "quantity-t-source.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": snapshot,
    })
    restored = read_project(target)["snapshot"]
    from_disk = api.project_operator_manufacturing_request_snapshot(
        restored, settings, working,
    )
    assert api.project_operator_quantity_endcap_hole_editor_geometry(
        from_disk, role="head",
    ) == projected
    assert (snapshot, settings, working) == before


@pytest.mark.parametrize("bad", (None, True, False, 0, -2, "nan", "inf"))
def test_quantity_editor_refuses_explicit_invalid_thickness_instead_of_settings_fallback(bad):
    source, _ = _source(thickness=bad)
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_operator_quantity_endcap_hole_editor_geometry(source, role="tail")
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_operator_manufacturing_request_snapshot(
            source, {"t": 2}, {},
        )


def test_quantity_editor_missing_t_cannot_invent_two_mm():
    snapshot, _ = _source()
    snapshot.pop("t")
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_operator_quantity_endcap_hole_editor_geometry(
            snapshot, role="head",
        )
    # An explicitly supplied, valid Settings-only legacy source can still
    # be projected via the *same* public Engine request contract.
    complete = api.project_operator_manufacturing_request_snapshot(
        snapshot, {"t": "1.75"}, {},
    )
    projected = api.project_operator_quantity_endcap_hole_editor_geometry(
        complete, role="head",
    )
    assert projected == api.project_operator_hole_editor_endcap(
        "head", width=920, depth=430, thickness=1.75,
    )


def test_real_gui_quantity_editor_and_commit_use_persisted_t_not_stale_settings(monkeypatch):
    snapshot, model = _source()
    original_snapshot = deepcopy(snapshot)
    hole = CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(0, 0))
    calls, committed_t, published = [], [], []

    class Editor:
        def scene(self):
            return None

        def _open_unified_hole_editor(self, *args, **kwargs):
            calls.append((args, kwargs))
            return self

    editor = Editor()
    workspace = SimpleNamespace(
        quantity_model=model, active_part="head",
        snapshot=lambda: {"active_mode": "quantity", "quantity": model.snapshot()},
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot=deepcopy(snapshot),
        _settings_values={"t": 2.5, "w": 750, "d": 300},
        _phase6_box_whd={"w": 860, "d": 365},
        baseline_model_var=SimpleNamespace(get=lambda: "受電箱"),
        _scene_query_callback=editor.scene,
        _load_part_holes=lambda *_: None,
        submit_update_intent=lambda *a, **kw: published.append((a, kw)),
    )
    composition = SimpleNamespace(
        app=app, publish_live_state=lambda *a, **kw: published.append((a, kw)),
    )
    original_commit = api.commit_operator_quantity_version_holes

    def observe_commit(source, owner, **kwargs):
        committed_t.append(source["t"])
        return original_commit(source, owner, **kwargs)

    monkeypatch.setattr(api, "commit_operator_quantity_version_holes", observe_commit)
    ports = quantity_ports(composition, None)
    ports["holes"]("head")
    assert len(calls) == 1
    args, kwargs = calls[0]
    projected = api.project_operator_quantity_endcap_hole_editor_geometry(
        api.project_operator_manufacturing_request_snapshot(
            snapshot, app._settings_values, app._phase6_box_whd,
        ), role="head",
    )
    assert args[2:] == (projected.surface, projected.width, projected.height)
    assert kwargs["reference_guide"] == projected.reference_guide

    kwargs["feature_list_override"].append(hole)
    kwargs["sync_callback"]()
    assert committed_t == [1.6]
    assert model.features_for("head") == [hole]
    assert app._phase6_input_snapshot["t"] == original_snapshot["t"]
    assert app._settings_values["t"] == 2.5
    assert published

    app._phase6_input_snapshot["t"] = True
    with pytest.raises(ValueError, match="T 包外尺寸"):
        ports["holes"]("head")
    assert len(calls) == 1
    assert model.features_for("head") == [hole]
