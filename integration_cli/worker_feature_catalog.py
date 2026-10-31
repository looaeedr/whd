# -*- coding: utf-8 -*-
"""#2383 Full cabinet-family feature discovery for the installed Worker.

An owner in WHD's GUI/headless engine is NOT equivalent to an externally
certified manufacturing API. This catalog makes every known family feature
addressable by a stable capability ID, with the exact public phase and
source authority it still lacks. The five already certified physical roles
remain the ONLY ready manufacturing routes until each new role passes Gate C.
"""
from __future__ import annotations

from collections.abc import Mapping

FAMILIES = ("金庫型", "受電箱")

# Role -> existing canonical implementation owner. This registry does not
# implement or rederive any geometry, Fold, Relief, collision or 3D formula.
_COMMON_OWNERS = {
    "door": "ae_engine/manufacturing_api.py",
    "end_cap_head": "ae_engine/manufacturing_api.py",
    "end_cap_tail": "ae_engine/manufacturing_api.py",
    "indicator_box": "ae_engine/manufacturing_api.py",
    "indicator_small_door": "ae_engine/manufacturing_api.py",
    "box_body": "ae_engine/manufacturing_api.py",
    "base_plate": "ae_engine/manufacturing_api.py",
    "custom_fold": "ae_engine/custom_fold_manufacturing.py",
    "fold_profile": "ae_engine/box_body_structure.py",
    "certified_relief": "ae_engine/manufacturing_api.py",
    "assembly_joint": "ae_engine/manufacturing_scene_orchestration.py",
    "source_feature_holes": "ae_engine/manufacturing_api.py",
    "physical_piece_split": "ae_engine/manufacturing_export.py",
    "quantity_batch": "ae_engine/manufacturing_api.py",
    "complete_assembly": "ae_engine/manufacturing_scene_orchestration.py",
}
_RECEIVING_OWNERS = {
    "inner_door": "ae_engine/receiving_inner_door_candidates.py",
    "divider": "ae_engine/cabinet_types/receiving.py",
    "fixing_plate": "ae_engine/receiving_fixed_plate_formed_manufacturing.py",
    "back_panel": "ae_engine/cabinet_types/receiving.py",
    "side_panel": "ae_engine/receiving_ear_side_manufacturing_marking.py",
    "nfb_base_plate": "ae_engine/receiving_nfb_v5_part_only_manufacturing.py",
    "nfb_pad": "ae_engine/receiving_nfb_pad_pair_manufacturing.py",
    "nfb_ear": "ae_engine/receiving_fixed_plate_formed_manufacturing.py",
    "nfb_cutting": "ae_engine/receiving_nfb_cutting_manufacturing.py",
    "joint_marking": "ae_engine/receiving_joint_marking.py",
    "multi_bay_batch": "ae_engine/receiving_csv_multibay_manufacturing.py",
}

# Reasons are machine-readable. A blocked capability is an API discovery
# response, NEVER authorization to call prepare/export or a fake DXF.
_BLOCKED_REASONS = {
    "box_body": "WHD_FOLD_AND_PHYSICAL_PIECES_UNVERIFIED",
    "base_plate": "WHD_BASE_PLATE_PHYSICAL_SOURCE_UNVERIFIED",
    "custom_fold": "WHD_CUSTOM_FOLD_SOURCE_UNVERIFIED",
    "fold_profile": "WHD_FOLD_SOURCE_TOPOLOGY_UNVERIFIED",
    "certified_relief": "WHD_ASSEMBLY_RELIEF_CONTEXT_UNVERIFIED",
    "assembly_joint": "WHD_ASSEMBLY_JOINT_UNVERIFIED",
    "source_feature_holes": "WHD_PART_SPECIFIC_FEATURE_MAPPING_REQUIRED",
    "physical_piece_split": "WHD_MULTI_PIECE_INVENTORY_UNVERIFIED",
    "quantity_batch": "WHD_QUANTITY_INVENTORY_UNVERIFIED",
    "complete_assembly": "WHD_ASSEMBLY_GOLDEN_UNVERIFIED",
    "inner_door": "WHD_INNER_DOOR_FRAME_UNVERIFIED",
    "divider": "WHD_DIVIDER_TOPOLOGY_UNVERIFIED",
    "fixing_plate": "WHD_FIXING_PLATE_SOURCE_UNVERIFIED",
    "back_panel": "WHD_BACK_PANEL_SOURCE_UNVERIFIED",
    "side_panel": "WHD_SIDE_PANEL_SOURCE_UNVERIFIED",
    "nfb_base_plate": "WHD_NFB_BASE_SOURCE_UNVERIFIED",
    "nfb_pad": "WHD_NFB_PAD_ASSEMBLY_UNVERIFIED",
    "nfb_ear": "WHD_NFB_EAR_FORMED_SOURCE_UNVERIFIED",
    "nfb_cutting": "WHD_NFB_CUTTING_SOURCE_UNVERIFIED",
    "joint_marking": "WHD_JOINT_MARKING_SOURCE_UNVERIFIED",
    "multi_bay_batch": "WHD_SET_BAY_JOINT_SOURCE_UNVERIFIED",
    "end_cap_head": "WHD_RECEIVING_ENDCAP_TOPOLOGY_UNVERIFIED",
    "end_cap_tail": "WHD_RECEIVING_ENDCAP_TOPOLOGY_UNVERIFIED",
}


def installed_family_feature_catalog(
    installed_capabilities: Mapping[str, object],
) -> list[dict[str, object]]:
    """Resolve EVERY registered family role against actual W-03/04 authority.

    Ready status is derived from the same signed Worker advertisement, not
    hard-coded from the existence of ae_engine PartSpec/GUI source.
    Unsupported roles are still discoverable under stable family/role IDs.
    """
    supported = set()
    for item in installed_capabilities["capabilities"]:
        if item["worker_supported"] is True and item["geometry_acceptance_passed"] is True:
            supported.update((family, item["part_kind"]) for family in item["cabinet_families"])
    records = []
    for family in FAMILIES:
        owners = dict(_COMMON_OWNERS)
        if family == "受電箱":
            owners.update(_RECEIVING_OWNERS)
        for role, owner in sorted(owners.items()):
            ready = (family, role) in supported
            records.append({
                "capability_id": f"{family}/{role}",
                "cabinet_family": family,
                "feature_id": role,
                "implementation_owner": owner,
                "public_operations": ["capabilities", "prepare", "export"]
                    if ready else ["capabilities"],
                "manufacturing_supported": ready,
                "geometry_acceptance_passed": ready,
                "production_scope": "single_part" if ready else (
                    "complete_assembly" if role in (
                        "assembly_joint", "certified_relief", "complete_assembly",
                        "joint_marking", "multi_bay_batch",
                    ) else "part_only"
                ),
                "blocked_code": None if ready else _BLOCKED_REASONS.get(
                    role, "WHD_CAPABILITY_UNSUPPORTED"
                ),
            })
    if len({entry["capability_id"] for entry in records}) != len(records):
        raise ValueError("WHD duplicate family feature capability")
    return records


# This is a real v1.1 prepare/export ingress gate, NOT another capability
# advertisement. Every known family feature can reach the wire validator;
# only the independently certified physical P0 roles may reach W-06 claim.
# New Gate C routes must deliberately replace this denial when their
# source/Frame/FinalScene/multi-DXF owners have actually been certified.
_P0_PHYSICAL_ROLES = frozenset({
    "door", "end_cap_head", "end_cap_tail",
    "indicator_box", "indicator_small_door", "custom_fold",
})


def require_certified_feature_route(request: Mapping[str, object]) -> None:
    """Deny unimplemented family features before any durable Worker job claim.

    The request schema accepts the complete stable family feature taxonomy
    so CADSplit can submit versioned requests without treating a known
    feature as an unknown protocol token. This gate must NEVER infer that an
    existing WHD GUI/engine owner is an externally safe manufacturing route.
    """
    from integration_cli.prepare_evidence import PrepareEvidenceError

    for item in request["items"]:
        part = item["part"]
        family = part["cabinet_family"]
        role = part["kind"]
        owners = dict(_COMMON_OWNERS)
        if family == "受電箱":
            owners.update(_RECEIVING_OWNERS)
        elif family != "金庫型":
            raise PrepareEvidenceError(
                "WHD_CAPABILITY_UNKNOWN",
                "cabinet family has no installed Worker feature contract",
            )
        if role not in owners:
            raise PrepareEvidenceError(
                "WHD_CAPABILITY_UNKNOWN",
                "feature is not registered for this cabinet family",
            )
        if role in _P0_PHYSICAL_ROLES and not (
            family == "受電箱" and role in ("end_cap_head", "end_cap_tail")
        ):
            # W-03 and W-04 still do all actual geometry, Frame, source,
            # approval and Save->Reload verification. This is NOT approval.
            continue
        code = _BLOCKED_REASONS.get(role, "WHD_CAPABILITY_UNSUPPORTED")
        raise PrepareEvidenceError(
            code, f"{family}/{role} requires its own certified Gate C route",
        )
