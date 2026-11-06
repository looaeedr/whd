# -*- coding: utf-8 -*-
"""#2517: Receiving NFB Confirm source qualification belongs to the public Engine.

The original Hole Editor and the standalone candidate manager must share the
same model/brand/physical-slot guard. This is a source draft decision, never
a FinalScene / CUTTING / DXF manufacturing approval.
"""
from copy import deepcopy
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import (
    OVERRIDE, new_nfb_ui1a_draft,
)
from ae_engine.receiving_nfb_ui1a_edits import (
    editable_nfb_draft,
    plan_receiving_nfb_editor_confirm as engine_owner,
)
from gui_modules.application import fold_designer_composition_receiving as gui


V5 = numeric_model_ref("士林", "2P400")
LEGACY = "400_140X257_107.dxf"


def _draft(model):
    return editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=([model], ""),
    ))


def _plan(draft, chosen, *, embedded):
    return manufacturing_api.plan_receiving_nfb_editor_confirm(
        draft, draft, [list(chosen), []], layer_count=1,
        embedded=embedded, parent_brand="士林",
    )


def test_both_public_facades_are_same_canonical_nfb_confirm_owner():
    assert manufacturing_api.plan_receiving_nfb_editor_confirm is engine_owner
    assert ae_engine.plan_receiving_nfb_editor_confirm is engine_owner
    assert "plan_receiving_nfb_editor_confirm" in ae_engine.__all__


def test_native_csv_editor_uses_real_brand_csv_and_exact_slot_multiset():
    draft = _draft(V5)
    before = deepcopy(draft)
    plan = _plan(draft, (V5,), embedded=True)
    assert plan.current_numeric_editor is True
    assert plan.has_source_models is True
    assert draft == before

    with pytest.raises(ValueError, match="選型與開孔設定不同步"):
        _plan(draft, (V5, V5), embedded=True)
    assert draft == before


def test_legacy_candidate_keeps_existing_filename_and_lossless_draft_gate():
    draft = _draft(LEGACY)
    plan = _plan(draft, (LEGACY,), embedded=False)
    assert not plan.current_numeric_editor
    assert plan.has_source_models
    with pytest.raises(ValueError, match="開關型號已不在廠牌 CSV"):
        _plan(draft, ("NOT_IN_INDEX.dxf",), embedded=False)

    rotated = deepcopy(draft)
    rotated["layers"][0]["rotation_deg"] = 90
    with pytest.raises(ValueError, match="NFB 草稿角度"):
        _plan(rotated, (LEGACY,), embedded=False)

    overridden = deepcopy(draft)
    overridden["layers"][0]["brand"] = {"mode": OVERRIDE, "value": "士林"}
    with pytest.raises(ValueError, match="品牌覆寫"):
        _plan(overridden, (LEGACY,), embedded=False)

    displaced = deepcopy(draft)
    displaced["layers"][0]["slots"][0]["manual_x_state"] = "UNVERIFIED_BASIS"
    displaced["layers"][0]["slots"][0]["manual_x_mm"] = 20
    with pytest.raises(ValueError, match="位移尚未正式提交"):
        _plan(displaced, (LEGACY,), embedded=False)


def test_numeric_cross_brand_identity_fails_without_relabeling_source():
    draft = _draft("nfbv5:東元:2P400")
    original = deepcopy(draft)
    with pytest.raises(ValueError, match="實際廠牌與 CSV 型號不符"):
        _plan(draft, ("nfbv5:東元:2P400",), embedded=True)
    assert draft == original


def test_empty_native_editor_has_no_source_and_no_manufacturing_grant():
    draft = _draft(LEGACY)
    draft["layers"][0]["slots"].clear()
    plan = _plan(draft, (), embedded=True)
    assert plan.has_source_models is False
    assert plan.current_numeric_editor is False
    assert not hasattr(plan, "manufacturing_ready")


def test_real_gui_confirm_only_consumes_public_engine_source_plan():
    source = inspect.getsource(gui)
    confirm = source.split("        def confirm():", 1)[1].split(
        "        buttons = ttk.Frame(frame)", 1
    )[0]
    assert "manufacturing_api.plan_receiving_nfb_editor_confirm(" in confirm
    assert "parse_numeric_model_ref" not in confirm
    assert "model_filenames(" not in confirm
    assert "effective_nfb_slot_brand(" not in confirm
    assert "resolve_receiving_nfb_model_spec(" not in confirm
    assert "list_receiving_nfb_model_refs(" not in confirm
    assert "editor_nfb_features_from_csv(" in confirm
