# -*- coding: utf-8 -*-
"""#1504 AC-21/SWT-14: real CURRENT CSV quantity-version partial evidence.

This proves physical V5 source provenance, independent version copies,
three-tier transient UI inheritance, .p6fold persistence, and real original
Tk single-box brand selection. A full two-old-project Windows operator UAT
remains separate and must not be inferred from these regression tests.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_refs, parse_numeric_model_ref
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, NEEDS_RESELECTION, new_nfb_ui1a_draft,
    set_nfb_layer_brand, set_nfb_slot_brand, select_nfb_slot_model,
    reconcile_set_brand, effective_nfb_slot_brand, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from phase6_quantity_model import QuantityModel, SCHEMA_V2, SCHEMA_V3
from phase6_project_file import PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V3, write_project, read_project


def _refs():
    shihlin = numeric_model_refs("士林")
    teco = numeric_model_refs("東元")
    assert shihlin and teco
    assert parse_numeric_model_ref(shihlin[0])[0] == "士林"
    assert parse_numeric_model_ref(teco[0])[0] == "東元"
    return shihlin[0], teco[0]


def _config(ref, x, *, brand_mode=INHERIT):
    brand, _ = parse_numeric_model_ref(ref)
    return {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "nfb:quantity:upper:one",
            "model_filename": ref,
            "source_brand": brand,
            "brand_mode": brand_mode,
            "rotation_deg": 90,
            "manual_x_mm": x,
            "manual_x_state": "CONFIRMED",
            "datum_revision": "operator-physical-version",
            "datum_snapshot": {"w": 800, "owner": "upper"},
        }],
    }


def _save(q, path):
    return write_project(path, {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "受電箱",
            "active_mode": "quantity",
            "quantity": q.snapshot(),
            "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
        },
    })


def test_ac21_swt14_current_v5_each_version_model_brand_and_operator_basis_are_independent(
    tmp_path,
):
    a, b = _refs()
    model = QuantityModel()
    first = model.selected_version_id
    model.set_version_nfb_config(first, submitted=True,
                                 config=_config(a, 0))
    before = deepcopy(model.nfb_config_for_version(first))
    second = model.add_version()
    cloned = model.nfb_config_for_version(second)["nfb_config"]["holes"][0]
    assert cloned["model_filename"] == a
    assert cloned["source_brand"] == "士林"
    assert cloned["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert cloned["manual_x_mm"] == 0
    assert cloned["rotation_deg"] == 90
    assert model.nfb_config_for_version(first) == before
    model.set_version_nfb_config(
        second, submitted=True, config=_config(b, 180.25, brand_mode=OVERRIDE)
    )
    assert model.nfb_config_for_version(first) == before
    second_before = deepcopy(model.nfb_config_for_version(second))
    assert second_before["nfb_config"]["holes"][0]["source_brand"] == "東元"
    assert second_before["nfb_config"]["holes"][0]["brand_mode"] == OVERRIDE
    assert second_before["nfb_config"]["holes"][0]["manual_x_mm"] == 180.25
    assert model.snapshot()["schema"] == SCHEMA_V2

    path = _save(model, tmp_path / "independent-versions.p6fold")
    reopened = read_project(path)
    assert reopened["schema"] == PROJECT_SCHEMA_V3
    restored = QuantityModel.from_payload(reopened["snapshot"]["quantity"])
    assert restored.nfb_config_for_version(first) == before
    assert restored.nfb_config_for_version(second) == second_before
    restored.set_version_nfb_config(second, submitted=False)
    assert restored.nfb_config_for_version(first) == before
    assert restored.nfb_config_for_version(second) == {}
    assert model.nfb_config_for_version(second) == second_before
    assert model.nfb_config_for_version(first) == before


def test_ac21_swt14_three_tier_current_csv_brand_inheritance_never_rewrites_model():
    a, b = _refs()
    draft = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=2,
        model_layers=([a, a], [a]),
    )
    original = deepcopy(draft)
    draft = set_nfb_layer_brand(draft, 0, mode=OVERRIDE, value="東元")
    draft = set_nfb_slot_brand(draft, 0, 0, mode=OVERRIDE, value="士林")
    draft = select_nfb_slot_model(draft, 0, 1, b, catalog={"東元": (b,)})
    assert [effective_nfb_slot_brand(draft, 0, slot) for slot in (0, 1)] == [
        "士林", "東元",
    ]
    assert effective_nfb_slot_brand(draft, 1, 0) == "士林"
    preview = nfb_ui1a_preview(
        draft, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert [u["status"] for row in preview["layers"] for u in row["slots"]] == [
        "MODEL_SELECTED", "MODEL_SELECTED", "MODEL_SELECTED",
    ]
    changed_parent = reconcile_set_brand(draft, "東元")
    assert [effective_nfb_slot_brand(changed_parent, 0, i) for i in (0, 1)] == [
        "士林", "東元",
    ]
    assert effective_nfb_slot_brand(changed_parent, 1, 0) == "東元"
    stale = nfb_ui1a_preview(
        changed_parent, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert stale["layers"][1]["slots"][0]["status"] == NEEDS_RESELECTION
    assert changed_parent["layers"][1]["slots"][0]["filename"] == a
    assert changed_parent["layers"][1]["slots"][0]["source_brand"] == "士林"
    assert original["set_brand"] == "士林"
    assert not stale["can_manufacture"]
    assert not stale["has_absolute_x"]


def test_ac21_swt14_invalid_cross_brand_current_v5_submission_is_atomic():
    a, b = _refs()
    model = QuantityModel()
    version = model.selected_version_id
    model.set_version_nfb_config(version, submitted=True, config=_config(a, 0))
    before = deepcopy(model.snapshot())
    invalid = _config(b, 180.25)
    invalid["holes"][0]["source_brand"] = "士林"
    with pytest.raises(ValueError, match="mismatch"):
        model.set_version_nfb_config(version, submitted=True, config=invalid)
    assert model.snapshot() == before
    returned = model.nfb_config_for_version(version)
    returned["nfb_config"]["holes"][0]["model_filename"] = b
    returned["nfb_config"]["holes"][0]["datum_snapshot"]["w"] = -1
    assert model.snapshot() == before
    assert normalize_nfb_config(_config(a, 0))["holes"][0]["source_brand"] == "士林"


def test_ac21_swt14_quantity_selected_version_parent_brand_is_single_owner(tmp_path):
    from ae_engine.receiving_quantity_box import project_common_box
    a,b=_refs()
    q=QuantityModel()
    first=q.selected_version_id
    q.set_version_nfb_config(first, submitted=True, config=_config(a, 0))
    second=q.add_version()
    q.set_version_nfb_config(second, submitted=True,
                             config=_config(b, 180, brand_mode=OVERRIDE))
    old_first=deepcopy(q.nfb_config_for_version(first))
    old_second=deepcopy(q.nfb_config_for_version(second))
    assert q.set_version_nfb_parent_brand(
        second, "東元", legacy_default="士林",
    )
    assert q.snapshot()["schema"] == SCHEMA_V3
    assert q.nfb_parent_brand_for_version(first) == "士林"
    assert q.nfb_parent_brand_for_version(second) == "東元"
    assert q.nfb_config_for_version(first) == old_first
    assert q.nfb_config_for_version(second) == old_second
    base={"model":"受電箱","active_mode":"quantity",
          "receiving_quantity_box":{"w":800,"h":1600,"d":350,
                                    "switch_brand":"士林"},
          "quantity":q.snapshot()}
    assert project_common_box(base)["receiving_layout"]["sets"][0]["switch_brand"]=="東元"
    q.select(first)
    base["quantity"]=q.snapshot()
    assert project_common_box(base)["receiving_layout"]["sets"][0]["switch_brand"]=="士林"
    q.set_version_nfb_parent_brand(first,"東元",legacy_default="士林")
    assert q.nfb_parent_brand_for_version(second) == "東元"
    assert q.nfb_config_for_version(second) == old_second
    q.set_version_nfb_parent_brand(first,"士林",legacy_default="士林")
    q.select(second)
    third=q.add_version()
    assert q.nfb_parent_brand_for_version(third)=="東元"
    assert q.nfb_config_for_version(third)["nfb_config"]["holes"][0][
        "manual_x_state"]=="RECONFIRM_REQUIRED"
    q.set_version_nfb_parent_brand(third,"士林",legacy_default="士林")
    assert q.nfb_parent_brand_for_version(second)=="東元"
    raw=q.snapshot()
    path=write_project(tmp_path/"quantity-per-version-parent.p6fold",{
        "schema":PROJECT_SCHEMA_V1,"snapshot":{**base,"quantity":raw},
    })
    loaded=read_project(path)["snapshot"]
    reloaded=QuantityModel.from_payload(loaded["quantity"])
    assert reloaded.nfb_parent_brand_for_version(first)=="士林"
    assert reloaded.nfb_parent_brand_for_version(second)=="東元"
    assert reloaded.nfb_parent_brand_for_version(third)=="士林"
    assert reloaded.nfb_config_for_version(second)==old_second
    assert loaded["receiving_quantity_box"]["switch_brand"]=="士林"
    assert project_common_box(loaded)["receiving_layout"]["sets"][0]["switch_brand"]=="士林"


def test_ac21_swt14_original_gui_brand_selector_uses_selected_version_only():
    gui=(Path(__file__).resolve().parents[1] /
         "gui_modules/application/fold_designer_composition_receiving.py"
         ).read_text(encoding="utf-8")
    block=gui.split("    def single_brand():",1)[1].split(
        "    def set_global_brand(value):",1)[0]
    assert "quantity.selected_version_id" in block
    assert "quantity.nfb_parent_brand_for_version(" in block
    assert "quantity.set_version_nfb_parent_brand(" in block
    assert 'candidate["quantity"] = quantity.snapshot()' in block
    assert 'update_common_box(source, {"switch_brand": value})' not in block
    assert 'get_brand=(single_brand if single else' in gui
    assert 'set_brand=set_single_brand if single else set_global_brand' in gui
    # Neither quantity per-version parent nor Set/Bay parent may put another
    # editable brand authority INSIDE canonical NFBConfig.
    persistence=(Path(__file__).resolve().parents[1] /
                 "ae_engine/receiving_nfb_persistence.py").read_text(
                     encoding="utf-8")
    assert 'if "brand" in value or "switch_brand" in value:' in persistence


def test_ac21_swt14_invalid_parent_brand_and_old_v2_migrate_without_mutation():
    a,_=_refs()
    q=QuantityModel()
    original=q.selected_version_id
    q.set_version_nfb_config(original,submitted=True,config=_config(a,0))
    before=deepcopy(q.snapshot())
    with pytest.raises(ValueError,match="品牌"):
        q.set_version_nfb_parent_brand(original,"FAKE",
                                       legacy_default="士林")
    assert q.snapshot()==before
    assert q.snapshot()["schema"]==SCHEMA_V2
    legacy=QuantityModel.from_payload(before)
    assert legacy.nfb_parent_brand_for_version(original,
                                               legacy_default="士林")=="士林"
    legacy.set_version_nfb_parent_brand(original,"東元",
                                         legacy_default="士林")
    assert legacy.snapshot()["schema"]==SCHEMA_V3
    assert before["schema"]==SCHEMA_V2
    assert legacy.nfb_config_for_version(original)==q.nfb_config_for_version(original)



def test_ac21_swt14_changed_quantity_parent_marks_inherited_v5_model_reselect():
    from phase6_quantity_model import quantity_inherited_nfb_brand_conflicts
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_v5_part_only_manufacturing import _current_single_tier_csv_holes
    a,b=_refs()
    q=QuantityModel()
    first=q.selected_version_id
    q.set_version_nfb_config(first,submitted=True,config=_config(a,0))
    q.set_version_nfb_parent_brand(first,"東元",legacy_default="士林")
    data={"model":"受電箱","active_mode":"quantity",
          "receiving_quantity_box":{"w":800,"h":1600,"d":350,
                                    "switch_brand":"士林"},
          "quantity":q.snapshot(),"nfb_config_submitted":True,
          "nfb_config":q.nfb_config_for_version(first)["nfb_config"]}
    original=deepcopy(data)
    assert quantity_inherited_nfb_brand_conflicts(data)==(
        "nfb:quantity:upper:one",
    )
    with pytest.raises(ValueError,match="NEEDS_RESELECTION"):
        _submitted_csv_holes(data)
    with pytest.raises(ValueError,match="NEEDS_RESELECTION"):
        _current_single_tier_csv_holes(data,"upper")
    assert data==original
    override=deepcopy(data)
    q.set_version_nfb_config(first,submitted=True,
                             config=_config(a,0,brand_mode=OVERRIDE))
    override["quantity"]=q.snapshot()
    override["nfb_config"]=q.nfb_config_for_version(first)["nfb_config"]
    assert quantity_inherited_nfb_brand_conflicts(override)==()
    # Existing explicit per-unit override remains an independent source.
    assert parse_numeric_model_ref(override["nfb_config"]["holes"][0][
        "model_filename"])[0]=="士林"


def test_ac21_swt14_quantity_change_parent_preserves_model_and_no_new_ready():
    from phase6_quantity_model import quantity_inherited_nfb_brand_conflicts
    a,_=_refs()
    q=QuantityModel()
    first=q.selected_version_id
    q.set_version_nfb_config(first,submitted=True,config=_config(a,0))
    first_before=deepcopy(q.nfb_config_for_version(first))
    second=q.add_version()
    q.set_version_nfb_parent_brand(second,"東元",legacy_default="士林")
    result=q.snapshot()
    assert q.nfb_config_for_version(first)==first_before
    assert result["versions"][0]["nfb_parent_brand"]=="士林"
    assert result["versions"][1]["nfb_parent_brand"]=="東元"
    assert "manufacturing_verified" not in str(result)
    scope={"active_mode":"quantity","quantity":result,
           "receiving_quantity_box":{"w":800,"h":1600,"d":350,
                                     "switch_brand":"士林"}}
    assert quantity_inherited_nfb_brand_conflicts(scope)==(
        "nfb:quantity:upper:one",
    )
    q.select(first)
    scope["quantity"]=q.snapshot()
    assert quantity_inherited_nfb_brand_conflicts(scope)==()


def test_ac21_swt14_real_tk_single_brand_selector_scopes_two_versions(monkeypatch):
    """Actual Single GUI combobox must write only the selected Quantity version.

    Unlike source-string checks, this follows the operator's Tk event through
    original Receiving mode, workspace transaction and re-opened dialog.
    """
    import tkinter as tk
    from tkinter import messagebox
    import gui
    import fold_designer_bridge as bridge
    from ae_engine.receiving_quantity_box import BOX_KEY

    warnings = []
    monkeypatch.setattr(messagebox, "showwarning",
                        lambda *args, **kw: warnings.append(args))
    monkeypatch.setattr(messagebox, "showerror",
                        lambda *args, **kw: warnings.append(args))
    root = tk.Tk()
    root.withdraw()
    window = None
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        root.update()

        window = bridge._phase6_open_receiving_single_settings(app)
        root.update()
        assert window.title() == "單只設定"
        assert app.designer_workspace.active_mode == "quantity"
        first = app.designer_workspace.quantity_model.selected_version_id
        brand = window._receiving_multi_brand_selector
        assert brand.get() == "士林"
        brand.set("東元")
        brand.event_generate("<<ComboboxSelected>>")
        root.update()

        saved = app.designer_workspace.snapshot()["quantity"]
        model = QuantityModel.from_payload(saved)
        assert model.snapshot()["schema"] == SCHEMA_V3
        assert model.nfb_parent_brand_for_version(first) == "東元"
        # Common physical W/H/D box remains immutable as NFB parent authority.
        assert app._phase6_input_snapshot[BOX_KEY]["switch_brand"] == "士林"
        window._receiving_multi_close()
        window = None
        root.update()

        # Deep-copy from first version, then change only second via REAL GUI.
        second = app.designer_workspace.quantity_model.add_version()
        assert second != first
        window = bridge._phase6_open_receiving_single_settings(app)
        root.update()
        brand = window._receiving_multi_brand_selector
        assert brand.get() == "東元"
        brand.set("士林")
        brand.event_generate("<<ComboboxSelected>>")
        root.update()

        q = QuantityModel.from_payload(app.designer_workspace.snapshot()["quantity"])
        assert q.nfb_parent_brand_for_version(first) == "東元"
        assert q.nfb_parent_brand_for_version(second) == "士林"
        assert app._phase6_input_snapshot[BOX_KEY]["switch_brand"] == "士林"
        window._receiving_multi_close()
        window = None
        root.update()

        app.designer_workspace.quantity_model.select(first)
        window = bridge._phase6_open_receiving_single_settings(app)
        root.update()
        assert window._receiving_multi_brand_selector.get() == "東元"
        assert not warnings
    finally:
        if window is not None and window.winfo_exists():
            window.destroy()
        root.destroy()
