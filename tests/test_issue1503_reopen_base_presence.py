# -*- coding: utf-8 -*-
"""#1503 true Windows saved v3 RED: valid loaded NFB base absent from live scene.

No operator project content is checked into Git. Synthetic source authority
matches the canonical existing 2026-10-18 receiving NFB/base contract.
"""
from copy import deepcopy
from types import SimpleNamespace

from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot


def test_loaded_receiving_project_restores_its_existing_explicit_base_source():
    from gui_modules.project_actions import load_phase6_project

    saved = _snapshot()
    # The old v3 file's existing_parts may only list the Box Body; however
    # receiving_base_plate is STILL an explicit original source authority.
    saved["existing_parts"] = ["box_body"]
    designer = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱"},
        available_parts=("box_body",),
    )
    app = SimpleNamespace(
        fold_designer_app=None,
        project_controller=SimpleNamespace(
            load=lambda _path: ({"snapshot": saved}, deepcopy(saved)),
        ),
        _apply_phase6_project_snapshot=lambda incoming: deepcopy(incoming),
        open_original_fold_designer=lambda: designer,
    )
    out = load_phase6_project(app, "legacy-v3-receiving.p6fold", open_designer=True)
    assert out is designer
    assert designer._phase6_input_snapshot.get("receiving_base_plate") == saved["receiving_base_plate"], (
        "LOADED_V3_SAVED_BASE_SOURCE_SILENTLY_LOST"
    )


def test_submitted_nfb_with_real_source_enters_canonical_assembly_without_legacy_part_checkbox():
    from phase6_manufacturing_adapter import _canonical_part_keys

    source = _snapshot()
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert "base_plate" in _canonical_part_keys(host), (
        "LOADED_SUBMITTED_NFB_VALID_BASE_NOT_REGISTERED"
    )

    no_submit = deepcopy(source)
    no_submit["nfb_config_submitted"] = False
    assert "base_plate" not in _canonical_part_keys(
        SimpleNamespace(
            designer_workspace=SimpleNamespace(available_parts=("box_body",)),
            _phase6_input_snapshot=no_submit,
        )
    ), "a draft never adds source geometry"


def test_unresolved_physical_source_never_creates_base_on_a_saved_project():
    from phase6_manufacturing_adapter import _canonical_part_keys
    source = _snapshot()
    source.pop("receiving_base_plate")
    source["nfb_config_submitted"] = False
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert _canonical_part_keys(host) == ("box_body",)

def _two_tier_csv_without_manual_base():
    source = _snapshot()
    source.pop("receiving_base_plate")
    source["nfb_config_submitted"] = True
    source["nfb_config"] = {
        "layer_count": 2,
        "holes": [
            {"physical_hole_id": "nfb:upper", "layer_index": 0, "slot_index": 0,
             "model_filename": "nfbv5:士林:2P400", "source_brand": "士林"},
            {"physical_hole_id": "nfb:lower", "layer_index": 1, "slot_index": 0,
             "model_filename": "nfbv5:士林:2P400", "source_brand": "士林"},
        ],
    }
    return source


def test_stale_two_tier_csv_bay_identity_blocks_unapproved_base_without_fallback():
    """NFB root/Bay mismatch is a true RED, not 'no matching blank'."""
    import pytest
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from phase6_manufacturing_adapter import _canonical_part_keys
    source = _two_tier_csv_without_manual_base()
    # The loaded Bay still owns the old one-tier NFB. A different root
    # config must NEVER manufacture or silently borrow a physical Base.
    with pytest.raises(ValueError, match="EAR_Z_NFB_SOURCE_IDENTITY_DRIFT"):
        receiving_base_plate_values(source)
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert _canonical_part_keys(host) == ("box_body",), (
        "STALE_BAY_IDENTITY_MUST_NEVER_REGISTER_BASE"
    )


def test_source_joined_two_tier_csv_derives_real_base_without_manual_choice():
    """Current CSV V5 dual tiers share the source-derived physical root."""
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
    from phase6_manufacturing_adapter import _canonical_part_keys
    source = _two_tier_csv_without_manual_base()
    source["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        source["nfb_config"]
    )
    assert "receiving_base_plate" not in source
    values = receiving_base_plate_values(source)
    assert values is not None and values["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_LEFT
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert _canonical_part_keys(host) == ("box_body", "base_plate"), (
        "COMMITTED_TWO_TIER_SOURCE_BASE_MUST_EXIST"
    )

def test_mfg_raw_part_provider_never_recursively_resolves_itself():
    """Regression from real Windows double->single project switch."""
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _query_fold_designer_render_data,
    )
    snapshot = _snapshot()
    calls = []
    app = SimpleNamespace(
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=snapshot,
            _phase6_last_resolved_manufacturing_geometry=None,
            _phase6_resolve_manufacturing_geometry=lambda: calls.append("recursive"),
        ),
        _fold_designer_part_spec_from_payload=lambda key, p: ("root", "ctx"),
        _authoritative_render_data=lambda part_spec, context: (part_spec, context),
    )
    raw = _query_fold_designer_render_data(
        app, "base_plate", {"_use_committed_relief": False},
    )
    assert raw == ("root", "ctx")
    assert calls == [], "RAW_MANUFACTURING_MUST_NOT_REENTER_RESOLVER"


def test_one_tier_2d_operator_read_uses_cached_exact_canonical_sheet():
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _query_fold_designer_render_data,
    )
    snapshot = _snapshot()
    genuine = SimpleNamespace(unfolded_topology=object())
    resolver_calls = []
    owner = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_last_resolved_manufacturing_geometry=SimpleNamespace(
            parts=(SimpleNamespace(part_key="base_plate", render_data=genuine),),
        ),
        _phase6_resolve_manufacturing_geometry=lambda: resolver_calls.append(True),
    )
    app = SimpleNamespace(fold_designer_app=owner)
    assert _query_fold_designer_render_data(app, "base_plate", {}) is genuine
    assert resolver_calls == [], "2D operator must reuse exact completed source"
