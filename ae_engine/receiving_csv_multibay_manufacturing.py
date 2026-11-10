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
from .manufacturing_export_selection import (
    resolved_export_intention_key, receiving_export_part_selected,
)



def _verified_nfb_composed_pair_rows(layout, requests, output_root, guard, *, thickness_mm):
    """Engine-only: verify every committed NFB pair before composing flat UV.

    Nothing from this proof stage becomes a separately published PART_ONLY
    batch. An already-approved pair may be placed alongside independent
    approved core flats, but the result never upgrades the cabinet to MFG-2.
    """
    from .manufacturing_contracts import (
        ManufacturingResolveRequest, thaw_manufacturing_value,
        manufacturing_request_fingerprint,
    )
    from .receiving_nfb_manufacturing_transport import restore_receiving_nfb_dto_selectors
    from .receiving_nfb_batch_pair_export import export_receiving_committed_nfb_csv_bays
    from .receiving_nfb_default_pair_request import (
        receiving_committed_nfb_pair_request_for_bay,
    )
    from .receiving_nfb_pair_export import (
        _committed_csv_brand_source_hashes, _require_committed_csv_source_unchanged,
    )
    from .manufacturing_export import resolved_physical_dxf_filename
    from .manufacturing_api import resolve_manufacturing_request
    from collections.abc import Sequence

    if not isinstance(requests, (tuple, list)) or not requests:
        raise ValueError("RECEIVING_COMPOSED_NFB_ALL_BAYS_REQUIRED")
    expected = tuple(
        (
            str(group["stable_id"]), str(bay["stable_id"]),
            float(bay["width"]), float(bay["height"]), float(bay["depth"]),
        )
        for group in layout["sets"] for bay in group["bays"]
    )
    if len(requests) != len(expected):
        raise ValueError("RECEIVING_COMPOSED_NFB_ALL_BAYS_REQUIRED")
    positions = tuple(
        (si, bi) for si, group in enumerate(layout["sets"])
        for bi, _bay in enumerate(group["bays"])
    )
    source_guards = []
    for (si, bi), request, (set_id, bay_id, width, height, depth) in zip(
        positions, requests, expected
    ):
        if not isinstance(request, ManufacturingResolveRequest):
            raise TypeError("RECEIVING_COMPOSED_NFB_ORIGINAL_REQUEST_REQUIRED")
        snapshot = restore_receiving_nfb_dto_selectors(
            thaw_manufacturing_value(request.input_snapshot)
        )
        actual_id = snapshot.get("_receiving_runtime_selection")
        # The immutable Request transport already contains its original
        # canonical Set/Bay layout. Read just physical identity/dimensions:
        # normalize_receiving_layout would re-interpret serialized current
        # Hole Editor candidates and reject valid already-verified Features.
        submitted_layout = snapshot.get("receiving_layout")
        if (not isinstance(submitted_layout, dict)
                or not isinstance(submitted_layout.get("sets"), (tuple, list))):
            raise ValueError("RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH")
        try:
            submitted_bays = tuple(
                (
                    str(group["stable_id"]), str(bay["stable_id"]),
                    float(bay["width"]), float(bay["height"]), float(bay["depth"]),
                )
                for group in submitted_layout["sets"] for bay in group["bays"]
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH"
            ) from exc
        if (not isinstance(actual_id, dict)
                or submitted_bays != expected
                or (actual_id.get("set_id"), actual_id.get("bay_id")) != (set_id, bay_id)
                or any(abs(float(snapshot.get(name, -1)) - dimension) > 1e-6
                       for name, dimension in (("w", width), ("h", height), ("d", depth)))):
            raise ValueError("RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH")
        # Never mix an approved NFB Request from another project that happens
        # to use the same default Set/Bay IDs and W/H/D. Rebuild the exact
        # public Engine Request from THIS saved Layout and its original T,
        # then require identical canonical manufacturing semantics.
        try:
            saved_request = receiving_committed_nfb_pair_request_for_bay(
                layout, set_index=si, bay_index=bi,
                thickness_mm=thickness_mm,
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise ValueError(
                "RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH"
            ) from exc
        if (manufacturing_request_fingerprint(saved_request)
                != manufacturing_request_fingerprint(request)):
            raise ValueError("RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH")
        source = _submitted_csv_holes(snapshot)
        if not source:
            raise ValueError("RECEIVING_COMPOSED_NFB_COMMITTED_SOURCE_REQUIRED")
        source_guards.append((source[1], _committed_csv_brand_source_hashes(source[1])))

    def checked_guard():
        guard()
        for holes, initial_hashes in source_guards:
            _require_committed_csv_source_unchanged(holes, initial_hashes)

    checked_guard()
    rows = []
    approved = {}
    # Both the original single-Bay pair proof and the multi-Bay transaction
    # must pass before the combined packer is given any NFB physical flat.
    with TemporaryDirectory(prefix=".whd-composed-nfb-proof-", dir=str(output_root)) as temp:
        batch = export_receiving_committed_nfb_csv_bays(
            requests, output_directory=temp, pre_commit_guard=checked_guard,
        )
        if len(batch.bays) != len(expected):
            raise ValueError("RECEIVING_COMPOSED_NFB_BATCH_INCOMPLETE")
        for request, (set_id, bay_id, receipt) in zip(requests, batch.bays):
            ns = receiving_instance_namespace(set_id=set_id, bay_id=bay_id)
            if (set_id, bay_id) != (
                expected[len(approved)][0], expected[len(approved)][1]
            ):
                raise ValueError("RECEIVING_COMPOSED_NFB_BATCH_IDENTITY_MISMATCH")
            physical = resolve_manufacturing_request(request).geometry
            physical_rows = tuple(resolved_physical_render_parts(physical))
            keys = {key for key, _render in physical_rows}
            doors = {key for key in keys if key.startswith("inner_door:")}
            bases = {key for key in keys if (
                key == "base_plate" or key.startswith("base_plate:nfb_layer:")
            )}
            if not doors or len(doors) != 1 or not bases or keys != doors | bases:
                raise ValueError("RECEIVING_COMPOSED_NFB_PAIR_INVENTORY_INVALID")
            receipt_paths = (receipt.inner_door_path,) + (
                (receipt.base_plate_path,)
                if hasattr(receipt, "base_plate_path")
                else tuple(receipt.base_plate_paths)
            )
            expected_paths = {
                str(Path(temp) / resolved_physical_dxf_filename(
                    key, instance_namespace=ns, box_body_physical_piece_roles=(),
                )) for key in keys
            }
            if set(receipt_paths) != expected_paths:
                raise ValueError("RECEIVING_COMPOSED_NFB_PAIR_FILE_ID_MISMATCH")
            for key, render in physical_rows:
                filename = resolved_physical_dxf_filename(
                    key, instance_namespace=ns, box_body_physical_piece_roles=(),
                )
                proof = Path(temp) / filename
                # Match the canonical second resolution to the *actually*
                # saved-and-reopened part-only DXF, not a claimed ready flag.
                if not verify_saved_part_render_data_dxf(render, proof).ok:
                    raise ValueError("RECEIVING_COMPOSED_NFB_PART_ROUNDTRIP_MISMATCH")
                rows.append((ns, key, filename, render))
            approved[ns] = frozenset(keys)
        checked_guard()
    return tuple(rows), approved, checked_guard


def export_current_receiving_multibay_dxf(
    saved_snapshot, *, physical_bay_geometry_provider,
    flags, output_dir, overwrite=False,
    group_mode=None, pre_commit_guard=None, nfb_pair_requests=None,
    include_saved_nfb_pairs=False, emit_debug=False,
):
    """Write once for each CURRENT physical Set/Bay, with no source borrowing.

    physical_bay_geometry_provider(set_index,bay_index) must supply freshly
    resolved LOCAL Bay 2D/3D scene, with the same physical piece identities
    as the already displayed canonical Phase6 assembly. It cannot authorize
    a missing NFB Base Plate, unidentified source, forged EAR/PAD or stale
    left/right world-to-UV marking.
    """
    if group_mode is not None:
        from .receiving_dxf_groups import RECEIVING_COMPOSED_DXF_MODES
        if group_mode not in RECEIVING_COMPOSED_DXF_MODES:
            raise ValueError("RECEIVING_COMPOSED_DXF_MODE_UNSUPPORTED")
        if not callable(pre_commit_guard):
            raise ValueError("RECEIVING_COMPOSED_DXF_PRECOMMIT_GUARD_REQUIRED")
        pre_commit_guard()
    if type(emit_debug) is not bool:
        raise TypeError("RECEIVING_DEBUG_EXPORT_FLAG_MUST_BE_BOOL")
    if emit_debug and group_mode is None:
        raise ValueError("RECEIVING_DEBUG_VERIFIED_GROUP_REQUIRED")
    if type(overwrite) is not bool:
        raise TypeError("RECEIVING_MULTIBAY_OVERWRITE_MUST_BE_BOOL")
    if type(include_saved_nfb_pairs) is not bool:
        raise TypeError("RECEIVING_COMPOSED_NFB_SAVED_SOURCE_FLAG_MUST_BE_BOOL")
    if include_saved_nfb_pairs and (group_mode is None or nfb_pair_requests is not None):
        raise ValueError("RECEIVING_COMPOSED_NFB_SAVED_SOURCE_SCOPE_INVALID")
    # Canonical Family Registry owns aliases for every GUI/Engine client.
    # Raw string matching rejected the registered lowercase "receiving" alias.
    from .cabinet_types.policy import canonical_family_name
    if canonical_family_name(saved_snapshot) != "受電箱":
        raise ValueError("RECEIVING_MULTIBAY_CURRENT_FAMILY_REQUIRED")
    if saved_snapshot.get("active_mode","set_bay")!="set_bay":
        raise ValueError("RECEIVING_MULTIBAY_NOT_QUANTITY_MODE")
    layout=normalize_receiving_layout(saved_snapshot.get("receiving_layout"))
    # Externally supplied approved NFB pairs may join independent core flats.
    # The same saved-layout fingerprint check later still rejects foreign NFB.
    # GUI include_saved_nfb_pairs retains its own original selection policy.
    independent_core_with_nfb_pair = (
        nfb_pair_requests is not None and not include_saved_nfb_pairs
    )
    if independent_core_with_nfb_pair:
        core_keys = {"box_body", "door", "head", "tail"}
        if (not any(bool(flags.get(k)) for k in core_keys)
                or any(bool(v) for k, v in flags.items() if k not in core_keys)):
            raise ValueError("RECEIVING_COMPOSED_NFB_INDEPENDENT_CORE_SCOPE_REQUIRED")
    all_bays=tuple((i,j) for i,s in enumerate(layout["sets"])
                   for j,_ in enumerate(s["bays"]))
    # The original main export button has no second NFB output directory.
    # If the operator selected both physical pair roles, derive the immutable
    # original Door/Base Requests from THIS saved Set/Bay layout in Engine.
    # Never approve X here, borrow one Bay, or silently output a partial pair.
    if (include_saved_nfb_pairs and bool(flags.get("door"))
            and bool(flags.get("base_plate"))):
        submissions = tuple(
            layout["sets"][si]["bays"][bi].get("nfb_config_submitted") is True
            for si,bi in all_bays
        )
        if any(submissions):
            if not all(submissions):
                raise ValueError("RECEIVING_COMPOSED_NFB_PARTIAL_BAY_CONFIRMATION")
            from .receiving_nfb_default_pair_request import (
                receiving_committed_nfb_pair_request_for_bay,
            )
            nfb_pair_requests = tuple(
                receiving_committed_nfb_pair_request_for_bay(
                    layout, set_index=si, bay_index=bi,
                    thickness_mm=saved_snapshot.get("t"),
                )
                for si,bi in all_bays
            )
    if len(all_bays)<1 or (len(all_bays)<2 and group_mode is None):
        raise ValueError("RECEIVING_MULTIBAY_REQUIRES_MULTIPLE_PHYSICAL_BAYS")
    if not callable(physical_bay_geometry_provider):
        raise TypeError("RECEIVING_MULTIBAY_LIVE_BAY_RESOLVER_REQUIRED")
    output_rows=[]
    # Preserve canonical BoxBody owner across the verified flat-sheet sink;
    # the grouped composer otherwise sees only detached PartRenderData.
    box_body_owners={}
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
        # Explicitly selecting Base requires an actual physical Base owner in
        # EVERY Bay. An UNCONFIGURED Bay (or a stale FinalScene provider) must
        # not silently produce a partial batch omitting the selected sheet.
        if (bool(flags.get("base_plate")) and nfb_pair_requests is None
                and not any(key=="base_plate" or key.startswith("base_plate:nfb_layer:")
                            for key in logical)):
            raise ValueError(
                "RECEIVING_MULTIBAY_SELECTED_BASE_PLATE_PHYSICAL_SOURCE_MISSING"
            )
        only_independent_intent=(
            any(bool(flags.get(key)) for key in ("head", "tail", "door"))
            and not any(bool(value) for key,value in flags.items()
                        if key not in {"head", "tail", "door"})
        )
        if only_independent_intent:
            requested=tuple(key for key in ("head", "tail", "door")
                            if bool(flags.get(key)))
            # An actual multi-Door FinalScene uses canonical cell IDs
            # (door_c1_r1 / door_c1_r2), not the legacy "door" root.
            # Check presence with the SAME Engine physical-to-intent projection
            # used below for selection; never invent or borrow any Bay scene.
            if any(
                not any(resolved_export_intention_key(part_key) == key
                        for part_key in logical)
                for key in requested
            ):
                raise ValueError(
                    "RECEIVING_MULTIBAY_SELECTED_INDEPENDENT_PHYSICAL_SOURCE_MISSING"
                )
        is_csv=(source.get("nfb_config_submitted") is True
                and not independent_core_with_nfb_pair)
        selected_logical=tuple(p for p in actual.parts
            if (p.part_key.startswith("custom:")
                or receiving_export_part_selected(p.part_key,flags))
            and not (nfb_pair_requests is not None and (
                p.part_key.startswith("inner_door:")
                or p.part_key=="base_plate"
                or p.part_key.startswith("base_plate:nfb_layer:")
            )))
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
        if body_selected:
            from .manufacturing_render_data import BoxBodyStructureRenderData
            from .receiving_layout import derive_bay_lock_state
            from .sheetmetal_drawing import CirclePrimitive
            body_owners = tuple(
                part.render_data for part in actual.parts
                if part.part_key == "box_body"
                and isinstance(part.render_data, BoxBodyStructureRenderData)
            )
            if len(body_owners) != 1:
                raise ValueError("RECEIVING_MULTIBAY_BODY_OWNER_MISSING")
            body_owner = body_owners[0]
            expected_locks = derive_bay_lock_state(
                layout, set_index=si, bay_index=bi,
            )
            for role, joined in (
                ("left_side", expected_locks[0]),
                ("right_side", expected_locks[1]),
            ):
                actual_pieces = tuple(
                    piece for piece in body_owner.pieces if piece.role == role
                )
                if len(actual_pieces) != 1:
                    raise ValueError("RECEIVING_MULTIBAY_SIDE_LOCK_TOPOLOGY_MISMATCH")
                render = actual_pieces[0].render_data
                metadata = render.metadata or {}
                if (metadata.get("baseline_side_lock_participation") is not joined
                        or metadata.get("baseline_side_lock_certified_count") != 6
                        or metadata.get("baseline_feature_count") != (9 if joined else 3)):
                    raise ValueError("RECEIVING_MULTIBAY_SIDE_LOCK_TOPOLOGY_MISMATCH")
                def matching_holes(radius):
                    return sum(
                        isinstance(primitive, CirclePrimitive)
                        and primitive.layer == "CUTTING"
                        and abs(float(primitive.radius) - radius) < 1e-6
                        for primitive in render.scene.primitives
                    )
                if (matching_holes(5.25) != (6 if joined else 0)
                        or matching_holes(8.0) != (2 if joined else 0)):
                    raise ValueError("RECEIVING_MULTIBAY_SIDE_LOCK_TOPOLOGY_MISMATCH")
            box_body_owners[ns] = body_owner
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
        # #1490: each physical Bay has independent NFB and PAD owners. A
        # complete original BODY+DOOR+BASE selection must include each Bay's
        # genuine PAD; never borrow another Bay or rely on display skins alone.
        if (is_csv and body_selected and bool(flags.get("door"))
                and bool(flags.get("base_plate"))):
            from .receiving_nfb_pad_pair_manufacturing import (
                verified_pad_base_physical_sheets,
            )
            pad_rows, proven = verified_pad_base_physical_sheets(
                source, actual.parts, allow_empty=True,
            )
            if pad_rows and not (
                any(p.part_key.startswith("inner_door:")
                    for p in selected_logical)
                and any(p.part_key == "base_plate"
                    or p.part_key.startswith("base_plate:nfb_layer:")
                    for p in selected_logical)
            ):
                raise ValueError(
                    "RECEIVING_MULTIBAY_FULL_NFB_PHYSICAL_SELECTION_INCOMPLETE"
                )
            for pad in pad_rows:
                pad_id=pad.physical_id
                filename=_resolved_physical_dxf_filename(
                    pad_id,instance_namespace=ns,
                )
                if (filename in expected_keys or pad_id in formed
                        or pad_id in {key for key,_ in physical_rows}):
                    raise ValueError("RECEIVING_MULTIBAY_PAD_OWNER_COLLISION")
                expected_keys.add(filename)
                # This precise PAD is certified by the current Bay's committed
                # CSV, verified Base and full-T geometry before staging.
                verified_formed_filenames.add(filename)
                output_rows.append((ns,pad_id,filename,proven[pad_id]))
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
                ),owner.scene))
    if not output_rows and nfb_pair_requests is None:
        raise ValueError("RECEIVING_MULTIBAY_NO_SELECTED_PHYSICAL_SHEETS")
    root=Path(output_dir)
    if not overwrite and any((root/name).exists() for _,_,name,_ in output_rows):
        raise FileExistsError("RECEIVING_MULTIBAY_EXISTING_DXF_NOT_OVERWRITTEN")
    root.mkdir(parents=True,exist_ok=True)
    nfb_approved = {}
    grouping_guard = pre_commit_guard
    if nfb_pair_requests is not None:
        if group_mode is None or bool(flags.get("inner_door")):
            raise ValueError("RECEIVING_COMPOSED_NFB_GROUP_SCOPE_REQUIRED")
        nfb_rows, nfb_approved, grouping_guard = _verified_nfb_composed_pair_rows(
            layout, nfb_pair_requests, root, pre_commit_guard,
            thickness_mm=saved_snapshot.get("t"),
        )
        for namespace, key, filename, render in nfb_rows:
            if filename in expected_keys:
                raise ValueError("RECEIVING_COMPOSED_NFB_DUPLICATE_PHYSICAL_SHEET")
            expected_keys.add(filename)
            verified_csv_filenames.add(filename)
            output_rows.append((namespace, key, filename, render))
    if not output_rows:
        raise ValueError("RECEIVING_MULTIBAY_NO_SELECTED_PHYSICAL_SHEETS")
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
        for filename,segments,source_scene in marking_proofs:
            _readback_marking_lines(
                Path(staging)/filename, segments,
                # Physical Bay source scoped before any other Bay is processed.
                check_scene=source_scene,
            )
        if group_mode is not None:
            from .receiving_dxf_groups import commit_verified_receiving_groups
            return commit_verified_receiving_groups(
                layout, group_mode, output_rows, staging, root,
                pre_commit_guard=grouping_guard, overwrite=overwrite,
                box_body_owner_by_namespace=box_body_owners,
                _verified_nfb_pair_parts_by_namespace=nfb_approved,
                emit_debug=emit_debug,
            )
        return _atomic_commit_staged_dxfs(
            staged,root,overwrite=overwrite,
        )
