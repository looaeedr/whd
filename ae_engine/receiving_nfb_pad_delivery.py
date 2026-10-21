# -*- coding: utf-8 -*-
"""#1503: physical PAD owner, source-traceable BOM and atomic trial DXF package.

The one current committed CSV/Bay source supplies 2D, 3D and the physical
demand. This is NOT a manufacturing release: partial physical tab insertion
and assembly collision have not met the full T2 mating requirement. The
unreleased DXF bundle is kept outside the canonical manufacturing sink.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

from .receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
from .receiving_nfb_pad_assembly_preview import build_committed_pad_assembly_display
from .receiving_nfb_numeric_catalog import brand_csv_path
from .receiving_nfb_pad_generator import TOOLING_RELATIVE_PATH
from .manufacturing_quantity import PhysicalPartDemand


@dataclass(frozen=True)
class PadPhysicalDelivery:
    """One real source-derived physical sheet, not one per selected model."""
    physical_id: str
    parent_base_id: str
    owner_hole_id: str
    source_brand: str
    source_model: str
    blank_width_mm: float
    blank_height_mm: float
    formed_width_mm: float
    formed_height_mm: float
    thickness_mm: float
    rise_mm: float
    quantity: int
    source_csv_sha256: str
    tooling_sha256: str
    render_data: object
    tab_tip_mating_preview_verified: bool
    full_thickness_contact_certified: bool = False
    full_volume_collision_certified: bool = False
    manufacturing_ready: bool = False


def _positive_int(value):
    if type(value) is not int or value <= 0:
        raise ValueError("PAD_BOM_PIECE_COUNT_MUST_BE_POSITIVE")
    return value


def _source_hashes(brand):
    csv=brand_csv_path(brand)
    tooling=Path(__file__).resolve().parents[1] / TOOLING_RELATIVE_PATH
    return sha256(csv.read_bytes()).hexdigest(), sha256(tooling.read_bytes()).hexdigest()


def resolve_committed_pad_physical_delivery(
    snapshot: Mapping, assembly_parts, *, piece_count: int = 1,
) -> tuple[PadPhysicalDelivery, ...]:
    """Join actual cut BASE+3D PAD with the SAME current 2D sheet by identity.

    Do not allow a no-X, stale source, missing four CUTTING square holes or
    fake MFG boolean to become inventory. Counts are ONE physical pad per
    shallower installed NFB per box, multiplied by requested box quantity.
    """
    count=_positive_int(piece_count)
    drafts=committed_nfb_pad_draft_parts(snapshot)
    skins=build_committed_pad_assembly_display(snapshot, assembly_parts)
    if len({p.part_id for p in drafts}) != len(drafts):
        raise ValueError("PAD_BOM_DUPLICATE_2D_OWNER")
    skin_by_id={p.part_id:p for p in skins}
    if len(skin_by_id) != len(skins) or set(skin_by_id)!={p.part_id for p in drafts}:
        raise ValueError("PAD_BOM_REAL_BASE_2D_3D_MISMATCH")
    rows=[]
    for sheet in drafts:
        skin=skin_by_id[sheet.part_id]
        data=sheet.render_data
        pattern=sheet.pattern
        if (not skin.four_tab_mesh_mating_verified
                or skin.parent_base_id != sheet.parent_base_id
                or skin.owner_hole_id != sheet.owner_hole_id
                or abs(float(skin.rise_mm)-float(pattern.rise_mm))>1e-6
                or data.unfolded_topology is None
                or data.unfolded_topology.piece_id != sheet.part_id
                or data.metadata.get("stable_id") != sheet.part_id
                or data.metadata.get("nfb_deferred_manufacturing_role") != "PAD"
                or data.metadata.get("manufacturing_ready") is not False
                or sheet.manufacturing_ready
                or skin.manufacturing_ready
                or skin.assembly_contact_certified):
            raise ValueError("PAD_BOM_PHYSICAL_IDENTITY_OR_RELEASE_DRIFT")
        digest, tool_digest=_source_hashes(pattern.brand)
        rows.append(PadPhysicalDelivery(
            physical_id=sheet.part_id,parent_base_id=sheet.parent_base_id,
            owner_hole_id=sheet.owner_hole_id,
            source_brand=pattern.brand,source_model=pattern.model,
            blank_width_mm=float(data.unfolded_topology.width),
            blank_height_mm=float(data.unfolded_topology.height),
            formed_width_mm=float(pattern.formed_width_mm),
            formed_height_mm=float(pattern.formed_height_mm),
            thickness_mm=float(pattern.plate_thickness_mm),
            rise_mm=float(pattern.rise_mm),
            quantity=count,source_csv_sha256=digest,tooling_sha256=tool_digest,
            render_data=data,
            tab_tip_mating_preview_verified=True,
        ))
    return tuple(rows)


def pad_physical_demand_rows(
    version_id: str, snapshot: Mapping, assembly_parts, *, piece_count: int,
) -> tuple[PhysicalPartDemand, ...]:
    """Typed physical BOM demands; intentionally NOT product DXF permission."""
    if not str(version_id or "").strip():
        raise ValueError("PAD_BOM_VERSION_ID_REQUIRED")
    return tuple(
        PhysicalPartDemand(
            version_id,record.physical_id,record.physical_id,
            record.quantity,1,record.render_data,
        )
        for record in resolve_committed_pad_physical_delivery(
            snapshot,assembly_parts,piece_count=piece_count,
        )
    )


def export_pad_trial_bundle(
    snapshot: Mapping, assembly_parts, destination, *, piece_count=1,
) -> dict[str, object]:
    """Atomically write *real source* pad/base DXFs and inspected BOM JSON.

    Unapproved manufacturing exports MUST continue to fail at the canonical
    WHD MFG boundary. This package explicitly says NOT FOR PRODUCTION and
    may not be treated as an approved CNC, welding or CHECK/Q batch.
    """
    records=resolve_committed_pad_physical_delivery(
        snapshot,assembly_parts,piece_count=piece_count)
    if not records:
        raise ValueError("PAD_TRIAL_NO_PHYSICAL_SHEETS")
    parts={str(part.part_key):part for part in tuple(assembly_parts)}
    from .dxf_serialization import save_scene_dxf
    from .manufacturing_verification import verify_saved_part_render_data_dxf
    from .manufacturing_export import safe_dxf_part_stem
    folder=Path(destination)
    if folder.exists():
        raise FileExistsError(str(folder))
    folder.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".pad-unreleased-",dir=str(folder.parent)))
    files=[]
    try:
        for item in records:
            parent=parts.get(item.parent_base_id)
            if parent is None:
                raise ValueError("PAD_TRIAL_REAL_PARENT_BASE_MISSING")
        sheets={rec.physical_id:rec.render_data for rec in records}
        for rec in records:
            sheets[rec.parent_base_id]=parts[rec.parent_base_id].render_data
        for name,render in sorted(sheets.items()):
            filename="UNRELEASED_"+safe_dxf_part_stem(name)+".dxf"
            target=stage/filename
            save_scene_dxf(target,render.scene)
            proof=verify_saved_part_render_data_dxf(render,target)
            if not proof.ok:
                raise ValueError("PAD_TRIAL_DXF_REOPEN_FAILED:"+name)
            files.append((name,filename,sha256(target.read_bytes()).hexdigest()))
        summary={
            "kind":"WHD_PAD_SOURCE_PROVEN_TRIAL",
            "manufacturing_ready":False,
            "full_assembly_contact_certified":False,
            "do_not_use_for_production":True,
            "requires":"full T2 tab depth, true volume collision, paired Base CHECK/Q",
            "parts":[{
                "id":rec.physical_id,
                "base_id":rec.parent_base_id,
                "nfb_hole_id":rec.owner_hole_id,
                "brand":rec.source_brand,
                "model":rec.source_model,
                "blank_mm":[rec.blank_width_mm,rec.blank_height_mm],
                "formed_mm":[rec.formed_width_mm,rec.formed_height_mm],
                "rise_mm":rec.rise_mm,
                "thickness_mm":rec.thickness_mm,
                "quantity":rec.quantity,
                "csv_sha256":rec.source_csv_sha256,
                "tooling_sha256":rec.tooling_sha256,
            } for rec in records],
            "dxf": [{"part_id":part,"filename":name,"sha256":digest}
                    for part,name,digest in files],
        }
        (stage/"BOM_AND_VERIFICATION_NOT_FOR_PRODUCTION.json").write_text(
            json.dumps(summary,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        (stage/"NOT_FOR_PRODUCTION.txt").write_text(
            "WHD PAD / BASE physical trial. NOT production-ready.\n"
            "T2 full-depth fitting, actual collision and MFG/CHECK Q NOT approved.\n",
            encoding="utf-8",
        )
        os.replace(stage,folder)
        return summary
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def pad_bom_demands_from_committed_snapshot(
    version_id: str, snapshot: Mapping, *, piece_count: int,
) -> tuple[PhysicalPartDemand, ...]:
    """Demand-only projection for quantity mode's committed NFB source.

    A quantity-mode manufacturing resolver does not yet furnish a certified
    PAD assembled solid; its job is to count actual physical sheets, not to
    infer any manufacturing permission. Require a confirmed current Hole
    Editor X and valid common source before creating any BOM row.
    """
    count=_positive_int(piece_count)
    if not isinstance(snapshot,Mapping):
        raise TypeError("PAD_BOM_SNAPSHOT_REQUIRED")
    if not str(version_id or "").strip():
        raise ValueError("PAD_BOM_VERSION_ID_REQUIRED")
    if snapshot.get("nfb_config_submitted") is not True:
        return ()
    rows=tuple(committed_nfb_pad_draft_parts(snapshot))
    if len({p.part_id for p in rows})!=len(rows):
        raise ValueError("PAD_BOM_DUPLICATE_PHYSICAL_OWNER")
    # A committed flat source with mixed V5 depths MUST NOT silently claim
    # zero material if the selected X source was omitted on save/reopen.
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import model_spec
    physical=receiving_base_plate_values(snapshot)
    preferred=snapshot.get("receiving_base_plate")
    # When an operator explicitly selected FLAT but the committed X is
    # missing, receiving_base_plate_values() may correctly return None.
    # Never treat that unresolved outcome as zero-pad manufacturing demand.
    source_is_flat=(
        (physical is not None and physical.get("receiving_bend_pattern") in (
            "LEFT_FLAT_SIDE","RIGHT_FLAT_SIDE"))
        or (isinstance(preferred,Mapping)
            and preferred.get("pattern") in ("LEFT_FLAT_SIDE","RIGHT_FLAT_SIDE"))
    )
    if source_is_flat:
        config=snapshot.get("nfb_config")
        holes=config.get("holes") if isinstance(config,Mapping) else ()
        layer_count=config.get("layer_count") if isinstance(config,Mapping) else None
        if isinstance(holes,(list,tuple)) and type(layer_count) is int:
            expected=0
            for tier in range(layer_count):
                # Raw NFBConfig uses layer_index for the physical tier;
                # slot_index is each switch's index WITHIN that tier.
                tier_rows=tuple(row for row in holes
                                if isinstance(row,Mapping)
                                and row.get("layer_index",0 if layer_count==1 else None)==tier)
                depths=[]
                for row in tier_rows:
                    identity=parse_numeric_model_ref(row.get("model_filename"))
                    if identity is None:
                        depths=[]
                        break
                    source=model_spec(*identity)
                    if source is None or not source.dimensionally_complete:
                        raise ValueError("PAD_BOM_SELECTED_CSV_SOURCE_INCOMPLETE")
                    depths.append(float(source.depth_mm))
                if depths:
                    deepest=max(depths)
                    expected+=sum(deepest-x>1e-8 for x in depths)
            if expected and len(rows)!=expected:
                raise ValueError("PAD_BOM_CONFIRMED_WORLD_X_OR_PART_COUNT_MISSING")
    return tuple(PhysicalPartDemand(
        str(version_id),p.part_id,p.part_id,count,1,p.render_data,
    ) for p in rows)
