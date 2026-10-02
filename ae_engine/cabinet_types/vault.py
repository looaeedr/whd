# -*- coding: utf-8 -*-
"""Vault / 金庫型 cabinet-family registration."""
from .registry import CabinetTypeRegistration

REGISTRATION = CabinetTypeRegistration(
    canonical_name="金庫型",
    aliases=("VAULT",),
    module_name=__name__,
    implemented=True,
)
