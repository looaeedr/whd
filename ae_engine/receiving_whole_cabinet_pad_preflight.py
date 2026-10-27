# -*- coding: utf-8 -*-
"""#1490: whole-cabinet PAD source inventory check, never a manufacturing grant.

The original selected-sheet DXF writer can independently prove current CSV
NFB door/base and formed EAR/SIDE, but a shallow NFB can require an additional
installed PAD.  A successful subset of sheet files is not proof that all
physical members of the box have been exported.

This module asks the CURRENT committed FinalScene PAD resolver for its exact
physical owners.  It cannot issue fabrication permission or bypass any
existing source, collision, world-Z or generic DXF guards.
"""
from __future__ import annotations

from collections.abc import Iterable


def missing_required_pad_sheets(
    snapshot, actual_assembly_parts, selected_export_part_ids: Iterable[str],
) -> tuple[str, ...]:
    """Return source-required PAD owners omitted from a proposed full inventory.

    The source resolver independently validates submitted CSV identity, Base
    source, folded-skin mating and the actual square cutouts.  If those facts
    cannot be derived, its failure is intentionally propagated (fail closed).
    """
    from .receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )

    rows = resolve_committed_pad_physical_delivery(
        snapshot, tuple(actual_assembly_parts), piece_count=1,
    )
    owners = tuple(row.physical_id for row in rows)
    if len(owners) != len(set(owners)):
        raise ValueError("RECEIVING_FULL_NFB_DUPLICATE_PAD_PHYSICAL_OWNER")
    exported = set(selected_export_part_ids)
    return tuple(sorted(set(owners) - exported))
