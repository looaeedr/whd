# -*- coding: utf-8 -*-
"""#1502: current submitted inner-door NFB -> ONE existing physical Base Plate.

This is a PART_ONLY DXF entry, not an EAR-Z/PAD or whole MFG-2 release.
It revalidates the live Set/Bay, indexed source SHA, exact physical spec and
lower four-circle source before the existing atomic manufacturing writer.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf
from ae_engine.manufacturing_export import receiving_instance_namespace
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.receiving_nfb_cutting_manufacturing import read_nfb_runtime_source_profiles_csv
from ae_engine.receiving_nfb_lower_fixing_source import (
    resolve_unique_nfb_lower_reference_handle,
)
from ae_engine.receiving_nfb_ui1b_bridge import (
    NfbVerifiedDraftSubmission, _nfb_config_proof_sha256,
)
from ae_engine.receiving_switch_model_catalog import INDEX_PATH
from .receiving_nfb_partial_export_action import nfb_verification_geometry_changed
from ae_engine.receiving_nfb_transactions import _verify_hole_locations
from ae_engine.receiving_nfb_pair_acceptance import validate_nfb_door_base_pair


def prepare_verified_receiving_nfb_base_plate(
    bundle: NfbVerifiedDraftSubmission, *,
    layout: Mapping[str, object],
    current_snapshot: Mapping[str, object],
    base_spec: BasePlatePartSpec,
    index_path=INDEX_PATH,
    profile_path=None,
):
    """Reverify one saved NFB pair without writing; shared by single and pair DXF."""
    if not isinstance(bundle, NfbVerifiedDraftSubmission) or not bundle.can_submit:
        raise ValueError("NFB base needs current source-verified submitted proof")
    if not isinstance(layout, Mapping) or not isinstance(current_snapshot, Mapping):
        raise TypeError("NFB base requires live Receiving layout and geometry")
    if nfb_verification_geometry_changed(current_snapshot, bundle.snapshot_at_verification):
        raise ValueError("NFB base inner-door geometry changed; reverify")
    if _nfb_config_proof_sha256(bundle.config) != bundle.config_sha256_at_verification:
        raise ValueError("NFB base source-verified NFBConfig mutated")
    try:
        selected_set = layout["sets"][bundle.set_index]
        bay = selected_set["bays"][bundle.bay_index]
        saved = bay["nfb_config"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("NFB base submitted Set/Bay missing") from exc
    scope = bundle.scope
    if (bay.get("nfb_config_submitted") is not True
            or (selected_set.get("stable_id"), bay.get("stable_id"), bundle.version_id)
               != scope.identity
            or selected_set.get("switch_brand") != bundle.verified_door.indexed_model_key[0]
            or saved != bundle.config
            or (tuple(scope.base_plate_part_ids) and "base_plate" not in scope.base_plate_part_ids)):
        raise ValueError("NFB base current submitted owner/config does not match proof")
    # A saved Config matching the session cache is insufficient: it must
    # match the ACTUAL source-verified machining positions and rotations.
    _verify_hole_locations(saved, bundle.verified_door)
    if not isinstance(base_spec, BasePlatePartSpec):
        raise TypeError("NFB base must use existing BasePlatePartSpec")
    physical = receiving_base_plate_values(current_snapshot)
    if physical is None or base_spec.physical_id != "base_plate":
        raise ValueError("NFB actual Receiving Base Plate is not configured")
    expected = {
        "height": physical["h"],
        "shrink_top": physical["base_plate_shrink_top"],
        "shrink_bottom": physical["base_plate_shrink_bottom"],
        "shrink_left": physical["base_plate_shrink_left"],
        "shrink_right": physical["base_plate_shrink_right"],
        "bend": physical["base_plate_bend"],
    }
    if (base_spec.receiving_bend_pattern != physical["receiving_bend_pattern"]
            or str(base_spec.model_name or "").strip() not in ("受電箱", "RECEIVING")
            or any(abs(float(getattr(base_spec, key)) - value) > 1e-6
                   for key, value in expected.items())):
        raise ValueError("NFB base physical spec differs from live configured plate")
    source = Path(bundle.source_path)
    import re
    expected_name = bundle.verified_door.indexed_model_key[1]
    allowed_copy = re.fullmatch(
        re.escape(Path(expected_name).stem) + r"(?:[(][1-9][0-9]*[)])?[.]dxf",
        source.name, re.IGNORECASE,
    )
    if (not allowed_copy
            or sha256(source.read_bytes()).hexdigest() != bundle.source_inventory.source_sha256
            or bundle.verified_door.source_sha256 != bundle.source_inventory.source_sha256):
        raise ValueError("NFB base original indexed source bytes changed")
    idx = Path(index_path)
    profiles = read_nfb_runtime_source_profiles_csv(
        Path(profile_path) if profile_path is not None
        else idx.parent / "來源輪廓索引.csv"
    )
    matching = tuple(x for x in profiles
                     if (x.brand, x.indexed_filename.casefold()) ==
                     (bundle.verified_door.indexed_model_key[0],
                      bundle.verified_door.indexed_model_key[1].casefold()))
    if len(matching) != 1:
        raise ValueError("NFB base live indexed model profile is missing or ambiguous")
    from ae_engine.receiving_nfb_editable_source import resolve_editable_nfb_source_profile
    profile = resolve_editable_nfb_source_profile(source, profile=matching[0])
    if profile.source_sha256 != bundle.source_inventory.source_sha256:
        raise ValueError("NFB base DXF edited after verification; verify and submit current source")
    metadata = getattr(bundle.verified_door.render_data, "metadata", {})
    if (metadata.get("nfb_source_handle") != profile.source_sha256 + ":" + profile.upper_handle
            or metadata.get("nfb_profile_revision") != profile.revision):
        raise ValueError("NFB base inner-door upper original identity changed")
    lower = resolve_unique_nfb_lower_reference_handle(source, profile=profile)
    from ae_engine.cabinet_types.policy import derive_inner_door_panels
    panels = tuple(part for part in derive_inner_door_panels(current_snapshot)
                   if part.stable_id == scope.inner_door_part_id)
    if len(panels) != 1:
        raise ValueError("NFB base has no unique current physical inner-door panel")
    composed = build_existing_receiving_base_with_verified_nfb(
        snapshot=current_snapshot, inner_door_id=panels[0].inner_door_id,
        base_spec=base_spec, verified_inner_door=bundle.verified_door,
        source_path=source, profile=profile, lower_reference_handle=lower,
    )
    # Verify both real physical parts on every export, not a cached READY tag.
    # This receipt counts the 4 native screws/NFB but NEVER grants EAR-Z/PAD
    # or full-box CHECK/Q manufacturing approval.
    pair_receipt = validate_nfb_door_base_pair(
        snapshot=current_snapshot, inner_door_id=panels[0].inner_door_id,
        verified_door=bundle.verified_door, composed_base=composed,
    )
    if pair_receipt.approval_scope != 'PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2':
        raise ValueError('NFB_PAIR_SCOPE_NOT_PART_ONLY')
    return composed, pair_receipt, panels[0], profile


def export_verified_receiving_nfb_base_plate(
    bundle: NfbVerifiedDraftSubmission, *,
    layout: Mapping[str, object],
    current_snapshot: Mapping[str, object],
    base_spec: BasePlatePartSpec,
    output_directory,
    index_path=INDEX_PATH,
    profile_path=None,
):
    """Export one currently verified physical Base Plate PART_ONLY DXF."""
    composed, _pair_receipt, _panel, _profile = prepare_verified_receiving_nfb_base_plate(
        bundle, layout=layout, current_snapshot=current_snapshot,
        base_spec=base_spec, index_path=index_path, profile_path=profile_path,
    )
    scope = bundle.scope
    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("NFB base partial destination must already be a directory")
    resolved = SimpleNamespace(parts=(SimpleNamespace(
        part_key="base_plate", render_data=composed.render_data,
    ),))
    paths = save_resolved_manufacturing_geometry_dxf(
        resolved, root, overwrite=False, part_only=True,
        instance_namespace=receiving_instance_namespace(
            set_id=scope.set_id, bay_id=scope.bay_id,
        ),
    )
    return paths["base_plate"], composed
