import importlib
import inspect
from pathlib import Path


STAGES = (
    "normalize_candidate_inventory",
    "decide_owner_registry",
    "query_world_geometry",
    "solve_explicit_joint_candidate",
    "apply_resolved_cut",
    "assemble_diagnostics_evidence",
    "assemble_mutation_result",
)


def test_p7_r_f_explicit_joint_resolver_is_a_bounded_pipeline_facade():
    import phase6_manufacturing_geometry as facade

    owner = importlib.import_module("phase6_explicit_joint_pipeline")
    facade_source = inspect.getsource(facade._phase6_resolve_explicit_joint_reliefs)

    assert "phase6_explicit_joint_pipeline" in Path(
        facade.__file__
    ).read_text(encoding="utf-8")
    assert "resolve_explicit_joint_reliefs" in facade_source
    assert len(facade_source.splitlines()) <= 60

    for forbidden in (
        "discover_joint_relief_candidate",
        "verify_joint_candidate_replay",
        "project_joint_interference_to_relief_owner",
        "ResolvedJointDiagnostic",
        "unary_union",
        "while solver_iterations",
    ):
        assert forbidden not in facade_source

    for name in STAGES:
        stage = getattr(owner, name)
        signature = inspect.signature(stage)
        assert "self" not in signature.parameters
        assert "app" not in signature.parameters
        assert all(
            parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for parameter in signature.parameters.values()
        )


def test_p7_r_f_stage_owner_has_no_reverse_or_duplicate_manufacturing_path():
    owner = importlib.import_module("phase6_explicit_joint_pipeline")
    source = inspect.getsource(owner)

    assert "phase6_manufacturing_geometry" not in source
    assert "fold_designer_bridge" not in source
    assert "def resolve_explicit_joint_reliefs" in source

    # The pipeline may orchestrate the canonical collision APIs, but it must not
    # grow a second raw backprojection/registry implementation.
    for forbidden in (
        "def detect_planar_collision",
        "def project_collision_to_endcap_relief",
        "def lookup_certified_endcap_relief",
        "def folded_mesh_with_flat_uv_from_polygon",
    ):
        assert forbidden not in source


def test_p7_r_f_stage_order_matches_approved_pipeline_contract():
    owner = importlib.import_module("phase6_explicit_joint_pipeline")
    assert tuple(owner.EXPLICIT_JOINT_PIPELINE_STAGES) == STAGES
