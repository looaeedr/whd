# -*- coding: utf-8 -*-
"""#1502: original selected DXF action exports ALL physical Receiving Bays.

One current Bay at a time is independently re-resolved from the existing
Phase6 composition. These are never duplicates of the currently selected
Bay's source, and their assembly world translation never becomes a shifted
sheet CUTTING coordinate. One atomic output includes all selected Bays.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from .contracts import ResolvedManufacturingGeometry
from .manufacturing_api import (
    save_part_render_data_dxf, verify_saved_part_render_data_dxf,
    _resolved_physical_dxf_filename,
)
from .manufacturing_export import (
    resolved_physical_render_parts, receiving_instance_namespace,
    _atomic_commit_staged_dxfs, _reject_unapproved_nfb_pad_ear_manufacturing,
    reject_unverified_receiving_nfb_tier_base, _validate_nfb_base_part_scope,
)
from .receiving_layout import (
    normalize_receiving_layout, project_receiving_bay_legacy_aliases,
)
from .receiving_nfb_committed_final_scene import _submitted_csv_holes
from .receiving_fixed_plate_formed_manufacturing import (
    _verified_formed_ear_parts, _verified_current_csv_manufacturing_owners,
)
from .receiving_ear_side_manufacturing_marking import (
    with_verified_receiving_ear_side_markings,
)
from .receiving_fixed_plate_side_check_dxf import _readback_marking_lines
from .manufacturing_scene_access import owner_render_data


def export_current_receiving_multibay_dxf(
    saved_snapshot, *, physical_bay_geometry_provider,
    flags, output_dir, overwrite=False,
):
    """Write once for each CURRENT physical Set/Bay, with no source borrowing.

    physical_bay_geometry_provider(set_index,bay_index) must supply freshly
    resolved LOCAL Bay 2D/3D scene, with the same physical piece identities
    as the already displayed canonical Phase6 assembly. It cannot authorize
    a missing NFB Base Plate, unidentified source, forged EAR/PAD or stale
    left/right world-to-UV marking.
    """
    from gui_modules.project.export_actions import _resolved_export_intention_key
    if type(overwrite) is not bool:
        raise TypeError("RECEIVING_MULTIBAY_OVERWRITE_MUST_BE_BOOL")
    if saved_snapshot.get("model") not in {"受電箱","RECEIVING"}:
        raise ValueError("RECEIVING_MULTIBAY_CURRENT_FAMILY_REQUIRED")
    if saved_snapshot.get("active_mode","set_bay")!="set_bay":
        raise ValueError("RECEIVING_MULTIBAY_NOT_QUANTITY_MODE")
    layout=normalize_receiving_layout(saved_snapshot.get("receiving_layout"))
    all_bays=tuple((i,j) for i,s in enumerate(layout["sets"])
                   for j,_ in enumerate(s["bays"]))
    if len(all_bays)<2:
        raise ValueError("RECEIVING_MULTIBAY_REQUIRES_MULTIPLE_PHYSICAL_BAYS")
    if not callable(physical_bay_geometry_provider):
        raise TypeError("RECEIVING_MULTIBAY_LIVE_BAY_RESOLVER_REQUIRED")
    output_rows=[]
    marking_proofs=[]
    expected_keys=set()
    verified_csv_filenames=set()
    verified_formed_filenames=set()
    for si,bi in all_bays:
        source=project_receiving_bay_legacy_aliases(
            saved_snapshot,set_index=si,bay_index=bi,
        )
        selection=source["_receiving_runtime_selection"]
        ns=receiving_instance_namespace(
            set_id=selection["set_id"],bay_id=selection["bay_id"],
        )
        actual=physical_bay_geometry_provider(si,bi)
        if (not isinstance(actual,ResolvedManufacturingGeometry)
                or not tuple(actual.parts or ())):
            raise ValueError("RECEIVING_MULTIBAY_CURRENT_FINALSCENE_MISSING")
        logical={p.part_key for p in actual.parts}
        if len(logical)!=len(actual.parts):
            raise ValueError("RECEIVING_MULTIBAY_DUPLICATE_LOGICAL_PHYSICAL_OWNER")
        only_independent_intent=(
            any(bool(flags.get(key)) for key in ("head", "tail", "door"))
            and not any(bool(value) for key,value in flags.items()
                        if key not in {"head", "tail", "door"})
        )
        if only_independent_intent:
            requested=tuple(key for key in ("head", "tail", "door")
                            if bool(flags.get(key)))
            if any(key not in logical for key in requested):
                raise ValueError(
                    "RECEIVING_MULTIBAY_SELECTED_INDEPENDENT_PHYSICAL_SOURCE_MISSING"
                )
        is_csv=source.get("nfb_config_submitted") is True
        selected_logical=tuple(p for p in actual.parts
            if p.part_key.startswith("custom:")
            or bool(flags.get(_resolved_export_intention_key(p.part_key),False)))
        if not selected_logical:
            continue
        # Actual HEAD/TAIL/outer DOOR FinalScene sheets have no NFB cutting
        # dependency. Selecting ONLY these physically present sheets must not
        # require valid NFB source for some other unselected sheet. Side
        # sheets are intentionally excluded (NFB EAR weld-marking dependency).
        from .receiving_nfb_v5_diagnostics import actual_unrelated_nfb_scene_parts
        unrelated=actual_unrelated_nfb_scene_parts(
            actual.parts,dependent_part_ids=(),
        )
        only_independent=(
            bool(selected_logical)
            and all(p.part_key in unrelated for p in selected_logical)
            and not any(bool(enabled) for key, enabled in flags.items()
                        if key not in {"head", "tail", "door"})
        )
        if (is_csv and not only_independent
                and not _submitted_csv_holes(source)):
            raise ValueError("RECEIVING_MULTIBAY_SUBMITTED_CSV_NOT_CURRENT")
        selected=replace(actual,parts=selected_logical)
        # The source-facing body SIDE MARKING proves its own flange contact
        # on THIS Bay. Do not import the marks or EARs of Bay 1 into Bay 2.
        body_selected=bool(flags.get("box_body")) and "box_body" in logical
        if is_csv and body_selected:
            dims=tuple(float(source[k]) for k in ("w","h","d"))
            thick=float(source["t"])
            formed,uv,_contacts=_verified_formed_ear_parts(
                source,actual,dimensions=dims,sheet_thickness=thick,
            )
            marked=with_verified_receiving_ear_side_markings(
                source,actual,dimensions=dims,sheet_thickness=thick,
            )
            selected=replace(marked,parts=tuple(p for p in marked.parts
                if p.part_key in {q.part_key for q in selected_logical}))
        else:
            formed={}
            uv=()
        physical_rows=tuple(resolved_physical_render_parts(selected))
        if not physical_rows:
            raise ValueError("RECEIVING_MULTIBAY_SELECTED_FINALSCENE_EMPTY")
        if len({key for key,_ in physical_rows})!=len(physical_rows):
            raise ValueError("RECEIVING_MULTIBAY_DUPLICATE_SHEET_SOURCE")
        approved=set()
        if is_csv and not only_independent:
            approved=_verified_current_csv_manufacturing_owners(
                source,actual,selected,
            )
            for key,render in physical_rows:
                meta=getattr(render,"metadata",None) or {}
                if (key=="base_plate"
                        or key.startswith("base_plate:nfb_layer:")
                        or meta.get("nfb_v5_trial_status")) and key not in approved:
                    raise ValueError("RECEIVING_MULTIBAY_NFB_SHEET_NOT_SOURCE_VERIFIED")
        local_rows=tuple((key,"source-checked",render) for key,render in physical_rows)
        _reject_unapproved_nfb_pad_ear_manufacturing(local_rows)
        for key,_,render in local_rows:
            if key not in approved:
                reject_unverified_receiving_nfb_tier_base(render,output_key=key)
            if (getattr(render,"metadata",None) or {}).get(
                "receiving_base_plate_unconfigured"
            ) is True:
                raise ValueError("RECEIVING_MULTIBAY_UNCONFIGURED_BASE_PLATE")
        _validate_nfb_base_part_scope(
            tuple(row for row in local_rows if row[0] not in approved),
            part_only=False,
        )
        for key,render in physical_rows:
            filename=_resolved_physical_dxf_filename(
                key,instance_namespace=ns,
            )
            if filename in expected_keys:
                raise ValueError("RECEIVING_MULTIBAY_OUTPUT_NAMESPACE_COLLISION")
            expected_keys.add(filename)
            if key in approved:
                # This exact physical Bay key was re-proven from current CSV
                # against its own real 2D/3D FinalScene, XYZ and CHECK/Q.
                verified_csv_filenames.add(filename)
            output_rows.append((ns,key,filename,render))
        for ear_id,ear_render in formed.items():
            filename=_resolved_physical_dxf_filename(
                ear_id,instance_namespace=ns,
            )
            if filename in expected_keys or ear_id in {k for k,_ in physical_rows}:
                raise ValueError("RECEIVING_MULTIBAY_DUPLICATE_FIXING_SOURCE")
            expected_keys.add(filename)
            # Scope this authorization to the exact Bay EARs constructed by
            # _verified_formed_ear_parts above, never arbitrary metadata.
            verified_formed_filenames.add(filename)
            output_rows.append((ns,ear_id,filename,ear_render))
        if is_csv and body_selected:
            for side in ("box_body:left_side","box_body:right_side"):
                owner=owner_render_data(selected,side)
                matches=tuple((key,name) for ns0,key,name,render in output_rows
                              if ns0==ns and render is owner)
                if len(matches)!=1:
                    raise ValueError("RECEIVING_MULTIBAY_SIDE_SHEET_OWNER_AMBIGUOUS")
                marking_proofs.append((matches[0][1],tuple(
                    seg for receipt in uv if receipt.side_piece_id==side
                    for seg in receipt.marking_segments
                )))
    if not output_rows:
        raise ValueError("RECEIVING_MULTIBAY_NO_SELECTED_PHYSICAL_SHEETS")
    root=Path(output_dir)
    if not overwrite and any((root/name).exists() for _,_,name,_ in output_rows):
        raise FileExistsError("RECEIVING_MULTIBAY_EXISTING_DXF_NOT_OVERWRITTEN")
    root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix=".whd-multibay-csv-",dir=root) as staging:
        staged={}
        for namespace,key,filename,render in output_rows:
            path=Path(staging)/filename
            if (filename in verified_csv_filenames
                    or filename in verified_formed_filenames):
                # Generic trial-DXF gate remains enabled everywhere else.
                # Here a fully source-verified current physical sheet is
                # serialized at the primitive boundary, then re-opened.
                from .dxf_serialization import save_scene_dxf
                save_scene_dxf(path,render.scene)
            else:
                save_part_render_data_dxf(render,path,overwrite=False)
            if not verify_saved_part_render_data_dxf(render,path).ok:
                raise ValueError("RECEIVING_MULTIBAY_SAVED_DXF_ROUNDTRIP_FAILED:"+
                                 namespace+":"+key)
            staged[namespace+":"+key]=path
        for filename,segments in marking_proofs:
            _readback_marking_lines(
                Path(staging)/filename,segments,
            )
        return _atomic_commit_staged_dxfs(
            staged,root,overwrite=overwrite,
        )
