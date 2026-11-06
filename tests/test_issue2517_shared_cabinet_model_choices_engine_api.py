"""#2517: Vault/Receiving one Engine model catalog, not separate GUI policies."""
from __future__ import annotations

import inspect
import json

from ae_engine import manufacturing_api as api
from ae_engine import list_cabinet_model_choices
from ae_engine import ae


def test_public_engine_catalog_preserves_vault_receiving_and_custom_order():
    models = api.list_cabinet_model_choices(["金庫型", "未知類型", " 金庫型 ", "試作箱"])
    assert models == ["金庫型", "試作箱", "受電箱", "自訂"]
    assert models == list_cabinet_model_choices(["金庫型", "未知類型", " 金庫型 ", "試作箱"])
    assert json.loads(json.dumps(models, ensure_ascii=False)) == models


def test_formula_receiving_appears_without_vault_baseline_and_ro_is_not_invented():
    assert api.list_cabinet_model_choices([]) == ["受電箱", "自訂"]
    assert "RO" not in api.list_cabinet_model_choices(["金庫型"])
    # Existing physical baseline folders remain explicit source choices.
    assert api.list_cabinet_model_choices(["RO"]) == ["RO", "受電箱", "自訂"]


def test_catalog_reads_live_baselines_in_engine_not_in_gui(monkeypatch):
    monkeypatch.setattr(ae, "get_baseline_list", lambda: ["金庫型", "金庫型"])
    assert api.list_cabinet_model_choices() == ["金庫型", "受電箱", "自訂"]
    monkeypatch.setattr(ae, "get_baseline_list", lambda: [])
    assert api.list_cabinet_model_choices() == ["受電箱", "自訂"]


def test_main_gui_and_fold_designer_share_catalog_and_preserve_project_model():
    from gui import Phase6ApplicationHost
    import fold_designer_bridge as bridge

    assert Phase6ApplicationHost._baseline_model_choices is not None
    source = inspect.getsource(Phase6ApplicationHost._baseline_model_choices)
    assert "manufacturing_api.list_cabinet_model_choices()" in source
    assert "get_baseline_list" not in source
    # Fold Designer consumes the model list from the same main-GUI snapshot,
    # additionally retaining the saved project model even if a source vanished.
    fold_source = inspect.getsource(bridge._phase6_prepare_predecessor_init)
    assert 'snapshot.get("baseline_models")' in fold_source
    assert "self._phase6_baseline_initial_model" in fold_source
