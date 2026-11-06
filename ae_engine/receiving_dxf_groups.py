"""#2692 canonical Receiving Set/Bay manufacturing DXF grouping.

Physical first/last Bay is determined from each Set's topology, never HEAD or
TAIL *sheet* roles. The existing current-Bay source and EAR/PAD/NFB gates must
have verified EVERY staged physical sheet before this module runs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from .contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, receiving_instance_namespace,
)
from .panel_naming import normalize_panel_name
from .receiving_layout import normalize_receiving_layout


RECEIVING_COMPOSED_DXF_MODES = frozenset({"PER_SET", "ALL", "END_VS_MIDDLE"})


def _taipei_output_stamp():
    """Actual export minute, not the input DXF modification timestamp."""
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d%H%M")


def _group_output_filename(legacy_name, cells, stamp):
    """Name only; the original verified physical sheet geometry is unchanged."""
    if (not isinstance(stamp, str)
            or re.fullmatch(r"[0-9]{12}", stamp) is None):
        raise ValueError("RECEIVING_COMPOSED_DXF_TIMESTAMP_INVALID")
    try:
        parsed = datetime.strptime(stamp, "%Y%m%d%H%M")
    except ValueError as exc:
        raise ValueError("RECEIVING_COMPOSED_DXF_TIMESTAMP_INVALID") from exc
    if parsed.strftime("%Y%m%d%H%M") != stamp:
        raise ValueError("RECEIVING_COMPOSED_DXF_TIMESTAMP_INVALID")
    names = tuple(normalize_panel_name(name) for _si, _bi, name in cells)
    numbered = [re.fullmatch(r"[Pp]([0-9]+)", n) for n in names]
    if all(numbered):
        numbers = sorted(int(m.group(1)) for m in numbered)
        label = (f"p{numbers[0]}" if len(numbers) == 1
                 else f"p{numbers[0]}~p{numbers[-1]}")
    else:
        # Never invent a P-number for a renamed Bay.
        label = "_".join(n.casefold() for n in names)
    name = f"{stamp}{label}{Path(legacy_name).stem}.dxf"
    if len(name) > 240:
        raise ValueError("RECEIVING_COMPOSED_DXF_FILENAME_TOO_LONG")
    return name


def plan_receiving_grouped_dxf(layout, mode, *, file_stamp=None):
    """Immutable ordered (group filename, physical Bay cells) response.

    Cell: (zero-based Set, zero-based Bay, canonical operator panel name).
    P-number is never used as a substitute for the physical Bay position.
    """
    if mode not in RECEIVING_COMPOSED_DXF_MODES:
        raise ValueError("RECEIVING_COMPOSED_DXF_MODE_UNSUPPORTED")
    state = normalize_receiving_layout(layout)
    sets = tuple(state["sets"])
    all_cells = tuple(
        (si, bi, normalize_panel_name(bay["panel_name"]))
        for si, row in enumerate(sets)
        for bi, bay in enumerate(row["bays"])
    )
    if not all_cells:
        raise ValueError("RECEIVING_COMPOSED_DXF_NO_PHYSICAL_BAYS")
    if len({name.casefold() for _, _, name in all_cells}) != len(all_cells):
        raise ValueError("RECEIVING_COMPOSED_DXF_DUPLICATE_PANELS")
    if mode == "PER_SET":
        result = tuple(
            (f"第{si+1}套.dxf",
             tuple((si, bi, normalize_panel_name(bay["panel_name"]))
                   for bi, bay in enumerate(row["bays"])))
            for si, row in enumerate(sets)
        )
    elif mode == "ALL":
        result = (("全部.dxf", all_cells),)
    else:
        edge, middle = [], []
        for si, row in enumerate(sets):
            count = len(row["bays"])
            for bi, bay in enumerate(row["bays"]):
                cell = (si, bi, normalize_panel_name(bay["panel_name"]))
                if bi == 0 or bi == count-1:
                    edge.append(cell)  # one-Bay Set occurs exactly once
                else:
                    middle.append(cell)
        result = (("頭尾盤.dxf", tuple(edge)),)
        if middle:
            result += (("中間盤.dxf", tuple(middle)),)
    if file_stamp is not None:
        result = tuple(
            (_group_output_filename(name, cells, file_stamp), cells)
            for name, cells in result
        )
        if len({name.casefold() for name, _ in result}) != len(result):
            raise ValueError("RECEIVING_COMPOSED_DXF_FILENAME_COLLISION")
    return result


def commit_verified_receiving_groups(
    layout, mode, physical_rows, stage_dir, output_dir,
    *, pre_commit_guard, overwrite=False, box_body_owner_by_namespace=None,
    _verified_nfb_pair_parts_by_namespace=None,
):
    """Publish only complete *previously verified* per-Bay physical sheets.

    The caller has independently saved+reopened each supplied source flat,
    checked source CSV/ear/pad witnesses, and retained each original namespace.
    Compose into temporary group files, reopen every translated primitive,
    then commit the WHOLE set with rollback. Never publish the individual flats.
    """
    if not callable(pre_commit_guard):
        raise ValueError("RECEIVING_COMPOSED_DXF_PRECOMMIT_GUARD_REQUIRED")
    groups = plan_receiving_grouped_dxf(layout, mode, file_stamp=_taipei_output_stamp())
    source = normalize_receiving_layout(layout)
    by_namespace = {}
    seen = set()
    for namespace, physical_id, _filename, render in tuple(physical_rows):
        identity = (str(namespace), str(physical_id))
        if identity in seen:
            raise ValueError("RECEIVING_COMPOSED_DXF_DUPLICATE_PHYSICAL_OWNER")
        seen.add(identity)
        by_namespace.setdefault(str(namespace), []).append((str(physical_id), render))
    expected_namespaces = {
        receiving_instance_namespace(
            set_id=row["stable_id"], bay_id=bay["stable_id"],
        )
        for row in source["sets"] for bay in row["bays"]
    }
    if set(by_namespace) != expected_namespaces:
        raise ValueError("RECEIVING_COMPOSED_DXF_INCOMPLETE_BAY_SOURCE")
    # The grouped output has already flattened each BoxBody to certified
    # per-piece scenes. Carry ONLY the original Engine owner topology; do
    # not rebuild, substitute or trust a GUI-derived assembled flat.
    from collections.abc import Mapping
    if box_body_owner_by_namespace is not None and not isinstance(
        box_body_owner_by_namespace, Mapping,
    ):
        raise TypeError("RECEIVING_COMPOSED_DXF_BODY_OWNER_MAPPING_REQUIRED")
    owner_source = dict(box_body_owner_by_namespace or {})
    from collections.abc import Mapping
    if _verified_nfb_pair_parts_by_namespace is not None and not isinstance(
        _verified_nfb_pair_parts_by_namespace, Mapping
    ):
        raise TypeError("RECEIVING_COMPOSED_NFB_PROOF_MAPPING_REQUIRED")
    pair_source = dict(_verified_nfb_pair_parts_by_namespace or {})
    if set(pair_source) - expected_namespaces:
        raise ValueError("RECEIVING_COMPOSED_NFB_UNKNOWN_PHYSICAL_BAY")
    if set(owner_source) - expected_namespaces:
        raise ValueError("RECEIVING_COMPOSED_DXF_UNKNOWN_BODY_OWNER")
    from .composed_panel_dxf import save_composed_panel_dxf
    staged = {}
    stage = Path(stage_dir)
    for filename, cells in groups:
        panel_instances = []
        group_body_owners = {}
        group_nfb_parts = {}
        for si, bi, panel_name in cells:
            row = source["sets"][si]
            bay = row["bays"][bi]
            ns = receiving_instance_namespace(
                set_id=row["stable_id"], bay_id=bay["stable_id"],
            )
            records = by_namespace[ns]
            if ns in owner_source:
                group_body_owners[panel_name] = owner_source[ns]
            if ns in pair_source:
                group_nfb_parts[panel_name] = frozenset(pair_source[ns])
            panel_instances.append((panel_name, ResolvedManufacturingGeometry(
                parts=tuple(ResolvedManufacturingPart(key, render)
                            for key, render in records),
            )))
        # The Engine composer checks actual canonical scenes, independent
        # source-flat roundtrips and final combined DXF primitive exactness.
        # Preserve Set/Bay ordering even for P10 after a deleted P3.
        result = save_composed_panel_dxf(
            panel_instances, stage / filename, pre_commit_guard=pre_commit_guard,
            overwrite=False, preserve_input_order=True,
            box_body_owner_by_panel=group_body_owners,
            _verified_nfb_pair_parts=group_nfb_parts,
        )
        staged[filename] = Path(result.path)
    pre_commit_guard()  # Same immutable current-source witness before publish.
    return _atomic_commit_staged_dxfs(
        staged, Path(output_dir), overwrite=overwrite,
    )
