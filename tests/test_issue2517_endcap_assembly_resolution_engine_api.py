"""#2517: public Engine owns physical EndCap relief solve and diagnostics."""
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    manufacturing_api, solve_endcap_assembly_relief,
    endcap_relief_solution_diagnostic,
)
from ae_engine import assembly_collision
import phase6_manufacturing_service as service


def test_public_solver_uses_real_part_inputs_without_gui_geometry(monkeypatch):
    witness = object()
    recorded = []
    def fake_solver(**kwargs):
        recorded.append(kwargs)
        return witness
    monkeypatch.setattr(assembly_collision, "solve_world_backprojected_endcap_relief", fake_solver)
    body = SimpleNamespace(render_data=object(), x_profile=({"len": 12},))
    head = SimpleNamespace(part_key="head", render_data=object(), x_profile=({"len": 20},), y_profile=({"len": 30},), placement="top")
    dims, graph = (100., 80., 40.), object()
    assert manufacturing_api.solve_endcap_assembly_relief is solve_endcap_assembly_relief
    assert solve_endcap_assembly_relief(
        body, head, finished_dimensions=dims, sheet_thickness=2., clearance=0.5,
        assembly_intent="INSERT", assembly_graph=graph, cabinet_family="金庫型",
        allow_3d_fallback=False,
    ) is witness
    assert recorded == [{
        "box_body_render_data": body.render_data,
        "endcap_render_data": head.render_data,
        "box_body_x_profile": body.x_profile,
        "endcap_x_profile": head.x_profile,
        "endcap_y_profile": head.y_profile,
        "finished_dimensions": dims,
        "endcap_placement": "top",
        "sheet_thickness": 2., "clearance": 0.5,
        "assembly_intent": "INSERT", "assembly_graph": graph,
        "endcap_part": "head", "cabinet_family": "金庫型",
        "allow_3d_fallback": False, "assembly_joint": None,
    }]


@pytest.mark.parametrize("solution,expected", [
    (SimpleNamespace(verified=True), None),
    (SimpleNamespace(verified=False, rule_id="cert-1", trust_level="CERTIFIED"), "已認證公式與立體影子驗證衝突；正式結果仍採已認證公式"),
    (SimpleNamespace(verified=False, rule_id="cert-2", trust_level="ENGINE_CONFLICT"), "已認證公式與立體影子驗證衝突；正式結果仍採已認證公式"),
    (SimpleNamespace(verified=False, rule_id=None, trust_level="UNKNOWN", shadow_validation={"reason": "physical penetration"}), "physical penetration"),
    (SimpleNamespace(verified=False, rule_id=None, trust_level="UNVERIFIED"), "3D 回折驗證仍有材料穿透"),
])
def test_diagnostic_matches_existing_endcap_truth_table(solution, expected):
    assert manufacturing_api.endcap_relief_solution_diagnostic is endcap_relief_solution_diagnostic
    assert endcap_relief_solution_diagnostic(solution) == expected


def test_phase6_calls_public_engine_boundary_without_trust_or_shadow_policy():
    source = inspect.getsource(service.resolve)
    assert "solve_endcap_assembly_relief(" in source
    assert "endcap_relief_solution_diagnostic(" in source
    assert "solve_world_backprojected_endcap_relief" not in source
    endcap_block = source.split("for key in required:", 1)[1].split(
        "atomic_committable =", 1
    )[0]
    assert "shadow_validation" not in endcap_block
    assert "已認證公式與立體影子驗證衝突" not in source
    assert "_phase6_solution_is_committable(" not in source


def test_solver_errors_propagate_without_gui_fallback(monkeypatch):
    def fail(**kwargs):
        raise ValueError("canonical solver unavailable")
    monkeypatch.setattr(assembly_collision, "solve_world_backprojected_endcap_relief", fail)
    body = SimpleNamespace(render_data=object(), x_profile=())
    tail = SimpleNamespace(part_key="tail", render_data=object(), x_profile=(), y_profile=(), placement="bottom")
    with pytest.raises(ValueError, match="canonical solver unavailable"):
        solve_endcap_assembly_relief(
            body, tail, finished_dimensions=(1, 2, 3), sheet_thickness=2.,
            clearance=0., assembly_intent="OVERLAY", assembly_graph=None,
            cabinet_family="受電箱", allow_3d_fallback=True,
        )
