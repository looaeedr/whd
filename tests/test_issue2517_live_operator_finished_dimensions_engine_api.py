"""#2517: operator effective physical dimensions belong to Engine, not GUI."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_live_operator_finished_dimensions
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from phase6_manufacturing_adapter import operator_finished_dimensions_for_app


def _app(model="金庫型", *, snapshot=None, settings=None, whd=None, active="box_body"):
    return SimpleNamespace(
        active_part_key=active,
        _phase6_input_snapshot=snapshot if snapshot is not None else
            {"model": model, "w": 400, "h": 600, "d": 250, "t": 2},
        _settings_values=settings if settings is not None else {},
        _phase6_box_whd=whd if whd is not None else {},
        _phase6_corner_state={},
    )


def _engine(app, *, part_key=None, triangles=None):
    return resolve_live_operator_finished_dimensions(
        part_key or app.active_part_key,
        input_snapshot=app._phase6_input_snapshot,
        settings_values=app._settings_values,
        working_box=app._phase6_box_whd,
        triangles=triangles,
    )


def test_public_owner_is_engine_and_gui_is_narrow_request_adapter():
    assert manufacturing_api.resolve_live_operator_finished_dimensions is resolve_live_operator_finished_dimensions
    src = inspect.getsource(operator_finished_dimensions_for_app)
    assert "manufacturing_api.resolve_live_operator_finished_dimensions(" in src
    for forbidden in ("RECEIVING", "受電箱", 'for axis in ("w", "h", "d")', "settings.update(", "resolve_operator_finished_dimensions("):
        assert forbidden not in src
    import ae_engine.display_dimensions as source
    assert "phase6_" not in inspect.getsource(source.resolve_live_operator_finished_dimensions)
    assert "tkinter" not in inspect.getsource(source.resolve_live_operator_finished_dimensions)


@pytest.mark.parametrize("family", ["金庫型", "受電箱", "RECEIVING"])
def test_live_sparse_snapshot_and_settings_matches_actual_app_client(family):
    app = _app(family,
        snapshot={"model": family, "h": 600, "t": 2},
        settings={"t": 2},
        whd={"w": 800, "h": 1800, "d": 350})
    original = deepcopy((app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd))
    result = _engine(app)
    gui = operator_finished_dimensions_for_app(app)
    assert gui == result
    assert result[0] == pytest.approx(800)
    assert result[2] == pytest.approx(350)
    # H is a real, explicit snapshot value for Vault; Receiving reads working H.
    assert result[1] == pytest.approx(600 if family == "金庫型" else 1800)
    assert (app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd) == original


def test_receiving_live_working_dimensions_override_stale_settings_only():
    app = _app("受電箱",
        snapshot={"model":"受電箱","w":999,"h":1200,"d":300,"t":2},
        settings={"w":111,"h":222,"d":333,"t":2},
        whd={"w":800,"h":1600,"d":350})
    assert _engine(app) == pytest.approx((800,1600,350))
    assert operator_finished_dimensions_for_app(app) == pytest.approx((800,1600,350))
    app._phase6_box_whd["w"] = 820
    assert _engine(app)[0] == pytest.approx(820)


def test_vault_explicit_snapshot_does_not_take_working_box_as_new_authority():
    app = _app("金庫型",
        snapshot={"model":"金庫型","w":700,"h":1200,"d":300,"t":2},
        settings={"t":2},
        whd={"w":900,"h":1500,"d":450})
    assert _engine(app) == pytest.approx((700,1200,300))
    assert operator_finished_dimensions_for_app(app) == pytest.approx((700,1200,300))


def test_door_cell_keeps_existing_saved_physical_size():
    app = _app("受電箱",
        snapshot={"model":"受電箱","part_dimensions":{
            "door_c1_r1":{"width":335,"height":535}},
            "t":2},
        settings={"t":2},
        whd={"w":800,"h":1600,"d":350},active="door_c1_r1")
    assert _engine(app) == pytest.approx((335,535))
    assert operator_finished_dimensions_for_app(app) == pytest.approx((335,535))


def test_mesh_authority_and_nonfinite_thickness_refusal_share_real_engine():
    triangles = (((0.0,0.0,0.0),(100.0,0.0,0.0),(0.0,200.0,0.0)),)
    app = _app(active="door")
    assert _engine(app, triangles=triangles) == pytest.approx(
        resolve_operator_finished_dimensions("door",
            snapshot=app._phase6_input_snapshot,
            settings=app._settings_values, triangles=triangles, thickness=2.0)
    )
    assert operator_finished_dimensions_for_app(app, triangles=triangles) == pytest.approx(_engine(app, triangles=triangles))
    app._settings_values["t"] = float("nan")
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        _engine(app, triangles=triangles)
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        operator_finished_dimensions_for_app(app, triangles=triangles)
