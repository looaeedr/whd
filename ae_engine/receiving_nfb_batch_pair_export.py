# -*- coding: utf-8 -*-
"""#2517 public multi-Bay Receiving CSV NFB PART_ONLY manufacturing API.

Callers provide immutable, per-Bay canonical WHD ManufacturingResolveRequest
objects, never a caller-composed FinalScene or inferred NFB world X. The exact
existing single-Bay Engine API manufactures 2/3 genuine physical DXFs per
selected Bay. A single destination transaction exposes NONE unless every
Bay staged successfully, reopened every DXF, and the source still matches.
No full-cabinet/PAD/EAR or source-only CLI certification is granted.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from collections.abc import Sequence

from .manufacturing_contracts import (
    ManufacturingResolveRequest, thaw_manufacturing_value,
)
from .receiving_nfb_manufacturing_transport import (
    restore_receiving_nfb_dto_selectors,
)
from .receiving_nfb_committed_final_scene import _submitted_csv_holes
from .receiving_nfb_pair_export import (
    NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    export_current_csv_nfb_pair_from_request,
    _committed_csv_brand_source_hashes,
    _require_committed_csv_source_unchanged,
)
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, receiving_instance_namespace,
)


@dataclass(frozen=True)
class NfbCsvMultiBayPartOnlyDxf:
    """Actual Set/Bay receipt list; explicitly NOT full cabinet manufacture."""
    bays: tuple[tuple[str, str, NfbCsvPairedPartOnlyDxf | NfbCsvTwoTierPartOnlyDxf], ...]
    output_paths: tuple[str, ...]
    scope: str = "CSV_MULTIBAY_PART_ONLY_NOT_WHOLE_CABINET"


def export_receiving_committed_nfb_csv_bays(
    requests: Sequence[ManufacturingResolveRequest],
    *, output_directory: str | Path, pre_commit_guard=None,
) -> NfbCsvMultiBayPartOnlyDxf:
    """Atomically export N verified physical Receiving NFB door/base pairs.

    All Bay identities and current submitted CSV sources are preflighted
    before the first staged DXF. No separate GUI/CADSplit geometry pipeline:
    each immutable request enters the same canonical Engine resolver that
    powers a single Bay. Preserve source-CSV SHA across the ENTIRE batch,
    including after other Bays have been manufactured; verify external input
    bytes with an optional operator/caller pre_commit_guard.
    """
    if not isinstance(requests, (tuple, list)) or not requests:
        raise ValueError("CSV_MULTIBAY_MANUFACTURING_REQUESTS_REQUIRED")
    if pre_commit_guard is not None and not callable(pre_commit_guard):
        raise TypeError("CSV_MULTIBAY_SOURCE_GUARD_MUST_BE_CALLABLE")

    prepared = []
    used = set()
    for request in requests:
        if not isinstance(request, ManufacturingResolveRequest):
            raise TypeError("CSV_MULTIBAY_MANUFACTURING_REQUEST_REQUIRED")
        snapshot = restore_receiving_nfb_dto_selectors(
            thaw_manufacturing_value(request.input_snapshot)
        )
        current = _submitted_csv_holes(snapshot)
        if not current:
            raise ValueError("CSV_MULTIBAY_COMMITTED_SOURCE_REQUIRED")
        selected = snapshot.get("_receiving_runtime_selection")
        if not isinstance(selected, dict):
            raise ValueError("CSV_MULTIBAY_EXACT_SET_BAY_REQUIRED")
        set_id, bay_id = selected.get("set_id"), selected.get("bay_id")
        if not isinstance(set_id, str) or not set_id or not isinstance(bay_id, str) or not bay_id:
            raise ValueError("CSV_MULTIBAY_EXACT_SET_BAY_REQUIRED")
        namespace = receiving_instance_namespace(set_id=set_id, bay_id=bay_id)
        if namespace in used:
            raise ValueError("CSV_MULTIBAY_DUPLICATED_PHYSICAL_SET_BAY")
        used.add(namespace)
        prepared.append((
            request, set_id, bay_id,
            current[1], _committed_csv_brand_source_hashes(current[1]),
        ))

    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("CSV_MULTIBAY_OUTPUT_DIRECTORY_MISSING")
    if pre_commit_guard is not None:
        pre_commit_guard()

    with TemporaryDirectory(prefix=".whd-nfb-multibay-", dir=str(root)) as stage:
        stage_root = Path(stage)
        original = []
        staged = {}
        for request, set_id, bay_id, holes, initial_hashes in prepared:
            receipt = export_current_csv_nfb_pair_from_request(
                request, output_directory=stage_root,
            )
            if isinstance(receipt, NfbCsvPairedPartOnlyDxf):
                paths = (receipt.inner_door_path, receipt.base_plate_path)
            elif isinstance(receipt, NfbCsvTwoTierPartOnlyDxf):
                paths = (receipt.inner_door_path,) + receipt.base_plate_paths
            else:
                raise TypeError("CSV_MULTIBAY_ENGINE_PAIR_RECEIPT_INVALID")
            if (len(paths) not in (2, 3)
                    or len(set(paths)) != len(paths)
                    or any(not Path(path).is_file() for path in paths)):
                raise ValueError("CSV_MULTIBAY_STAGED_PARTS_INCOMPLETE")
            for path in paths:
                stem = Path(path).name
                if stem in staged:
                    raise ValueError("CSV_MULTIBAY_DUPLICATED_PHYSICAL_FILENAME")
                staged[stem] = Path(path)
            original.append((set_id, bay_id, receipt))
        if pre_commit_guard is not None:
            pre_commit_guard()
        for _request, _set_id, _bay_id, holes, initial_hashes in prepared:
            _require_committed_csv_source_unchanged(holes, initial_hashes)
        # This is the same rollback-capable physical DXF commit owner used
        # by the original single-Bay pair. One failure never publishes 1/16.
        saved = _atomic_commit_staged_dxfs(staged, root, overwrite=False)

    results = []
    ordered_paths = []
    for set_id, bay_id, receipt in original:
        if isinstance(receipt, NfbCsvPairedPartOnlyDxf):
            actual = replace(
                receipt,
                inner_door_path=saved[Path(receipt.inner_door_path).name],
                base_plate_path=saved[Path(receipt.base_plate_path).name],
            )
            paths = (actual.inner_door_path, actual.base_plate_path)
        else:
            actual = replace(
                receipt,
                inner_door_path=saved[Path(receipt.inner_door_path).name],
                base_plate_paths=tuple(saved[Path(p).name] for p in receipt.base_plate_paths),
            )
            paths = (actual.inner_door_path,) + actual.base_plate_paths
        ordered_paths.extend(paths)
        results.append((set_id, bay_id, actual))
    return NfbCsvMultiBayPartOnlyDxf(tuple(results), tuple(ordered_paths))
