# -*- coding: utf-8 -*-
"""Engine-owned EndCap relief solution production-commit policy.

Keep certified formula authority distinct from 3D shadow verification:
a certified rule with ENGINE_CONFLICT may be committable while the UI still
reports the shadow diagnostic. Never grant uncertified fallback a commit.
"""
from __future__ import annotations


def endcap_relief_solution_committable(solution):
    if bool(getattr(solution, "verified", False)):
        return True
    trust = str(getattr(solution, "trust_level", "") or "")
    return bool(getattr(solution, "rule_id", None)) and trust in {
        "CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"
    }


def endcap_relief_transaction_committable(required_parts, solutions):
    """Fail closed unless all required physical EndCaps can commit together.

    Individual certification/verified status remains owned by the existing
    endcap_relief_solution_committable policy; no preview geometry is promoted.
    Empty selection has nothing to commit, so cannot authorize publication.
    """
    required = tuple(required_parts or ())
    if not required:
        return False
    return all(
        key in solutions and endcap_relief_solution_committable(solutions[key])
        for key in required
    )
