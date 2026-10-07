from __future__ import annotations

import inspect

from ae_engine import certified_relief_registry
from ae_engine import certified_relief_models
from ae_engine import certified_relief_corner_policy


def test_issue1351_models_are_reexported_from_registry():
    assert certified_relief_registry.CertifiedReliefRule is certified_relief_models.CertifiedReliefRule
    assert certified_relief_registry.CertifiedReliefResult is certified_relief_models.CertifiedReliefResult
    assert certified_relief_registry.CertifiedReliefStatus is certified_relief_models.CertifiedReliefStatus


def test_issue1351_corner_policy_owner_is_extracted_one_way():
    assert certified_relief_registry.lookup_certified_corner_state is certified_relief_corner_policy.lookup_certified_corner_state
    assert certified_relief_registry.certified_corner_policy_for_part is certified_relief_corner_policy.certified_corner_policy_for_part
    facade = inspect.getsource(certified_relief_registry)
    assert len(facade.splitlines()) < 1350
    for owner in (inspect.getsource(certified_relief_models), inspect.getsource(certified_relief_corner_policy)):
        assert "from .certified_relief_registry import" not in owner
        assert "import ae_engine.certified_relief_registry" not in owner
