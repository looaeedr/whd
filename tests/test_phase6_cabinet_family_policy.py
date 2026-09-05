from pathlib import Path


def test_generic_family_policy_resolves_receiving_and_vault_capabilities():
    from ae_engine.cabinet_types import policy
    from phase6_box_body_structure import BoxBodyStructureType, default_box_body_structure_state

    receiving = {"model": "受電箱", "t": 2.0}
    vault = {"model": "金庫型", "t": 2.0}

    assert policy.canonical_family_name(receiving) == "受電箱"
    assert policy.canonical_family_name(vault) == "金庫型"
    assert policy.endcap_depth_comp_t(receiving) == 2.0
    assert policy.endcap_depth_comp_t(vault) == 3.0
    assert policy.baseline_feature_model_name("受電箱") == "金庫型"
    assert policy.baseline_feature_model_name("金庫型") == "金庫型"
    assert policy.door_nameplate_center_datum_top("受電箱") == 140.0
    assert policy.door_nameplate_center_datum_top("金庫型") is None

    rstate = policy.resolve_box_body_structure_state(receiving, default_box_body_structure_state())
    assert rstate["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    assert rstate["locked"] is True
    baseline = default_box_body_structure_state()
    vstate = policy.resolve_box_body_structure_state(vault, baseline)
    assert vstate == baseline


def test_policy_exposes_geometry_parameters_without_owning_registry_answers():
    from ae_engine.cabinet_types import policy
    from phase6_box_body_structure import default_box_body_structure_state

    receiving = {"model": "受電箱"}
    state = policy.resolve_box_body_structure_state(receiving, default_box_body_structure_state())
    assert policy.effective_endcap_bottom_fw(receiving, state, thickness=2.0, default_fw=29.0) == 17.0
    changed = policy.set_bottom_relief_reserves(receiving, state, reserve_u=3.0, reserve_v=1.5)
    assert policy.bottom_relief_reserves(receiving, changed) == (3.0, 1.5)
    assert policy.bottom_relief_registry_applicable(receiving, changed) is True

    vault = {"model": "金庫型"}
    assert policy.effective_endcap_bottom_fw(vault, state, thickness=2.0, default_fw=25.0) == 25.0
    assert policy.bottom_relief_registry_applicable(vault, state) is False


def test_policy_exposes_family_fold_semantics_without_ui_family_branch():
    from ae_engine.cabinet_types import policy

    profile = [
        {"phase6_key": "zl1", "len": 24.0, "angle": 90},
        {"phase6_key": "w", "len": 800.0, "angle": 90},
        {"phase6_key": "zr1", "len": 12.0},
    ]
    receiving = {"model": "受電箱"}
    vault = {"model": "金庫型"}
    transformed = policy.transform_box_body_profile(receiving, profile)
    assert [row["phase6_key"] for row in transformed] == ["zl1", "w"]
    assert "angle" not in transformed[-1]
    assert policy.box_body_profile_uses_outside_dimensions(receiving) is True
    assert policy.endcap_fw_profile_uses_material_dimensions(receiving) is True
    assert policy.box_body_profile_uses_outside_dimensions(vault) is False
    assert policy.endcap_fw_profile_uses_material_dimensions(vault) is False
    assert policy.family_fixes_box_body_structure(receiving) is True
    assert policy.family_fixes_box_body_structure(vault) is False


def test_mechanical_layers_do_not_import_receiving_module_directly():
    files = (
        "phase6_fold_profiles.py",
        "phase6_endcap_semantics.py",
        "ae_engine/manufacturing_api.py",
    )
    violations = []
    for name in files:
        source = Path(name).read_text(encoding="utf-8")
        if "cabinet_types.receiving" in source or "cabinet_types import receiving" in source:
            violations.append(name)
    assert violations == []


def test_policy_module_stays_out_of_ui_project_and_registry_ownership():
    from ae_engine.cabinet_types import policy

    source = Path(policy.__file__).read_text(encoding="utf-8")
    forbidden = ("tkinter", "phase6_project_session", "phase6_project_controller", "certified_relief_registry", "manufacturing_api")
    assert not [name for name in forbidden if name in source]


def test_gui_and_bridge_use_family_facade_not_direct_receiving_imports():
    violations = []
    for name in ("gui.py", "fold_designer_bridge.py"):
        source = Path(name).read_text(encoding="utf-8")
        if "cabinet_types.receiving" in source or "cabinet_types import receiving" in source:
            violations.append(name)
    assert violations == []
