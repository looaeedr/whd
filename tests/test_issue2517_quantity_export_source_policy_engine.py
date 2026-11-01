"""#2517: source policy in headless Engine, GUI only consumes API decision."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from gui_modules.project import export_actions


def _versions(*rows):
    return {"versions": [dict(version_id=f"quantity-v{i+1}", **row)
                         for i, row in enumerate(rows)]}


def _snapshot(model="受電箱", *rows):
    return {"model": model, "quantity": _versions(*rows)}


def _submitted(name):
    return {"nfb_config_submitted": True,
            "nfb_config": {"holes": [{"model_filename": name}]}}


def test_current_numeric_csv_version_family_is_engine_owned_and_read_only():
    snapshot = _snapshot("受電箱", _submitted("nfbv5:士林:SLA"),
                         _submitted("nfbv5:士林:SLB"))
    live = {"quantity": deepcopy(snapshot["quantity"])}
    pristine = deepcopy((snapshot, live))
    decision = manufacturing_api.plan_quantity_export_source(snapshot, live)
    assert isinstance(decision, manufacturing_api.QuantityExportSourceDecision)
    assert decision.use_current_csv_export is True
    assert decision.submitted_version_ids == ("quantity-v1", "quantity-v2")
    assert (snapshot, live) == pristine
    with pytest.raises((AttributeError, TypeError)):
        decision.use_current_csv_export = False


def test_old_legacy_source_unsubmitted_and_other_family_do_not_claim_current_csv():
    legacy = _snapshot("受電箱", _submitted("nfb_old.dxf"), _submitted("nfb_old2.dxf"))
    assert not manufacturing_api.plan_quantity_export_source(
        legacy, {"quantity": deepcopy(legacy["quantity"])}
    ).use_current_csv_export
    blank = _snapshot("受電箱", {"nfb_config_submitted": False})
    assert not manufacturing_api.plan_quantity_export_source(
        blank, {"quantity": deepcopy(blank["quantity"])}
    ).use_current_csv_export
    vault = _snapshot("金庫型", _submitted("nfbv5:士林:SLA"))
    assert not manufacturing_api.plan_quantity_export_source(
        vault, {"quantity": deepcopy(vault["quantity"])}
    ).use_current_csv_export


def test_numeric_and_legacy_in_same_quantity_batch_fail_closed():
    mixed = _snapshot("受電箱", _submitted("nfbv5:士林:SLA"),
                      _submitted("legacy_file.dxf"))
    with pytest.raises(ValueError, match="混用數值 CSV"):
        manufacturing_api.plan_quantity_export_source(
            mixed, {"quantity": deepcopy(mixed["quantity"])}
        )


@pytest.mark.parametrize("mutation", [
    lambda x: x["versions"][0]["nfb_config"]["holes"][0].update(
        model_filename="nfbv5:士林:OTHER"),
    lambda x: x["versions"][0].update(nfb_config_submitted=False),
    lambda x: x["versions"].append({
        "version_id": "quantity-v2", **_submitted("nfbv5:士林:SLB")}),
])
def test_saved_and_live_submissions_cannot_be_borrowed_between_versions(mutation):
    saved = _snapshot("受電箱", _submitted("nfbv5:士林:SLA"))
    live = deepcopy(saved["quantity"])
    mutation(live)
    with pytest.raises(ValueError, match="NFB 數量版本與目前工作狀態不一致"):
        manufacturing_api.plan_quantity_export_source(
            saved, {"quantity": live},
        )


def test_malformed_submitted_source_cannot_bypass_engine_gate():
    original = _snapshot("受電箱", _submitted("nfbv5:士林:SLA"))
    same = deepcopy(original["quantity"])
    same["versions"][0]["version_id"] = ""
    original["quantity"] = deepcopy(same)
    with pytest.raises(ValueError, match="穩定來源身分"):
        manufacturing_api.plan_quantity_export_source(
            original, {"quantity": same},
        )


def test_gui_quantity_export_only_uses_public_engine_policy():
    source = inspect.getsource(export_actions._export_selected_resolved_parts)
    assert "manufacturing_api.plan_quantity_export_source(" in source
    assert "source_policy.use_current_csv_export" in source
    assert "export_current_csv_quantity_manufacturing" in source
    assert "def submitted_facts(" not in source
    assert "parse_numeric_model_ref" not in source
    assert "numeric_submissions" not in source
