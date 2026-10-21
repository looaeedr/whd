# -*- coding: utf-8 -*-
"""Receiving NFB installation: REAL physical faces, never sheet mid-planes.

#1502 / #1503. Source of model depths: the selected brand/model CSV, passed
by its caller. This module deliberately does not guess a brand or certify 3D,
DXF, CUTTING/BEND or weld-ear MARKING from arithmetic alone.

The shop does not apply bend compensation. In particular the NFB face-to-face
step (107 - 72 = 35) is not automatically the outside dimension of one bend.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


FIRST_SIDE_FOLD_MM = -40.0


@dataclass(frozen=True)
class ReceivingNfbSurfaceChain:
    """All Zs measured inward from the SAME outer-door physical face (mm)."""

    inner_door_outer_face_mm: float
    inner_door_inner_face_mm: float
    reference_base_nfb_face_mm: float
    reference_base_back_face_mm: float
    fixing_plate_contact_face_mm: float
    fixing_plate_back_face_mm: float
    secondary_base_nfb_face_mm: float | None
    secondary_base_back_face_mm: float | None
    nfb_face_step_mm: float | None
    second_side_fold_mm: float | None

    @property
    def fixing_plate_contact_mark_from_front_mm(self) -> float:
        """Side-wall marking DEPTH target; not a released 2D MARKING entity.

        The actual side-sheet UV/X/Y, weld outline and projection must come
        from the real side-sheet/ear assembly; never draw a bogus DXF line.
        """
        return self.fixing_plate_contact_face_mm


def receiving_nfb_second_side_fold_mm(
    *, reference_nfb_depth_mm: float, secondary_nfb_depth_mm: float,
    base_plate_thickness_mm: float,
) -> float:
    """User's NON-FOLDED two-plate inference for the 2nd side return.

    Put both virtual flat base plates against the SAME inner-door inside
    physical face:
       NFB deep mount face = inside face + deep NFB depth
       NFB shallow mount face = inside face + shallow NFB depth
       shallow back skin     = shallow mount face + base T
       second return         = deep mount face - shallow back skin

    Shihlin 107/72, T2 => (107 - 72) - 2 = 33 mm.
    There is ONE base-plate T deduction, not two. The real pair of front
    NFB mounting surfaces is still 35 mm apart. FIRST side fold stays -40.
    This is a target material/face-chain dimension, NOT a claim that every
    BEND station-to-station material interval or one folded outside envelope
    equals 33, and not approval of manufacture.
    """
    d, s, t = (float(reference_nfb_depth_mm),
               float(secondary_nfb_depth_mm), float(base_plate_thickness_mm))
    if not all(isfinite(x) and x > 0 for x in (d, s, t)):
        raise ValueError("NFB depth and base plate T must be positive finite values")
    if d <= s:
        raise ValueError("reference NFB depth must be deeper than secondary")
    result = d - s - t
    if result <= 0:
        raise ValueError("NFB depth step too small for physical second side return")
    return result


def resolve_receiving_nfb_surface_chain(
    *, inner_door_outer_face_from_front_mm: float,
    inner_door_thickness_mm: float,
    base_plate_thickness_mm: float,
    fixing_plate_thickness_mm: float,
    reference_nfb_depth_mm: float,
    secondary_nfb_depth_mm: float | None = None,
) -> ReceivingNfbSurfaceChain:
    """Compute relative physical face positions without double-counting T.

    The 80-mm inner-door offset in a live GUI/3D snapshot may be a CENTER
    offset; only pass 80 here if verified to be its OUTER physical face.
    Callers must first resolve actual folded-mesh skins from the authoritative
    assembly transform. Passing an unverified placement center is forbidden.

    Deep base plate and BOTH fixing plates share one translated Z datum.
    The base BACK skin touches the fixing plate FRONT skin with zero gap.
    """
    outer, it, bt, ft, deep = (float(inner_door_outer_face_from_front_mm),
                             float(inner_door_thickness_mm),
                             float(base_plate_thickness_mm),
                             float(fixing_plate_thickness_mm),
                             float(reference_nfb_depth_mm))
    if not isfinite(outer) or outer < 0:
        raise ValueError("inner door outer physical face requires finite nonnegative offset")
    if not all(isfinite(v) and v > 0 for v in (it, bt, ft, deep)):
        raise ValueError("inner door/base/fixing thickness and NFB depth must be positive")
    door_inner = outer + it
    deep_front = door_inner + deep
    deep_back = deep_front + bt
    secondary_front = secondary_back = face_step = return_mm = None
    if secondary_nfb_depth_mm is not None:
        shallow = float(secondary_nfb_depth_mm)
        return_mm = receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=deep, secondary_nfb_depth_mm=shallow,
            base_plate_thickness_mm=bt,
        )
        secondary_front = door_inner + shallow
        secondary_back = secondary_front + bt
        face_step = deep_front - secondary_front
        assert abs((deep_front - secondary_back) - return_mm) < 1e-8
    return ReceivingNfbSurfaceChain(
        inner_door_outer_face_mm=outer,
        inner_door_inner_face_mm=door_inner,
        reference_base_nfb_face_mm=deep_front,
        reference_base_back_face_mm=deep_back,
        fixing_plate_contact_face_mm=deep_back,
        fixing_plate_back_face_mm=deep_back + ft,
        secondary_base_nfb_face_mm=secondary_front,
        secondary_base_back_face_mm=secondary_back,
        nfb_face_step_mm=face_step,
        second_side_fold_mm=return_mm,
    )


def selected_receiving_nfb_depth_pair_mm(
    brand: str, model_refs: tuple[str, str] | list[str],
) -> tuple[float, float]:
    """Resolve EXACT brand's two selected NFB references to (deep, shallow).

    Read depths from the operator's current index CSV or typed V5 CSV;
    do not store a second user-owned depth setting. This is a PURE depth
    projection, not evidence that two slots own one manufactured base.
    The caller must associate the selected NFB scope/Bay and the existing
    BasePlatePartSpec, and verify it is a CENTER_DOUBLE_SIDE_FOLD part.
    """
    if (not isinstance(model_refs, (tuple, list))
            or len(model_refs) != 2
            or not all(isinstance(ref, str) for ref in model_refs)):
        raise ValueError("two source-selected NFB model references required")
    from .receiving_nfb_model_identity import (
        parse_numeric_model_ref, selected_numeric_spec,
    )
    from .receiving_switch_model_catalog import model_depth_mm
    depths = []
    for ref in model_refs:
        if ref.startswith("nfbv5:"):
            spec = selected_numeric_spec(brand, ref)
            depth = spec.depth_mm if spec is not None else None
        else:
            depth = model_depth_mm(brand, ref)
        if depth is None:
            raise ValueError("NFB physical depth unknown for exact brand/model source")
        depths.append(float(depth))
    return tuple(sorted(depths, reverse=True))


def _source_depth_for_submitted_hole(hole, *, legacy_set_brand):
    """Resolve one physical switch from its stored brand + CSV model owner.

    The current Receiving Set no longer stores switch_brand. The typed V5
    model identity names its own source brand; legacy DXF filenames still
    require an explicit brand (per-hole or legacy Set) for backward data.
    Never infer a missing model's physical depth from another NFB's source.
    """
    from collections.abc import Mapping
    from .receiving_nfb_model_identity import (
        parse_numeric_model_ref, selected_numeric_spec,
    )
    from .receiving_switch_model_catalog import model_depth_mm

    if not isinstance(hole, Mapping):
        raise ValueError("RECEIVING_NFB_DEPTH_HOLE_SOURCE_INVALID")
    filename = hole.get("model_filename")
    if not isinstance(filename, str) or not filename:
        raise ValueError("RECEIVING_NFB_DEPTH_MODEL_SOURCE_MISSING")
    parsed = parse_numeric_model_ref(filename)
    brand = hole.get("source_brand", legacy_set_brand or (
        parsed[0] if parsed is not None else None
    ))
    if not isinstance(brand, str) or not brand:
        raise ValueError("RECEIVING_NFB_DEPTH_BRAND_SOURCE_MISSING")
    if filename.startswith("nfbv5:"):
        if parsed is None or parsed[0] != brand:
            raise ValueError("RECEIVING_NFB_DEPTH_V5_BRAND_IDENTITY_MISMATCH")
        spec = selected_numeric_spec(brand, filename)
        depth = spec.depth_mm if spec is not None else None
    else:
        depth = model_depth_mm(brand, filename)
    if depth is None:
        raise ValueError("RECEIVING_NFB_DEPTH_CSV_MODEL_DEPTH_MISSING")
    depth = float(depth)
    if not isfinite(depth) or depth <= 0:
        raise ValueError("RECEIVING_NFB_DEPTH_CSV_MODEL_DEPTH_INVALID")
    return depth


def committed_receiving_nfb_depth_pair_mm(snapshot) -> tuple[float, float] | None:
    """Derive a CENTER base depth pair from an ACTUALLY submitted Bay's holes.

    Do not manufacture from transient NFB draft, a legacy list of filenames,
    a stale unselected Bay, or a duplicate depth-input field. An exported
    BasePlatePartSpec must consume the same (Set, Bay) currently being viewed.
    The Set's switch_brand is the existing brand owner; there is no second
    editable Base Plate brand. This is only a *depth source resolution*, not
    whole-box MFG release or Z/weld-face certification.
    """
    from collections.abc import Mapping
    from .receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
    if not isinstance(snapshot, Mapping):
        raise TypeError("Receiving physical source snapshot must be a mapping")
    if "nfb_config_submitted" not in snapshot:
        # Fold Designer's canonical workspace snapshot stores submitted NFBs
        # under Receiving Set/Bay rather than as a root alias. Project only
        # a UNIQUE one-Set/one-Bay source (or an explicitly selected Bay).
        # Multi-Bay with no selection MUST NOT leak another Bay's depth.
        layout = snapshot.get("receiving_layout")
        sets = layout.get("sets") if isinstance(layout, Mapping) else None
        selected_bay = None
        if isinstance(sets, (list, tuple)) and sets:
            runtime = snapshot.get("_receiving_runtime_selection")
            if isinstance(runtime, Mapping):
                si,bi=runtime.get("set_index"),runtime.get("bay_index")
                if (type(si) is int and 0<=si<len(sets)
                        and isinstance(sets[si], Mapping)):
                    chosen = sets[si]
                    bays = chosen.get("bays")
                    if (chosen.get("stable_id")==runtime.get("set_id")
                            and isinstance(bays, (list, tuple))
                            and type(bi) is int and 0<=bi<len(bays)
                            and isinstance(bays[bi], Mapping)
                            and bays[bi].get("stable_id")==runtime.get("bay_id")):
                        selected_bay=bays[bi]
            elif (len(sets)==1 and isinstance(sets[0], Mapping)
                  and isinstance(sets[0].get("bays"), (list, tuple))
                  and len(sets[0]["bays"])==1):
                selected_bay=sets[0]["bays"][0]
        if not isinstance(selected_bay, Mapping):
            return None
        if selected_bay.get("nfb_config_submitted") is not True:
            return None
        return committed_receiving_nfb_depth_pair_mm({
            **snapshot,
            "nfb_config_submitted": True,
            "nfb_config": selected_bay.get("nfb_config"),
        })
    if snapshot.get("nfb_config_submitted") is not True:
        return None
    config = snapshot.get("nfb_config")
    if not isinstance(config, Mapping):
        raise ValueError("submitted NFBConfig missing from live Bay scope")
    holes = config.get("holes")
    if not isinstance(holes, (tuple, list)) or not holes:
        raise ValueError("submitted NFBConfig physical holes missing")
    # Only TWO distinct NFBs on the SAME physical row can determine one
    # second side fold; others retain preview and need independent authority.
    if config.get("layer_count") != 1 or len(holes) != 2:
        return None
    if not all(isinstance(row, Mapping) for row in holes):
        raise ValueError("submitted NFBConfig invalid physical hole")
    names = tuple(row.get("model_filename") for row in holes)
    if not all(isinstance(name, str) and name for name in names):
        raise ValueError("submitted NFBConfig has missing model filename")
    # Same filename alone does not prove same model across different brands.
    layout = snapshot.get("receiving_layout")
    if not isinstance(layout, Mapping):
        raise ValueError("submitted NFB depth has no owning Receiving Set")
    sets = layout.get("sets")
    if not isinstance(sets, (list, tuple)) or not sets:
        raise ValueError("submitted NFB depth has no physical Receiving Set")
    runtime = snapshot.get(RECEIVING_RUNTIME_SELECTION_KEY)
    if isinstance(runtime, Mapping):
        index = runtime.get("set_index")
        bay_index = runtime.get("bay_index")
        if type(index) is not int or not 0 <= index < len(sets):
            raise ValueError("Receiving selected NFB Set index invalid")
        chosen = sets[index]
        if (not isinstance(chosen, Mapping)
                or chosen.get("stable_id") != runtime.get("set_id")):
            raise ValueError("Receiving NFB selected Set identity drift")
        bays = chosen.get("bays")
        if (not isinstance(bays, (list, tuple))
                or type(bay_index) is not int or not 0 <= bay_index < len(bays)
                or not isinstance(bays[bay_index], Mapping)
                or bays[bay_index].get("stable_id") != runtime.get("bay_id")
                or bays[bay_index].get("nfb_config_submitted") is not True
                or bays[bay_index].get("nfb_config") != config):
            raise ValueError("Receiving NFB selected Bay/config identity drift")
    elif len(sets) == 1 and isinstance(sets[0], Mapping):
        chosen = sets[0]
        bays = chosen.get("bays")
        if (not isinstance(bays, (tuple, list)) or len(bays) != 1
                or not isinstance(bays[0], Mapping)
                or bays[0].get("nfb_config_submitted") is not True
                or bays[0].get("nfb_config") != config):
            raise ValueError("Receiving NFB active Bay identity ambiguous")
    else:
        raise ValueError("Receiving NFB active Set identity ambiguous")
    legacy_brand = chosen.get("switch_brand")
    depths = tuple(sorted((
        _source_depth_for_submitted_hole(
            hole, legacy_set_brand=legacy_brand,
        ) for hole in holes
    ), reverse=True))
    if abs(depths[0] - depths[1]) <= 1e-9:
        return None
    receiving_nfb_second_side_fold_mm(
        reference_nfb_depth_mm=depths[0],
        secondary_nfb_depth_mm=depths[1],
        base_plate_thickness_mm=float(snapshot.get("t", 0)),
    )
    return depths


def committed_receiving_flat_nfb_depth_mm(snapshot) -> float | None:
    """Exact single-depth NFB source for LEFT/RIGHT non-side-folded base.

    A flat physical mounting web can share ONE verified depth across its NFB
    holes. Read the active submitted Bay's actual Set brand and operator model
    reference, never infer depth from a filename suffix or another Bay. Two
    different models/depths require independent mounting/PAD certification,
    so a flat plate cannot claim a certified common NFB face for them.
    """
    from collections.abc import Mapping
    from .receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
    if not isinstance(snapshot,Mapping):
        raise TypeError("Receiving flat NFB depth needs physical snapshot")
    if snapshot.get("nfb_config_submitted") is False:
        return None
    layout=snapshot.get("receiving_layout")
    sets=layout.get("sets") if isinstance(layout,Mapping) else None
    if not isinstance(sets,(tuple,list)) or not sets:
        return None
    runtime=snapshot.get(RECEIVING_RUNTIME_SELECTION_KEY)
    selected=None
    if isinstance(runtime,Mapping):
        si,bi=runtime.get("set_index"),runtime.get("bay_index")
        if (type(si) is not int or not 0<=si<len(sets)
                or not isinstance(sets[si],Mapping)
                or sets[si].get("stable_id")!=runtime.get("set_id")):
            raise ValueError("RECEIVING_FLAT_NFB_SET_SCOPE_DRIFT")
        chosen=sets[si]
        bays=chosen.get("bays")
        if (not isinstance(bays,(list,tuple)) or type(bi) is not int
                or not 0<=bi<len(bays) or not isinstance(bays[bi],Mapping)
                or bays[bi].get("stable_id")!=runtime.get("bay_id")):
            raise ValueError("RECEIVING_FLAT_NFB_BAY_SCOPE_DRIFT")
        selected=(chosen,bays[bi])
    elif (len(sets)==1 and isinstance(sets[0],Mapping)
          and isinstance(sets[0].get("bays"),(tuple,list))
          and len(sets[0]["bays"])==1):
        selected=(sets[0],sets[0]["bays"][0])
    else:
        # Ambiguous physical source cannot position a unique flat plate.
        return None
    chosen,bay=selected
    if bay.get("nfb_config_submitted") is not True:
        return None
    config=bay.get("nfb_config")
    if not isinstance(config,Mapping):
        raise ValueError("RECEIVING_FLAT_NFB_SUBMITTED_CONFIG_MISSING")
    if ("nfb_config" in snapshot and snapshot["nfb_config"] != config):
        raise ValueError("RECEIVING_FLAT_NFB_CONFIG_SCOPE_DRIFT")
    holes=config.get("holes")
    if not isinstance(holes,(tuple,list)) or not holes:
        raise ValueError("RECEIVING_FLAT_NFB_REQUIRES_SUBMITTED_HOLES_SAME_ROW")
    if not all(isinstance(h,Mapping) for h in holes):
        raise ValueError("RECEIVING_FLAT_NFB_INVALID_HOLE_SOURCE")
    count=config.get("layer_count")
    if count!=1 or any(
        h.get("layer_count",count)!=1
        or type(h.get("slot_index",0)) is not int
        or h.get("slot_index",0)<0
        for h in holes
    ):
        raise ValueError("RECEIVING_FLAT_NFB_MULTIPLE_ROWS_NEED_DISTINCT_BASE")
    # Horizontal slot_index is not a vertical tier. An arbitrary count of
    # source-confirmed same-depth switches may share this real flat sheet;
    # the downstream FinalScene checks each generated hole for containment
    # and collisions. Distinct model aliases still need identical source.
    models={str(h.get("model_filename") or "").strip() for h in holes}
    if "" in models:
        raise ValueError("RECEIVING_FLAT_NFB_DIFFERENT_MODELS_NEED_PAD_OR_CENTER")
    legacy_brand=chosen.get("switch_brand")
    if len(models)!=1:
        from .receiving_nfb_model_identity import selected_numeric_spec
        signatures=set()
        for hole in holes:
            model_ref=str(hole["model_filename"])
            brand=hole.get("source_brand",legacy_brand)
            if not model_ref.startswith("nfbv5:"):
                raise ValueError("RECEIVING_FLAT_NFB_DIFFERENT_MODELS_NEED_PAD_OR_CENTER")
            spec=selected_numeric_spec(brand,model_ref)
            if spec is None or not spec.dimensionally_complete:
                raise ValueError("RECEIVING_FLAT_NFB_DIFFERENT_MODELS_NEED_PAD_OR_CENTER")
            signatures.add((
                brand,spec.width_mm,spec.height_mm,spec.opening_mm,
                spec.screw_pitch_mm,spec.screw_diameter_mm,
                spec.screw_offset_x_mm,spec.screw_offset_y_mm,spec.depth_mm,
            ))
        if len(signatures)!=1:
            raise ValueError("RECEIVING_FLAT_NFB_DIFFERENT_MODELS_NEED_PAD_OR_CENTER")
    depths=tuple(
        _source_depth_for_submitted_hole(
            hole, legacy_set_brand=legacy_brand,
        ) for hole in holes
    )
    if any(abs(depth-depths[0])>1e-9 for depth in depths):
        raise ValueError("RECEIVING_FLAT_NFB_DIFFERENT_DEPTHS_NEED_PAD")
    return depths[0]
