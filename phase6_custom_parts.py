# -*- coding: utf-8 -*-
"""Compatibility-only GUI storage imports; physical custom ID policy is Engine-owned."""
from ae_engine.manufacturing_api import (
    CustomPartCatalog, is_custom_part, custom_part_only_change,
    CUSTOM_PART_PREFIX as PREFIX, CUSTOM_PART_PRESET as PRESET,
)
