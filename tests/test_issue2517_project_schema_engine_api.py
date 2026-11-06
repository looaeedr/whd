"""#2517 Engine owns Phase6 Save/Reload schema and committed NFB decisions."""
from __future__ import annotations

from copy import deepcopy
import json
import inspect

import pytest

from ae_engine import manufacturing_api as api
import ae_engine.operator_project_persistence as owner
import phase6_project_file as gui


def test_public_api_vault_v1_and_receiving_v2_detached_save_reload(tmp_path):
    for model, schema in (
        ("金庫型", api.PROJECT_SCHEMA_V1),
        ("受電箱", api.PROJECT_SCHEMA_V2),
    ):
        request = {
            "schema": api.PROJECT_SCHEMA_V1,
            "snapshot": {"model": model, "w": 400, "h": 600, "d": 250, "t": 2},
            "final_geometry": {"fake": "preview"},
        }
        before = deepcopy(request)
        prepared = api.project_operator_project_for_write(request)
        assert request == before
        assert prepared["schema"] == schema
        assert prepared["final_geometry"] == {}
        restored = api.project_operator_project_for_read(prepared)
        assert restored["schema"] == schema
        assert restored["final_geometry"] == {}
        path = gui.write_project(tmp_path / (model + ".p6fold"), request)
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["schema"] == schema
        assert raw["final_geometry"] == {}
        assert gui.read_project(path)["schema"] == schema


def test_no_old_schema_nfb_smuggling_and_invalid_family_rejected():
    for schema in (api.PROJECT_SCHEMA_V2, api.PROJECT_SCHEMA_V3):
        with pytest.raises(ValueError, match="requires Receiving family"):
            api.validate_operator_project_payload({
                "schema": schema, "snapshot": {"model": "金庫型"},
            })
    for schema in (api.PROJECT_SCHEMA_V1, api.PROJECT_SCHEMA_V2):
        with pytest.raises(ValueError, match="old schema"):
            _force_submitted(schema)
    with pytest.raises(ValueError, match="has no committed"):
        api.validate_operator_project_payload({
            "schema": api.PROJECT_SCHEMA_V3,
            "snapshot": {"model": "受電箱"},
        }, for_read=True)


def _force_submitted(schema):
    # Simulate a source-only submitted NFB state without relying on a forged
    # JSON drawing: verify that the Engine gate is actually invoked.
    from unittest.mock import patch
    with patch.object(owner, "contains_submitted_nfb", return_value=True):
        return api.validate_operator_project_payload({
            "schema": schema, "snapshot": {"model": "受電箱"},
        }, for_read=True)


def test_bad_source_never_writes_a_project_file(tmp_path):
    path = tmp_path / "reject.p6fold"
    with pytest.raises(ValueError):
        gui.write_project(path, {
            "schema": api.PROJECT_SCHEMA_V3,
            "snapshot": {"model": "金庫型", "t": 2.0},
        })
    assert not path.exists()


def test_gui_codec_routes_schema_and_source_authority_only_via_public_api():
    assert gui.PROJECT_SCHEMA_V1 == api.PROJECT_SCHEMA_V1
    for fn, name in (
        (gui.validate_project, "validate_operator_project_payload"),
        (gui.write_project, "project_operator_project_for_write"),
        (gui.read_project, "project_operator_project_for_read"),
    ):
        assert "manufacturing_api." + name in inspect.getsource(fn)
    source = inspect.getsource(owner)
    assert "from phase6_" not in source
    assert "tkinter" not in source
