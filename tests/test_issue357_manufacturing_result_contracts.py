from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest


class OpaqueDomainObject:
    def __init__(self, name):
        self.name = name


def _result_fixture():
    from phase6_manufacturing_contracts import (
        ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,
        ManufacturingEffects,
        ManufacturingMutationResult,
        ManufacturingResolveResult,
    )

    solution = OpaqueDomainObject("head-solution")
    geometry = OpaqueDomainObject("resolved-geometry")
    diagnostics = ManufacturingDiagnosticsResult(
        relief_errors={"tail": "shadow mismatch"},
        relief_solutions={"head": solution},
        joint_diagnostics=[OpaqueDomainObject("J1")],
        rule_traces=[OpaqueDomainObject("R1")],
        interference_probe_parts=["head", "tail"],
        warnings=["certified formula retained"],
    )
    mutations = ManufacturingMutationResult(
        snapshot_patch={
            "assembly_relief": {
                "head": {"verified": True},
            }
        },
    )
    effects = ManufacturingEffects(
        publish_live_state=True,
        force_live_publish=True,
        reason="atomic relief commit",
    )
    cache = ManufacturingCacheReceipt(
        signature="sig-123",
        hit=False,
        stored=True,
    )
    result = ManufacturingResolveResult(
        geometry=geometry,
        diagnostics=diagnostics,
        mutations=mutations,
        effects=effects,
        cache=cache,
    )
    return result, solution, geometry


def test_issue357_explicit_result_envelope_is_immutable_and_defensive():
    from phase6_manufacturing_contracts import ManufacturingResolveResult

    result, solution, geometry = _result_fixture()

    assert isinstance(result, ManufacturingResolveResult)
    assert result.geometry is geometry
    assert result.diagnostics.relief_solutions["head"] is solution
    assert result.diagnostics.relief_errors["tail"] == "shadow mismatch"
    assert result.diagnostics.interference_probe_parts == ("head", "tail")
    assert result.effects.publish_live_state is True
    assert result.effects.force_live_publish is True
    assert result.cache.signature == "sig-123"

    with pytest.raises(FrozenInstanceError):
        result.geometry = object()


def test_issue357_source_container_mutation_does_not_mutate_result_metadata():
    from phase6_manufacturing_contracts import ManufacturingDiagnosticsResult

    errors = {"head": "x"}
    probes = ["head"]
    warnings = ["w1"]
    diagnostics = ManufacturingDiagnosticsResult(
        relief_errors=errors,
        interference_probe_parts=probes,
        warnings=warnings,
    )

    errors["head"] = "changed"
    probes.append("tail")
    warnings.append("w2")

    assert diagnostics.relief_errors["head"] == "x"
    assert diagnostics.interference_probe_parts == ("head",)
    assert diagnostics.warnings == ("w1",)


def test_issue357_adapter_apply_reproduces_phase1_legacy_state_without_executing_effect():
    from phase6_manufacturing_adapter import apply_manufacturing_result

    result, solution, geometry = _result_fixture()
    calls = []
    app = SimpleNamespace(
        _phase6_input_snapshot={"keep": 1},
        _live_sync_callback=lambda payload: calls.append(payload),
    )

    returned = apply_manufacturing_result(app, result)

    assert returned is geometry
    assert app._phase6_last_interference_probe_parts == ("head", "tail")
    assert app._phase6_last_relief_errors == {"tail": "shadow mismatch"}
    assert app._phase6_last_relief_solutions == {"head": solution}
    assert app._phase6_last_resolved_manufacturing_geometry is geometry
    assert app._phase6_last_resolved_manufacturing_signature == "sig-123"
    assert app._phase6_input_snapshot["keep"] == 1
    assert app._phase6_input_snapshot["assembly_relief"]["head"]["verified"] is True

    # Effects are explicit intent only in T3.  Applying legacy state must not
    # secretly publish or pump application side effects.
    assert calls == []


def test_issue357_result_contract_carries_all_observable_output_categories():
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult,
    )

    names = set(ManufacturingResolveResult.__dataclass_fields__)
    assert names == {"geometry", "diagnostics", "mutations", "effects", "cache"}


def test_issue357_result_contract_survives_later_phase2_resolver_cutover():
    import ast
    from pathlib import Path

    path = Path("phase6_manufacturing_service.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    segment = ast.get_source_segment(source, resolver) or ""
    assert "ManufacturingResolveResult" in segment

