# -*- coding: utf-8 -*-
"""#1502: independent CSV bottom-plate CHECK Q DXF reopen preflight.

All geometry originates in the existing physical NFB CSV FinalScene. The
canonical manufacturing export gate must NOT be opened by this preflight.
A temporary DXF exists only inside this function and is always discarded;
there is no caller-selected output path or manufacturing release status.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from .drawing_annotation_layout import annotate_quantity_render_data
from .dxf_acceptance import verify_saved_part_render_data_dxf
from .dxf_serialization import save_scene_dxf, verify_quantity_check_dxf
from .receiving_nfb_v5_check_q_preview import (
    CsvV5BaseCheckDemand,
    check_csv_v5_base_part_only_groups,
)


@dataclass(frozen=True)
class CsvV5CheckQDxfPreflight:
    """Non-release evidence of exact temporary DXF round trips."""
    group_keys: tuple[str, ...]
    quantities: tuple[int, ...]
    dxf_sha256: tuple[str, ...]
    status: str = "NFB_V5_CSV_CHECK_Q_DXF_PREFLIGHT_ONLY"
    manufacturing_ready: bool = False


def preflight_csv_v5_base_check_q_dxf(
    demands: Sequence[CsvV5BaseCheckDemand],
) -> CsvV5CheckQDxfPreflight:
    """Reopen each temporary CHECK-Q sheet and compare actual CUTTING/BEND.

    Stage 1 verifies source CSV SHA, physical tier identities, screw owners,
    untouched ear fixing holes, material and exact canonical CHECK grouping.
    Stage 2 serializes its already-resolved DrawingScene to *temporary* DXF,
    then independently reopens it with the existing acceptance engine and
    checks the actual Q label/layer/placement.

    This function cannot write to a production destination and never modifies
    trial metadata to indicate MFG-2 authorization.
    """
    preview = check_csv_v5_base_part_only_groups(demands)
    if preview.manufacturing_ready is not False or not preview.groups:
        raise ValueError("CSV CHECK Q 必須保持未核准製造的試算狀態")
    group_keys = []
    quantities = []
    checksums = []
    with TemporaryDirectory(prefix="whd-csv-nfb-dxf-preflight-") as directory:
        for group in preview.groups:
            annotated = annotate_quantity_render_data(
                group.render_data, group.quantity,
            )
            path = Path(directory) / group.filename
            # Do NOT call or weaken the manufacturing DXF export gate. This
            # low-level serializer is scoped to a private disposable preflight.
            save_scene_dxf(path, annotated.scene)
            accepted = verify_saved_part_render_data_dxf(annotated, path)
            if not accepted.ok:
                reasons = ", ".join(issue.category for issue in accepted.issues)
                raise ValueError("CSV NFB DXF 重開幾何不一致：" + reasons)
            verify_quantity_check_dxf(annotated.scene, path)
            group_keys.append(group.key)
            quantities.append(group.quantity)
            checksums.append(sha256(path.read_bytes()).hexdigest())
    return CsvV5CheckQDxfPreflight(
        group_keys=tuple(group_keys),
        quantities=tuple(quantities),
        dxf_sha256=tuple(checksums),
    )
