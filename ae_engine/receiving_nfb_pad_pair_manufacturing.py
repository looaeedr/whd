# -*- coding: utf-8 -*-
"""#1503: explicit, independently verified PAD+Base PART-ONLY CHECK/Q DXFs.

This is a narrowly scoped physical-pair manufacturing API, NOT a full-cabinet
release and NOT an escape hatch for generic unreleased NFB draft export. It
rebuilds validation from current V5 CSV, tooling, real source-cut Base FinalScene,
true folded world-skin full-T fit and swept Base-slab interference before
allowing any paired sheet to reach the canonical DrawingScene DXF serializer.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import os
import shutil
import tempfile

from .manufacturing_equivalence import (
    ManufacturingParameters, group_quantity_physical_demands,
)
from .manufacturing_quantity import PhysicalPartDemand
from .receiving_nfb_pad_delivery import (
    resolve_committed_pad_physical_delivery,
)
from .sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive,TextPrimitive,
)


@dataclass(frozen=True)
class PadBasePairManufacturingResult:
    output_directory: str
    per_box_pad_count: int
    pad_piece_count: int
    base_piece_count: int
    files: tuple[str, ...]
    evidence_sha256: str
    scope: str = "RECEIVING_PAD_BASE_PAIR_PART_ONLY_CHECK_Q"


def _require_real_base_cutting_only(parent, source_hole_count, pad_count):
    """No extra unrecognized CUTTING toolpath hiding in the selected Base."""
    rd=parent.render_data
    meta=rd.metadata
    if (meta.get("nfb_v5_trial_status") is None
            or meta.get("nfb_v5_target_role") != "base-plate"
            or meta.get("nfb_trial_export_approved") is not False
            or meta.get("nfb_base_mfg2_release_approved") is not False):
        raise ValueError("PAD_PAIR_BASE_FINALSCENE_V5_SOURCE_UNVERIFIED")
    cutting=[row for row in rd.scene.primitives if row.layer=="CUTTING"]
    circles=[row for row in cutting if isinstance(row,CirclePrimitive)]
    polys=[row for row in cutting if isinstance(row,PolylinePrimitive)
           and row.closed]
    # Current source Base has one real closed perimeter and four original
    # ear-mount cuts; each installed NFB contributes four actual screw circles
    # and each physical PAD contributes exactly four square cuts. The PAD
    # slab witness already verified the 4 squares at exact source UV.
    if (len(circles)!=4*source_hole_count
            or len(polys)!=5+4*pad_count
            or len(cutting)!=len(circles)+len(polys)):
        raise ValueError("PAD_PAIR_BASE_UNRECOGNIZED_CUTTING_OR_HOLE_COUNT")
    if (len(tuple(meta.get("nfb_v5_hole_ids") or ()))!=source_hole_count
            or len(tuple(meta.get("nfb_v5_pad_square_owners") or ()))!=pad_count):
        raise ValueError("PAD_PAIR_BASE_SOURCE_HOLE_OWNER_MISMATCH")


def _require_pad_cutting_only(render):
    cutting=[row for row in render.scene.primitives if row.layer=="CUTTING"]
    bends=[row for row in render.scene.primitives if row.layer=="BEND"]
    if (len(cutting)!=5
            or sum(isinstance(row,CirclePrimitive) for row in cutting)!=4
            or sum(isinstance(row,PolylinePrimitive) and row.closed for row in cutting)!=1
            or len(bends)!=2
            or any(not isinstance(row,LinePrimitive) for row in bends)
            or len(tuple(render.fold_guides))!=2
            or len(render.scene.primitives)!=7):
        raise ValueError("PAD_PAIR_PAD_REAL_CUTTING_BEND_INCOMPLETE")


def verified_pad_base_physical_sheets(
    snapshot, assembly_parts, *, allow_empty: bool = False,
):
    """Reprove actual PAD + owning Base from current CSV and FinalScene.

    The same physical validators authorize PAD+Base PART_ONLY and the
    separately source-verified complete-sheet bundle; neither authorizes
    welding workmanship or a generic MFG-2/NC release.
    Returns (committed PAD delivery rows, physical source render map).
    """
    if type(allow_empty) is not bool:
        raise TypeError("PAD_PAIR_ALLOW_EMPTY_MUST_BE_BOOL")
    records=resolve_committed_pad_physical_delivery(
        snapshot,assembly_parts,piece_count=1)
    if not records:
        if allow_empty:
            return (), {}
        raise ValueError("PAD_PAIR_NO_SOURCE_CONFIRMED_SHEETS")
    if any(not rec.full_thickness_contact_certified
           or not rec.seating_witness.base_slab_collision_verified
           or rec.seating_witness.tab_back_skin_shortfall_mm>1e-4
           or abs(rec.seating_witness.regular_leg_front_gap_mm)>1e-4
           for rec in records):
        raise ValueError("PAD_PAIR_REAL_FULL_T2_CONTACT_OR_COLLISION_UNVERIFIED")
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    found=_submitted_csv_holes(snapshot)
    if found is None or not found:
        raise ValueError("PAD_PAIR_CURRENT_COMMITTED_NFB_SOURCE_MISSING")
    _,holes=found
    if any(h.layer_count != holes[0].layer_count for h in holes):
        raise ValueError("PAD_PAIR_SOURCE_TIER_COUNT_DRIFT")
    total_layers=holes[0].layer_count
    if total_layers not in (1,2):
        raise ValueError("PAD_PAIR_UNSUPPORTED_SOURCE_TIER_COUNT")
    # Every physical NFB tier has its OWN unmodified Base source, screw
    # locations, four-hole PAD owners and actual installed Z. Never reuse
    # the first tier's whole-Bay NFB hole count for the second Base.
    expected_ids={}
    for hole in holes:
        tier=hole.slot_index
        if type(tier) is not int or tier not in range(total_layers):
            raise ValueError("PAD_PAIR_SOURCE_TIER_OWNER_INVALID")
        base_id=("base_plate" if total_layers==1
                 else f"base_plate:nfb_layer:{tier}")
        expected_ids.setdefault(base_id,set()).add(hole.physical_hole_id)
    parent_map={p.part_key:p for p in tuple(assembly_parts)}
    physical={}
    by_parent={}
    for record in records:
        parent=parent_map.get(record.parent_base_id)
        if parent is None or record.parent_base_id not in expected_ids:
            raise ValueError("PAD_PAIR_BASE_PARENT_DISCONNECTED")
        if record.owner_hole_id not in expected_ids[record.parent_base_id]:
            raise ValueError("PAD_PAIR_PAD_HOLE_TIER_OWNER_DRIFT")
        if any(row.physical_id==record.physical_id
               for row in by_parent.get(record.parent_base_id,())):
            raise ValueError("PAD_PAIR_DUPLICATE_SOURCE_OWNER")
        by_parent.setdefault(record.parent_base_id,[]).append(record)
    for parent_id,members in sorted(by_parent.items()):
        parent=parent_map[parent_id]
        metadata=parent.render_data.metadata
        if total_layers==2:
            from .receiving_nfb_layer_physical_parts import PREVIEW_STATUS
            tier=int(parent_id.rsplit(":",1)[-1])
            if (parent_id != f"base_plate:nfb_layer:{tier}"
                    or metadata.get("stable_id")!=parent_id
                    or metadata.get("nfb_layer_index")!=tier
                    or metadata.get("nfb_layer_manufacturing_status")!=PREVIEW_STATUS
                    or metadata.get("nfb_tier_real_skin_z_resolved") is not True
                    or parent.render_data.unfolded_topology.piece_id!=parent_id):
                raise ValueError("PAD_PAIR_TIER_BASE_PHYSICAL_SOURCE_NOT_VERIFIED")
        if set(metadata.get("nfb_v5_hole_ids") or ())!=expected_ids[parent_id]:
            raise ValueError("PAD_PAIR_BASE_NFB_HOLE_TIER_OWNER_DRIFT")
        if set(dict(metadata.get("nfb_v5_pad_square_owners") or ()))!={
                row.owner_hole_id for row in members}:
            raise ValueError("PAD_PAIR_BASE_PAD_SQUARE_TIER_OWNER_DRIFT")
        _require_real_base_cutting_only(
            parent,len(expected_ids[parent_id]),len(members))
        physical[parent_id]=parent.render_data
        for record in members:
            _require_pad_cutting_only(record.render_data)
            if record.physical_id in physical:
                raise ValueError("PAD_PAIR_DUPLICATE_PHYSICAL_SHEET")
            physical[record.physical_id]=record.render_data
    return tuple(records), physical


def export_verified_pad_base_part_only(
    snapshot, assembly_parts, output_directory, *,
    version_id: str, box_count: int,
    parameters: ManufacturingParameters,
) -> PadBasePairManufacturingResult:
    """Atomic paired DXF & CHECK/Q from the same physically proven NFB/Bay.

    Identity, local thickened-solid fit and readback are verified *in this
    call*. No caller-issued release boolean, stale geometry, preview role
    rename or arbitrary Scene file can authorize the output. The generic
    full-cabinet MFG-2 and all separately pending EAR/welding gates remain.
    """
    if (not isinstance(version_id,str) or not version_id.strip()
            or type(box_count) is not int or box_count<=0
            or not isinstance(parameters,ManufacturingParameters)):
        raise ValueError("PAD_PAIR_VERSION_COUNT_OR_PROCESS_REQUIRED")
    records, physical = verified_pad_base_physical_sheets(
        snapshot, assembly_parts,
    )
    demands=tuple(
        PhysicalPartDemand(version_id,pid,pid,box_count,1,render)
        for pid,render in physical.items()
    )
    groups=group_quantity_physical_demands(
        demands,{(version_id,pid):parameters for pid in physical},
    )
    if len(groups)!=len(physical):
        # Even geometrically equivalent pads owned by different actual
        # NFB holes must remain explicitly traceable as separate pieces.
        if sum(g.quantity for g in groups)!=box_count*len(physical):
            raise ValueError("PAD_PAIR_CHECK_Q_DEMAND_OR_GROUP_LOST")
    folder=Path(output_directory)
    if folder.exists():
        raise FileExistsError(str(folder))
    folder.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".pad-pair-mfg-",dir=folder.parent))
    witness=[]
    try:
        from .drawing_annotation_layout import annotate_quantity_render_data
        from .dxf_serialization import save_scene_dxf, verify_quantity_check_dxf
        from .manufacturing_verification import verify_saved_part_render_data_dxf
        from .manufacturing_equivalence import manufacturing_equivalence_payload
        for group in groups:
            expected=sha256(manufacturing_equivalence_payload(
                group.render_data,group.parameters).encode()).hexdigest()
            if group.key!=expected:
                raise ValueError("PAD_PAIR_CHECK_Q_SOURCE_FINGERPRINT_DRIFT")
            render=annotate_quantity_render_data(group.render_data,group.quantity)
            name=group.filename
            dest=stage/name
            save_scene_dxf(dest,render.scene)
            proof=verify_saved_part_render_data_dxf(render,dest)
            if not proof.ok:
                raise ValueError("PAD_PAIR_STAGED_DXF_ROUNDTRIP_FAILED")
            verify_quantity_check_dxf(render.scene,dest)
            witness.append({
                "name":name,"equivalence_key":group.key,
                "quantity":group.quantity,
                "source_ids":[row.physical_id for row in group.members],
                "sha256":sha256(dest.read_bytes()).hexdigest(),
            })
        manifest={
            "schema":"RECEIVING_PAD_BASE_PAIR_PART_ONLY_CHECK_Q_V1",
            "full_cabinet_manufacturing_released":False,
            "version_id":version_id,"box_count":box_count,
            "pad_per_box":len(records),
            "pad_total":box_count*len(records),
            "base_per_box":len(by_parent),
            "base_total":box_count*len(by_parent),
            "sources":[{
                "physical_id":r.physical_id,
                "parent_base_id":r.parent_base_id,
                "nfb_hole_id":r.owner_hole_id,
                "csv_sha256":r.source_csv_sha256,
                "tooling_sha256":r.tooling_sha256,
                "tab_insert_mm":r.seating_witness.tab_insertion_mm,
                "sheet_t_mm":r.thickness_mm,
                "base_slab_collision_verified":r.seating_witness.base_slab_collision_verified,
            } for r in records],
            "dxf":witness,
        }
        receipt=stage/"PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json"
        receipt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",
                           encoding="utf-8")
        digest=sha256(receipt.read_bytes()).hexdigest()
        os.replace(stage,folder)
        return PadBasePairManufacturingResult(
            str(folder),len(records),box_count*len(records),
            box_count*len(by_parent),tuple(row["name"] for row in witness),
            digest,
        )
    finally:
        if stage.exists():
            shutil.rmtree(stage)
