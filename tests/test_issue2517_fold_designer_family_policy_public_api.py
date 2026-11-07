# -*- coding: utf-8 -*-
"""#2517: Fold Designer Family Policy and Registry reads use public Engine ports."""
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as owner


POLICY_NAMES = (
    "canonical_family_name",
    "family_fixes_box_body_structure",
    "box_body_profile_uses_outside_dimensions",
    "supports_bottom_wrap_controls",
    "endcap_fw_profile_uses_material_dimensions",
)
ROOT = Path(__file__).resolve().parents[1]


def test_public_family_policy_ports_are_original_engine_callables():
    for name in POLICY_NAMES:
        public = "operator_" + name
        original = getattr(owner, name)
        assert getattr(api, public) is original
        assert getattr(ae_engine, public) is original
        assert public in ae_engine.__all__
    assert api.build_relief_promotion_candidate is ae_engine.build_relief_promotion_candidate
    assert api.resolve_cabinet_type is ae_engine.resolve_cabinet_type


@pytest.mark.parametrize("model", ("金庫型", "受電箱", "UNKNOWN_FAMILY", ""))
def test_public_gui_and_engine_family_policy_have_identical_nonmutating_results(model):
    snapshot = {"model": model, "receiving_layout": {"sets": []}, "other": [3, 2, 1]}
    original = deepcopy(snapshot)
    for name in POLICY_NAMES:
        exposed = getattr(api, "operator_" + name)
        expected = getattr(owner, name)
        assert exposed(snapshot) == expected(snapshot)
        assert getattr(ae_engine, "operator_" + name)(snapshot) == expected(snapshot)
        assert snapshot == original


def test_fold_designer_gui_does_not_import_internal_family_policy_or_registry():
    bridge = (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")
    corner = (ROOT / "gui_modules/application/fold_designer_composition_assembly_corner.py").read_text(
        encoding="utf-8"
    )
    for source in (bridge, corner):
        assert "from ae_engine.cabinet_types import policy as cabinet_family_policy" not in source
        assert "cabinet_family_policy." not in source
    assert "manufacturing_api.operator_canonical_family_name(" in bridge
    # Corner Data now forwards its raw Family + physical topology to one
    # public Engine eligibility API, rather than projecting Family in the GUI.
    assert "manufacturing_api.operator_corner_data_back_panel_mode_applicable(" in corner
    assert "from ae_engine.cabinet_types.registry import" not in bridge
    assert "manufacturing_api.resolve_cabinet_type(model)" in bridge
    assert "from ae_engine.certified_relief_registry import" not in corner
    assert "manufacturing_api.build_relief_promotion_candidate" in corner
    session = (ROOT / "gui_modules/application/fold_designer_part_session.py").read_text(encoding="utf-8")
    assert "bridge.cabinet_family_policy." not in session
    assert "bridge.manufacturing_api.operator_endcap_fw_profile_uses_material_dimensions(" in session
    for suffix in POLICY_NAMES[1:-1]:
        assert "manufacturing_api.operator_" + suffix + "(" in bridge



def test_remaining_fold_designer_family_capability_ports_are_public_engine():
    from types import SimpleNamespace
    from gui_modules.application import fold_designer_composition_state as composition

    state_gui = (ROOT / "gui_modules/application/fold_designer_composition_state.py").read_text(
        encoding="utf-8"
    )
    settings_gui = (ROOT / "gui_modules/application/fold_designer_composition_settings.py").read_text(
        encoding="utf-8"
    )
    for gui_code in (state_gui, settings_gui):
        assert "from ae_engine.cabinet_types import policy as cabinet_family_policy" not in gui_code
        assert "cabinet_family_policy." not in gui_code
    assert "canonical_family_name=manufacturing_api.operator_canonical_family_name" in state_gui
    assert "manufacturing_api.operator_supports_bottom_wrap_controls(" in settings_gui

    for family in ("受電箱", "金庫型", "UNKNOWN_FAMILY", ""):
        snapshot = {"model": family, "source": {"unchanged": [1, 2]}}
        before = deepcopy(snapshot)
        holder = type("Context", (), {"app": SimpleNamespace(_phase6_input_snapshot=snapshot)})()
        capabilities = composition.build_capability_owners(holder)
        expected = owner.canonical_family_name(snapshot) == "受電箱"
        assert capabilities.receiving.applicable() == expected
        assert api.operator_canonical_family_name(snapshot) == owner.canonical_family_name(snapshot)
        assert api.operator_supports_bottom_wrap_controls(snapshot) == owner.supports_bottom_wrap_controls(snapshot)
        assert snapshot == before
