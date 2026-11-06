"""#2517 Engine source must not reverse-import Phase6 compatibility facades."""
from pathlib import Path
import ast

import ae_engine.box_body_piece_features as piece_features
from ae_engine.box_body_structure_state import (
    BackPanelMode, BoxBodyStructureType, back_panel_mode,
    normalize_box_body_structure_state, side_rear_bend_material_length,
)
from ae_engine.box_body_editor_readback import formed_box_body_fw_widths
from ae_engine.receiving_quantity_versions import quantity_inherited_nfb_brand_conflicts
from ae_engine.manufacturing_api import (
    BoxBodyStructureType as PublicStructure,
    BackPanelMode as PublicBackPanel,
    quantity_inherited_nfb_brand_conflicts as PublicNfbConflicts,
)
from phase6_box_body_structure import (
    BoxBodyStructureType as LegacyStructure,
    BackPanelMode as LegacyBackPanel,
    side_rear_bend_material_length as LegacyRearBend,
)
from phase6_fold_profiles import formed_box_body_fw_widths as LegacyFormedFw
from phase6_quantity_model import quantity_inherited_nfb_brand_conflicts as LegacyNfbConflicts


def test_legacy_phase6_names_are_exact_canonical_engine_owners():
    assert BoxBodyStructureType is PublicStructure is LegacyStructure
    assert BackPanelMode is PublicBackPanel is LegacyBackPanel
    assert side_rear_bend_material_length is LegacyRearBend
    # Phase6 keeps a read-only wrapper for old GUI callers, not identity.
    # It must delegate to the exact Engine formed-FW formula.
    import inspect
    assert "manufacturing_api.formed_box_body_fw_widths(profile, thickness)" in inspect.getsource(LegacyFormedFw)
    profile = ({"len": 20.0, "angle": 90}, {"len": 600.0, "core": "W"}, {"len": 20.0})
    assert LegacyFormedFw(profile, 2.0) == formed_box_body_fw_widths(profile, 2.0)
    assert quantity_inherited_nfb_brand_conflicts is PublicNfbConflicts is LegacyNfbConflicts
    assert piece_features.BoxBodyStructureType is BoxBodyStructureType
    assert piece_features.normalize_box_body_structure_state is normalize_box_body_structure_state


def test_engine_has_zero_reverse_phase6_imports_in_modified_owners():
    paths = (
        "ae_engine/box_body_piece_features.py",
        "ae_engine/cabinet_types/receiving.py",
        "ae_engine/certified_relief_registry.py",
        "ae_engine/receiving_nfb_v5_part_only_manufacturing.py",
    )
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("phase6_", "gui_modules")), (
                    path, node.lineno, node.module
                )
            if isinstance(node, ast.Import):
                assert not any(item.name.startswith(("phase6_", "gui_modules")) for item in node.names), path


def test_receiving_legacy_back_panel_and_source_guard_stay_same_objects():
    assert LegacyBackPanel.FULL is BackPanelMode.FULL
    assert LegacyBackPanel.HALF is BackPanelMode.HALF
    assert back_panel_mode is not None
