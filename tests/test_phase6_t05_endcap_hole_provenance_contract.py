# -*- coding: utf-8 -*-
"""T5 Contract Tests: EndCap Hole and Feature Provenance Trace."""
from pathlib import Path
import pytest

from ae_engine.ae import VAULT_ENDCAP_FEATURE_POLICY
from ae_engine.sheetmetal_features import (
    VaultEndCapFeaturePolicy,
    resolve_vault_endcap_fixed_features,
    EndCapGeometry,
    ReliefConfig,
    ResolvedCircle,
    ResolvedRect,
)


def test_provenance_spec_document_exists_and_contains_required_sections():
    doc_path = Path('docs/superpowers/specs/2026-09-06-endcap-hole-provenance-trace.md')
    assert doc_path.is_file(), 'T5 Provenance spec document must exist'
    text = doc_path.read_text(encoding='utf-8')

    required_keywords = [
        'left_hanging_hole',
        'right_hanging_hole',
        'square_hole',
        'tail_bottom_center_round_hole',
        'VaultEndCapFeaturePolicy',
        'DO_NOT_SHARE',
        'relief.top_primary_left',
        'top_first_fold',
        'Receiving',
    ]
    for kw in required_keywords:
        assert kw in text, f'Missing required keyword {kw} in provenance spec'


def test_vault_endcap_feature_policy_geometry_invariants():
    assert isinstance(VAULT_ENDCAP_FEATURE_POLICY, VaultEndCapFeaturePolicy)
    assert VAULT_ENDCAP_FEATURE_POLICY.hanging_hole_radius > 0
    assert VAULT_ENDCAP_FEATURE_POLICY.hanging_hole_y_from_top_bend > 0
    assert VAULT_ENDCAP_FEATURE_POLICY.square_hole_size.x > 0
    assert VAULT_ENDCAP_FEATURE_POLICY.square_hole_size.y > 0
    assert VAULT_ENDCAP_FEATURE_POLICY.tail_bottom_hole_radius > 0
    assert VAULT_ENDCAP_FEATURE_POLICY.tail_bottom_hole_y > 0


def test_vault_endcap_head_tail_resolution_contract():
    geom = EndCapGeometry(
        total_width=400.0,
        total_depth=250.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    relief_cfg = ReliefConfig(
        top_secondary_x_factor=0.5,
        top_secondary_depth_factor=2.0,
        bottom_x_factor=0.5,
        bottom_y_factor=0.5,
    )

    # Head features: left hanging, right hanging, square hole
    head_features = resolve_vault_endcap_fixed_features(
        geom, relief_config=relief_cfg, policy=VAULT_ENDCAP_FEATURE_POLICY, is_tail=False
    )
    assert len(head_features) == 3
    sources = [f.source_type for f in head_features]
    assert sources.count('vault_endcap_hanging') == 2
    assert sources.count('vault_endcap_square') == 1

    # Tail features: left hanging, right hanging, square hole, PLUS tail bottom hole
    tail_features = resolve_vault_endcap_fixed_features(
        geom, relief_config=relief_cfg, policy=VAULT_ENDCAP_FEATURE_POLICY, is_tail=True
    )
    assert len(tail_features) == 4
    tail_sources = [f.source_type for f in tail_features]
    assert tail_sources.count('vault_endcap_hanging') == 2
    assert tail_sources.count('vault_endcap_square') == 1
    assert tail_sources.count('vault_tail_bottom') == 1


def test_provenance_table_share_status_contract():
    # Provenance policy dictionary contract: each feature must define its share status
    provenance_registry = {
        'left_hanging_hole': {
            'family': 'vault_only',
            'share_status': 'DO_NOT_SHARE',
            'datum': 'relief.top_primary_left + top_first_fold',
        },
        'right_hanging_hole': {
            'family': 'vault_only',
            'share_status': 'DO_NOT_SHARE',
            'datum': 'relief.top_primary_right + top_first_fold',
        },
        'square_hole': {
            'family': 'vault_only',
            'share_status': 'DO_NOT_SHARE',
            'datum': 'blank_origin_left_bottom',
        },
        'tail_bottom_center_round_hole': {
            'family': 'vault_tail_only',
            'share_status': 'DO_NOT_SHARE',
            'datum': 'center_x + blank_origin_bottom',
        },
        'user_surface_features': {
            'family': 'universal',
            'share_status': 'SHARE_CONTRACT',
            'datum': 'feature_anchor_finished_face',
        },
    }

    # Verify that ALL 4 fixed Vault features are strictly marked DO_NOT_SHARE for Receiving
    for key in ('left_hanging_hole', 'right_hanging_hole', 'square_hole', 'tail_bottom_center_round_hole'):
        assert provenance_registry[key]['share_status'] == 'DO_NOT_SHARE'
        assert 'vault' in provenance_registry[key]['family']

    # Universal features remain shared
    assert provenance_registry['user_surface_features']['share_status'] == 'SHARE_CONTRACT'
