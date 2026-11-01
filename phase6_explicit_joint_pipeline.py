# -*- coding: utf-8 -*-
"""Historic Phase6 import compatibility only; Engine owns all Joint relief stages.

No manufacturing/collision implementation is permitted in this module.
"""
from ae_engine.manufacturing_api import (
    EXPLICIT_JOINT_PIPELINE_STAGES,
    ExplicitJointPipelineOps,
    ExplicitJointPipelineRequest,
    ExplicitJointCandidateInventory,
    ExplicitJointOwnerDecision,
    normalize_candidate_inventory,
    decide_owner_registry,
    query_world_geometry,
    solve_explicit_joint_candidate,
    apply_resolved_cut,
    assemble_diagnostics_evidence,
    assemble_mutation_result,
    resolve_explicit_joint_reliefs,
)
