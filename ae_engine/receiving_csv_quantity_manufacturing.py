# -*- coding: utf-8 -*-
"""#1502: normal quantity NFB output through current CSV and physical CHECK/Q.

Every quantity version is resolved separately by the canonical Phase6
manufacturing service. This adapter checks that *version's* current submitted
NFB CSV, physical upper inner door, one/two actual base plates and, when box
body is selected, the physical side-skin MARKING and source T2 fixing EARs.
It then feeds the EXISTING exact-geometry equivalence/Q grouping. It never
uses the retired supplier DXF or a persisted READY boolean, invents pad
geometry, or treats a group count as proof of a per-version correct source.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from .manufacturing_quantity import PhysicalPartDemand
from .manufacturing_export import (
    resolved_physical_render_parts, _atomic_commit_staged_dxfs,
    _reject_unapproved_nfb_pad_ear_manufacturing,
    reject_unverified_receiving_nfb_tier_base, _validate_nfb_base_part_scope,
)
from .manufacturing_api import (
    save_part_render_data_dxf, verify_saved_part_render_data_dxf,
)
from .drawing_annotation_layout import annotate_quantity_render_data
from .dxf_serialization import verify_quantity_check_dxf


def export_current_csv_quantity_manufacturing(
    batch, output_dir, *, flags, overwrite=False,
):
    """One atomic operator action for ALL selected quantity NFB versions.

    Returns the existing group-key -> filepath convention. Non-submitted
    versions remain normal canonical parts, and quantities are their saved
    QuantityModel piece counts, not a duplicated Set/Bay multiplier.
    """
    from phase6_manufacturing_contracts import thaw_manufacturing_value
    from phase6_quantity_manufacturing import (
        QuantityManufacturingBatch, quantity_manufacturing_groups,
    )
    from phase6_quantity_model import QuantityModel
    from gui_modules.project.export_actions import _resolved_export_intention_key
    from .receiving_fixed_plate_formed_manufacturing import (
        _verified_current_csv_manufacturing_owners,
        _verified_formed_ear_parts,
    )
    from .receiving_ear_side_manufacturing_marking import (
        with_verified_receiving_ear_side_markings,
    )
    from .manufacturing_scene_access import owner_render_data
    from .receiving_fixed_plate_side_check_dxf import _readback_marking_lines

    if type(overwrite) is not bool:
        raise TypeError("RECEIVING_CSV_QUANTITY_OVERWRITE_MUST_BE_BOOLEAN")
    requests = tuple(batch.requests)
    versions = {v.version_id:v for v in batch.versions}
    if len(versions) != len(requests) or not versions:
        raise ValueError("RECEIVING_CSV_QUANTITY_VERSION_IDENTITY_MISMATCH")
    chosen = []
    marked_receipts = []
    verified_csv_owners = set()
    for vid, count, request in requests:
        version = versions.get(vid)
        if version is None or version.piece_count != count or count < 1:
            raise ValueError("RECEIVING_CSV_QUANTITY_COUNT_VERSION_DRIFT")
        snapshot = thaw_manufacturing_value(request.input_snapshot)
        # The immutable Phase6 DTO intentionally normalizes *all* numeric
        # values into floats. Only schema-defined integer identity fields
        # (not arbitrary dimensions/X/Z coordinates) are restored here.
        # A fractional, nonfinite or forged field still fails closed.
        from math import isfinite
        integer_identity_fields = frozenset((
            "rotation_deg", "layer_count", "layer_index", "slot_index",
            "set_index", "bay_index", "inner_door_layers",
            "receiving_inner_door_layers", "next_version_number",
        ))
        def restore_dto_id(value, key=None):
            if isinstance(value, dict):
                return {name: restore_dto_id(item, name)
                        for name,item in value.items()}
            if isinstance(value, list):
                return [restore_dto_id(item) for item in value]
            if key in integer_identity_fields and value is not None:
                if (type(value) not in (int,float) or not isfinite(value)
                        or int(value) != value):
                    raise ValueError(
                        "RECEIVING_CSV_QUANTITY_FROZEN_INTEGER_IDENTITY_INVALID:"
                        + str(key)
                    )
                return int(value)
            return value
        snapshot = restore_dto_id(snapshot)
        # The immutable Phase6 contract represents EVERY Real as float, so
        # persisted piece_count 3 becomes 3.0 when thawed. Restore ONLY
        # quantity version counts already independently confirmed by the
        # typed QuantityManufacturingBatch; nonintegral/negative/forged
        # counts remain rejected rather than weakening QuantityModel.
        from math import isfinite
        restored = []
        for row in snapshot["quantity"]["versions"]:
            expected_version = versions.get(row["version_id"])
            piece = row["piece_count"]
            if (expected_version is None or type(expected_version.piece_count) is not int
                    or type(piece) not in (int, float)
                    or not isfinite(piece)
                    or piece <= 0 or int(piece) != piece
                    or int(piece) != expected_version.piece_count):
                raise ValueError("RECEIVING_CSV_QUANTITY_FROZEN_PIECE_COUNT_DRIFT")
            restored.append({**row, "piece_count": int(piece)})
        snapshot["quantity"] = {**snapshot["quantity"], "versions": restored}
        persisted = QuantityModel.from_payload(snapshot["quantity"])
        if persisted.selected_version_id != vid:
            raise ValueError("RECEIVING_CSV_QUANTITY_SELECTED_VERSION_DRIFT")
        actual_saved = persisted.nfb_config_for_version(vid)
        selected = tuple(d for d in batch.demands if d.version_id == vid
                         and (d.source_part_id.startswith("custom:")
                         or bool(flags.get(_resolved_export_intention_key(
                             d.source_part_id), False))))
        if not selected:
            continue
        if len({d.physical_id for d in selected}) != len(selected):
            raise ValueError("RECEIVING_CSV_QUANTITY_DUPLICATE_PHYSICAL_ID")
        if snapshot.get("nfb_config_submitted") is True and not actual_saved:
            raise ValueError("RECEIVING_CSV_QUANTITY_SNAPSHOT_HAS_NO_SAVED_SOURCE")
        if actual_saved and actual_saved.get("nfb_config_submitted") is True:
            if (snapshot.get("nfb_config_submitted") is not True
                    or snapshot.get("nfb_config") != actual_saved["nfb_config"]):
                raise ValueError("RECEIVING_CSV_QUANTITY_SAVED_SOURCE_NOT_CURRENT")
            original=version.geometry
            body_selected = bool(flags.get("box_body"))
            if body_selected:
                dimensions=tuple(float(snapshot[k]) for k in ("w","h","d"))
                thickness=float(snapshot["t"])
                formed, uv, _contacts = _verified_formed_ear_parts(
                    snapshot, original, dimensions=dimensions,
                    sheet_thickness=thickness,
                )
                marked = with_verified_receiving_ear_side_markings(
                    snapshot, original, dimensions=dimensions,
                    sheet_thickness=thickness,
                )
            else:
                formed={}
                uv=()
                marked=original
            current={key:render for key,render in
                     resolved_physical_render_parts(marked)}
            if len(current)!=len(tuple(resolved_physical_render_parts(marked))):
                raise ValueError("RECEIVING_CSV_QUANTITY_PHYSICAL_DUPLICATE")
            required = {d.physical_id for d in selected}
            if not required.issubset(current):
                raise ValueError("RECEIVING_CSV_QUANTITY_SELECTED_PHYSICAL_MISSING")
            filtered=replace(marked,parts=tuple(
                part for part in marked.parts if
                (part.part_key in {d.source_part_id for d in selected})
            ))
            permitted=_verified_current_csv_manufacturing_owners(
                snapshot, original, filtered,
            )
            if not any(
                key.startswith("inner_door:") or key=="base_plate"
                or key.startswith("base_plate:nfb_layer:")
                for key in current
            ):
                raise ValueError("RECEIVING_CSV_QUANTITY_NO_CURRENT_PHYSICAL_NFB")
            # Every requested NFB sheet has its very own current-source
            # proof. Other selected independent sheets keep normal guards.
            rows=[]
            for d in selected:
                render=current[d.physical_id]
                metadata=getattr(render,"metadata",{}) or {}
                if (d.physical_id=="base_plate"
                        or d.physical_id.startswith("base_plate:nfb_layer:")
                        or metadata.get("nfb_v5_trial_status")):
                    if d.physical_id not in permitted:
                        raise ValueError("RECEIVING_CSV_QUANTITY_UNPROVEN_NFB_SHEET")
                rows.append((d.physical_id,"quantity-checked",render))
            _reject_unapproved_nfb_pad_ear_manufacturing(rows)
            for key,_,render in rows:
                if key not in permitted:
                    reject_unverified_receiving_nfb_tier_base(render,output_key=key)
            _validate_nfb_base_part_scope(
                tuple(row for row in rows if row[0] not in permitted),
                part_only=False,
            )
            verified_csv_owners.update((vid,key) for key in permitted)
            for d in selected:
                chosen.append(replace(d,render_data=current[d.physical_id]))
            if body_selected:
                for ear_id, source in formed.items():
                    if (ear_id in current
                            or any(d.physical_id==ear_id and d.version_id==vid
                                   for d in selected)):
                        raise ValueError("RECEIVING_CSV_QUANTITY_DUPLICATE_EAR_SOURCE")
                    chosen.append(PhysicalPartDemand(
                        vid,ear_id,ear_id,count,1,source,
                    ))
                for side in ("box_body:left_side","box_body:right_side"):
                    render=owner_render_data(marked,side)
                    physical_id=next((key for key,v in current.items()
                                      if v is render),None)
                    if physical_id is None:
                        raise ValueError("RECEIVING_CSV_QUANTITY_MISSING_MARKED_SIDE")
                    marked_receipts.append((vid,physical_id,
                        tuple(segment for row in uv if row.side_piece_id==side
                              for segment in row.marking_segments)))
        else:
            if snapshot.get("nfb_config_submitted") is True:
                raise ValueError("RECEIVING_CSV_QUANTITY_UNSUBMITTED_VERSION_BORROWED_NFB")
            chosen.extend(selected)
    if not chosen:
        raise ValueError("RECEIVING_CSV_QUANTITY_NO_SELECTED_PHYSICAL_PARTS")
    scoped=QuantityManufacturingBatch(
        versions=tuple(batch.versions),demands=tuple(chosen),requests=requests,
    )
    groups=quantity_manufacturing_groups(scoped,demands=scoped.demands)
    if sum(g.quantity for g in groups)!=sum(d.quantity for d in chosen):
        raise ValueError("RECEIVING_CSV_QUANTITY_GROUP_COUNT_DRIFT")
    # Annotated Q is not allowed to change any manufactured CUTTING, BEND
    # or MARKING; the same canonical CHECK/Q serializer validates that.
    group_for={(d.version_id,d.physical_id):g for g in groups
               for d in g.members}
    if len(group_for)!=len(chosen):
        raise ValueError("RECEIVING_CSV_QUANTITY_GROUP_MEMBERS_NOT_CONSERVED")
    root=Path(output_dir)
    if not overwrite and any((root/g.filename).exists() for g in groups):
        raise FileExistsError("RECEIVING_CSV_QUANTITY_EXISTING_DXF")
    root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix=".whd-receiving-q-",dir=root) as stage:
        staged={}
        for group in groups:
            render=annotate_quantity_render_data(group.render_data,group.quantity)
            target=Path(stage)/group.filename
            member_ids={(row.version_id,row.physical_id)
                        for row in group.members}
            if member_ids.issubset(verified_csv_owners):
                from .dxf_serialization import save_scene_dxf
                save_scene_dxf(target,render.scene)
            else:
                # A mixed verified/unverified group can NEVER inherit
                # a CSV source authorization through equivalence grouping.
                if (getattr(render,"metadata",None) or {}).get(
                    "nfb_v5_trial_status"
                ):
                    raise ValueError("RECEIVING_CSV_QUANTITY_GROUP_MIXED_PROOF")
                save_part_render_data_dxf(render,target,overwrite=False)
            if not verify_saved_part_render_data_dxf(render,target).ok:
                raise ValueError("RECEIVING_CSV_QUANTITY_SAVED_DXF_REOPEN_FAILED")
            verify_quantity_check_dxf(render.scene,target)
            staged[group.key]=target
        # For every selected version validate the original world-to-SIDE
        # flat MARKING once again against the true serialized Q group.
        for vid, physical_id, segments in marked_receipts:
            member=group_for.get((vid,physical_id))
            if member is None:
                raise ValueError("RECEIVING_CSV_QUANTITY_SIDE_GROUP_MISSING")
            _readback_marking_lines(staged[member.key],segments)
        return _atomic_commit_staged_dxfs(
            staged,root,overwrite=overwrite,
        )
