"""#2517 Fold Designer must not own physical Receiving 2D selector sources."""
from pathlib import Path

import pytest
from ae_engine import manufacturing_api as api


def test_vault_multidoor_base_plate_dimensions_are_engine_owned():
    snap = {
        "model": "金庫型",
        "door_layout_columns": [(600, [700, 300]), (400, [1000])],
        "base_plate_shrink_left": 55,
        "base_plate_shrink_right": 55,
        "base_plate_shrink_top": 30,
        "base_plate_shrink_bottom": 45,
    }
    actual = api.project_operator_multidoor_base_plate_dimensions(snap)
    assert dict(actual["base_plate_c1_r1"]) == {"width": 490, "height": 625}
    assert dict(actual["base_plate_c1_r2"]) == {"width": 490, "height": 225}
    assert dict(actual["base_plate_c2_r1"]) == {"width": 290, "height": 925}
    snap["base_plate_shrink_left"] = "invalid"
    assert api.project_operator_multidoor_base_plate_dimensions(snap)[
        "base_plate_c1_r1"
    ]["width"] == 490


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_has_exact_original_base_plate_not_phantom_door_cell(model):
    snapshot = {
        "model": model,
        "existing_parts": ("base_plate", "door"),
        "door_layout_columns": [(800, [1100, 500])],
    }
    identity = api.project_operator_base_navigation_identity(
        snapshot, snapshot["existing_parts"],
    )
    assert identity.receiving_single_base
    assert identity.preserve_navigation_root
    assert identity.source_parts == snapshot["existing_parts"]
    assert not identity.receiving_two_tier
    assert not api.project_operator_multidoor_base_plate_dimensions(snapshot)
    snapshot["nfb_config_submitted"] = True
    snapshot["nfb_config"] = {"layer_count": 2}
    two = api.project_operator_base_navigation_identity(snapshot, snapshot["existing_parts"])
    assert two.receiving_two_tier
    assert not two.preserve_navigation_root


def test_uncommitted_nfb_does_not_create_tiers_or_pad():
    snapshot = {
        "model": "受電箱", "w": 800, "t": 2,
        "nfb_config_submitted": False,
        "existing_parts": ("base_plate",),
        "nfb_config": {"layer_count": 2},
    }
    derived = api.project_operator_receiving_auxiliary_navigation(
        snapshot, available_parts=("base_plate",),
    )
    assert not derived.nfb_tier_profiles
    assert not derived.pad_profiles


def test_gui_derived_navigation_calls_public_api_instead_of_owning_physical_sources():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gui_modules/application/fold_designer_composition_shell_settings.py").read_text(
        encoding="utf-8"
    )
    segment = source.split("def sync_authoritative_derived_parts(")[1].split(
        "\ndef settings_service(", 1
    )[0]
    for name in (
        "project_operator_base_navigation_identity",
        "project_operator_multidoor_base_plate_dimensions",
        "project_operator_receiving_auxiliary_navigation",
    ):
        assert "manufacturing_api." + name in segment
    for forbidden in (
        "from ae_engine.receiving_nfb_base_assembly_xy import",
        "from ae_engine.receiving_base_plate_3d_profiles import",
        "from ae_engine.receiving_base_fixing_plate import",
        "from ae_engine.receiving_nfb_pad_operator_parts import",
        "derive_door_layout_cells(columns)",
        "committed_nfb_pad_draft_parts(candidate_source)",
    ):
        assert forbidden not in segment
    engine = (root / "ae_engine/operator_derived_navigation.py").read_text(
        encoding="utf-8"
    )
    # A data key named phase6_key and source documentation are not imports.
    # Only an actual reverse import would violate the Engine/GUI boundary.
    import ast
    module = ast.parse(engine)
    imports = (
        [name.name for node in ast.walk(module) if isinstance(node, ast.Import)
         for name in node.names]
        + [node.module or "" for node in ast.walk(module)
           if isinstance(node, ast.ImportFrom)]
    )
    assert not any(name.startswith(("gui_modules", "phase6_"))
                   for name in imports)
