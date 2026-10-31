# -*- coding: utf-8 -*-
"""DM3 RED guard: Divider relief/final material belongs to manufacturing domain."""
from __future__ import annotations

import inspect


def test_dm3_manufacturing_domain_owns_divider_relief_result_contract():
    from ae_engine import divider_manufacturing

    required = {
        "resolve_divider_final_geometry",
        "ResolvedDividerFinalGeometry",
        "DividerPlacementEvidence",
        "DividerReliefEvidence",
    }
    assert required <= set(dir(divider_manufacturing))

    result_fields = set(divider_manufacturing.ResolvedDividerFinalGeometry.__dataclass_fields__)
    assert {
        "part_id",
        "placement_datum",
        "placement_evidence",
        "relief_evidence",
        "final_material",
        "verified",
    } <= result_fields


def test_dm3_bridge_must_delegate_divider_relief_to_manufacturing_domain():
    from ae_engine import divider_manufacturing
    import phase6_manufacturing_geometry

    source = inspect.getsource(phase6_manufacturing_geometry._phase6_resolve_family_divider_reliefs)
    engine_source = inspect.getsource(divider_manufacturing.resolve_family_divider_reliefs)
    assert "manufacturing_api.resolve_family_divider_reliefs(" in source
    assert "resolve_divider_final_geometry(" in engine_source
    assert "build_joint_world_geometry(" in engine_source
    assert "build_divider_front_fold_relief_candidate(" not in source
    assert "_phase6_divider_fw_placement_evidence(" not in source
    assert "from phase6_" not in engine_source


def test_dm3_physical_contract_no_longer_exposes_placeholder_final_material_or_relief():
    from ae_engine.door_dividers import BoxBodyDividerPart

    source = inspect.getsource(BoxBodyDividerPart.physical_geometry_contract.fget)
    assert '"authority": "CANONICAL_MANUFACTURING_RESOLVE"' not in source
    assert '"authority": "ASSEMBLY_RELIEF_RESOLVE"' not in source
