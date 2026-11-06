# -*- coding: utf-8 -*-
"""Engine-owned immutable physical assembly part projection identity.

GUI FinalScene request/render containers reuse this exact class and remain
strictly presentation-only. The manufacturing resolver never imports Phase6.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class AssemblyScenePart:
    part_key: str
    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    placement: str = "offset"
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
