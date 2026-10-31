"""#2517/#2383: the state that drives physical side/back panels is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine import box_body_structure as geometry
from ae_engine import box_body_structure_core as geometry_core
from ae_engine import box_body_structure_state as owner
from ae_engine.cabinet_types import policy as family_policy
import phase6_box_body_structure as legacy
from integration_cli.worker_receiving_back_panel import (
    receiving_back_panel_spec_from_trusted_part,
)


def test_phase6_compatibility_uses_exact_engine_state_and_enums():
    assert legacy.BoxBodyStructureType is owner.BoxBodyStructureType
    assert legacy.BackPanelMode is owner.BackPanelMode
    assert geometry.BoxBodyStructureType is owner.BoxBodyStructureType
    assert geometry_core.BoxBodyStructureType is owner.BoxBodyStructureType
    assert legacy.normalize_box_body_structure_state is owner.normalize_box_body_structure_state
    assert legacy.set_side_back_back_panel_mode is owner.set_side_back_back_panel_mode
    assert manufacturing_api.set_side_back_back_panel_mode is owner.set_side_back_back_panel_mode
    assert manufacturing_api.back_panel_mode is owner.back_panel_mode


@pytest.mark.parametrize("mode", ("FULL", "HALF", "BACK_OPENING"))
def test_engine_persists_back_panel_mode_without_mutating_request(mode):
    original = owner.default_box_body_structure_state()
    immutable = deepcopy(original)
    changed = manufacturing_api.set_side_back_back_panel_mode(original, mode)
    assert original == immutable
    assert manufacturing_api.back_panel_mode(changed) is owner.BackPanelMode(mode)
    assert legacy.back_panel_mode(changed) is owner.BackPanelMode(mode)
    assert changed["configs"]["three_piece_side_back_split"]["back_panel_mode"] == mode


def test_original_legacy_missing_mode_is_full_and_invalid_mode_fails_closed():
    assert manufacturing_api.back_panel_mode(None) is owner.BackPanelMode.FULL
    with pytest.raises(ValueError, match="unsupported Receiving back-panel mode"):
        manufacturing_api.set_side_back_back_panel_mode(None, "FORGED")
    with pytest.raises(ValueError, match="unsupported Receiving back-panel mode"):
        manufacturing_api.back_panel_mode({
            "configs": {"three_piece_side_back_split": {"back_panel_mode": "FORGED"}}
        })


def test_worker_and_engine_manufacturing_do_not_import_phase6_state_or_fold():
    engine_structure = inspect.getsource(geometry)
    engine_core = inspect.getsource(geometry_core)
    worker = inspect.getsource(receiving_back_panel_spec_from_trusted_part)
    assert "from phase6_box_body_structure import" not in engine_structure
    assert "from phase6_fold_profiles import" not in engine_structure
    assert "from phase6_box_body_structure import" not in engine_core
    assert "from phase6_box_body_structure import" not in worker
    assert "manufacturing_api" in worker or "ae_engine.manufacturing_api" in worker
    assert "from phase6_" not in inspect.getsource(owner)


def test_family_policy_only_imports_engine_structure_state():
    """The family facade must never import the Phase6 compatibility re-export."""
    code = inspect.getsource(family_policy)
    assert "from phase6_box_body_structure import" not in code
    assert family_policy.resolve_box_body_structure_state("金庫型", None) == (
        owner.normalize_box_body_structure_state(None)
    )
