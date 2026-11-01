"""#2517: seven-stage USER_ADDED manufacturing pipeline is owned by Engine."""
import inspect
from dataclasses import dataclass
from types import SimpleNamespace

import ae_engine.explicit_joint_pipeline as engine
from ae_engine import manufacturing_api as api
import phase6_explicit_joint_pipeline as historic
from phase6_manufacturing_geometry import _phase6_resolve_explicit_joint_reliefs


@dataclass(frozen=True)
class Part:
    part_key: str
    render_data: object
    x_profile: tuple = ()
    y_profile: tuple = ()
    placement: str = "top"
    offset: tuple = (0, 0, 0)


def test_public_engine_solver_preserves_empty_explicit_joint_transaction():
    parts = (Part("box_body", SimpleNamespace(material=None)),)
    result = api.resolve_manufacturing_explicit_joint_reliefs(
        parts, (), finished_dimensions=(100, 120, 80), sheet_thickness=2,
        committed_state={"schema_version": 1, "items": {}},
    )
    assert result == (parts, (), {"schema_version": 1, "items": {}})
    assert engine.resolve_explicit_joint_reliefs is historic.resolve_explicit_joint_reliefs


def test_engine_no_reverse_dependency_and_phase6_is_only_adapter():
    source = inspect.getsource(engine)
    assert "from phase6_" not in source
    assert "from fold_designer_bridge" not in source
    assert "from phase6_final_scene_view" not in source
    assert "AssemblyScenePart(" not in source
    assert "replace(base, render_data=temp_render)" in source
    shim = inspect.getsource(historic)
    assert "def resolve_explicit_joint_reliefs" not in shim
    assert "from ae_engine.manufacturing_api import" in shim
    facade = inspect.getsource(_phase6_resolve_explicit_joint_reliefs)
    assert "manufacturing_api.resolve_manufacturing_explicit_joint_reliefs(" in facade
    assert "ExplicitJointPipelineOps(" not in facade


def test_engine_public_exports_real_stage_owner_without_gui_signature():
    assert api.resolve_manufacturing_explicit_joint_reliefs is engine.resolve_manufacturing_explicit_joint_reliefs
    assert tuple(engine.EXPLICIT_JOINT_PIPELINE_STAGES) == (
        "normalize_candidate_inventory", "decide_owner_registry",
        "query_world_geometry", "solve_explicit_joint_candidate",
        "apply_resolved_cut", "assemble_diagnostics_evidence",
        "assemble_mutation_result",
    )
