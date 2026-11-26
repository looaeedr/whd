# -*- coding: utf-8 -*-
"""#3501 first-type wire-pull enclosure topology; geometry candidate only."""
from __future__ import annotations

from .registry import CabinetTypeRegistration

# P1 does not grant general Family manufacturing or GUI admission.
REGISTRATION = CabinetTypeRegistration(
    canonical_name="拉線箱", aliases=("WIRE_PULL",), module_name=__name__, implemented=False,
)


LEGACY_PART_SPEC_ALLOWED = False


def resolve_standard_topology(spec):
    # Avoid a package-init dependency on manufacturing_api.
    from .wire_pull_topology import resolve
    return resolve(spec)
