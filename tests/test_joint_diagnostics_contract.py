# -*- coding: utf-8 -*-
from types import SimpleNamespace

from ae_engine.contracts import ResolvedJointDiagnostic, ResolvedManufacturingGeometry


def test_resolved_joint_diagnostic_is_queryable_by_joint_id():
    diag = ResolvedJointDiagnostic(
        joint_id="head-wrap-body", subject_part="head", target_part="box_body",
        relation="WRAP", source="USER_ADDED", registry_status="MISS",
        preserve_part="head", relief_part="box_body", illegal_penetration=True,
        pre_pair_count=4, post_pair_count=1,
        penetration_segments=(((0,0,0),(1,0,0)),),
    )
    resolved = ResolvedManufacturingGeometry(parts=(), diagnostics=(diag,))
    assert resolved.joint_diagnostic("head-wrap-body") is diag
    assert resolved.joint_diagnostics_for("head") == (diag,)
    assert diag.relation == "WRAP"
    assert diag.preserve_part == "head"
    assert diag.relief_part == "box_body"


def test_assembly_scene_bundle_carries_joint_diagnostics_and_selection():
    import fold_designer_bridge as bridge
    diag = ResolvedJointDiagnostic(
        joint_id="j", subject_part="head", target_part="box_body", relation="WRAP"
    )
    bundle = bridge._phase6_make_assembly_scene_render_data(
        assembly_parts=(), joint_diagnostics=(diag,), selected_joint_id="j"
    )
    assert bundle.joint_diagnostics == (diag,)
    assert bundle.selected_joint_id == "j"


def test_public_assembly_adapter_keeps_joint_diagnostics_out_of_operator_scene(monkeypatch):
    """Joint solver diagnostics are data/debug state, not operator assembly drawing layers."""
    import fold_designer_bridge as bridge

    diag = ResolvedJointDiagnostic(
        joint_id="head:box_body:left:INSERT_OVERLAY:legacy",
        subject_part="head",
        target_part="box_body",
        relation="INSERT_OVERLAY",
        penetration_segments=(((0, 0, 0), (1, 0, 0)),),
        direction_segment=((0, 0, 0), (0, 0, 1)),
    )
    resolved = ResolvedManufacturingGeometry(parts=(), diagnostics=(diag,))
    monkeypatch.setattr(bridge, "_phase6_resolve_manufacturing_geometry", lambda _self: resolved)

    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    app = SimpleNamespace(
        assembly_part_visible_vars={},
        assembly_part_corner_vars={},
        _phase6_last_interference_probe_parts=(),
        assembly_show_interference_var=Var(True),
        assembly_joint_diag_var=Var(diag.joint_id),
    )

    bundle = bridge._phase6_query_assembly_render_data(app)

    assert bundle.joint_diagnostics == ()
    assert bundle.selected_joint_id is None
