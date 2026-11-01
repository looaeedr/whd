"""#2692 canonical Receiving Set/Bay manufacturing DXF grouping.

Physical first/last Bay is determined from each Set's topology, never HEAD or
TAIL *sheet* roles. The existing current-Bay source and EAR/PAD/NFB gates must
have verified EVERY staged physical sheet before this module runs.
"""
from __future__ import annotations

from pathlib import Path

from .contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, receiving_instance_namespace,
)
from .panel_naming import normalize_panel_name
from .receiving_layout import normalize_receiving_layout


RECEIVING_COMPOSED_DXF_MODES = frozenset({"PER_SET", "ALL", "END_VS_MIDDLE"})


def plan_receiving_grouped_dxf(layout, mode):
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
    return result


def commit_verified_receiving_groups(
    layout, mode, physical_rows, stage_dir, output_dir,
    *, pre_commit_guard, overwrite=False,
):
    """Publish only complete *previously verified* per-Bay physical sheets.

    The caller has independently saved+reopened each supplied source flat,
    checked source CSV/ear/pad witnesses, and retained each original namespace.
    Compose into temporary group files, reopen every translated primitive,
    then commit the WHOLE set with rollback. Never publish the individual flats.
    """
    if not callable(pre_commit_guard):
        raise ValueError("RECEIVING_COMPOSED_DXF_PRECOMMIT_GUARD_REQUIRED")
    groups = plan_receiving_grouped_dxf(layout, mode)
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
    from .composed_panel_dxf import save_composed_panel_dxf
    staged = {}
    stage = Path(stage_dir)
    for filename, cells in groups:
        panel_instances = []
        for si, bi, panel_name in cells:
            row = source["sets"][si]
            bay = row["bays"][bi]
            ns = receiving_instance_namespace(
                set_id=row["stable_id"], bay_id=bay["stable_id"],
            )
            records = by_namespace[ns]
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
        )
        staged[filename] = Path(result.path)
    pre_commit_guard()  # Same immutable current-source witness before publish.
    return _atomic_commit_staged_dxfs(
        staged, Path(output_dir), overwrite=overwrite,
    )
