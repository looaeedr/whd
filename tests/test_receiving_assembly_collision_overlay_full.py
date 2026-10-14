# -*- coding: utf-8 -*-
"""One real 3D render: all-parts collision switch must expose ignored frame/head crossings."""
from types import SimpleNamespace
from dataclasses import replace
from phase6_final_scene_contracts import AssemblyScenePart
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_contracts import AssemblySceneRenderData, FinalSceneViewRequest


def test_actual_receiving_scene_collision_toggle_exposes_all_frame_head_pairs():
    from tests.test_issue1050_receiving_mother_plate_marking import _snapshot,_full_receiving_geometry
    from phase6_manufacturing_geometry import _phase6_resolve_family_divider_reliefs
    s=_snapshot();g=_full_receiving_geometry(s)
    parts,diagnostics,_=_phase6_resolve_family_divider_reliefs(
        g.parts, finished_dimensions=(s["w"],s["h"],s["d"]),sheet_thickness=s["t"])
    assert all(not d.illegal_penetration for d in diagnostics)
    # GUI FinalScene adapter converts manufacturing FoldProfileSegments to
    # plain, numeric profile rows before invoking the renderer.
    def as_rows(values):
        return tuple(
            dict(row) if isinstance(row, dict)
            else {"len":float(row.length),
                  **({"angle":float(row.angle)} if row.angle is not None else {}),
                  **({"phase6_key":str(row.phase6_key)} if row.phase6_key else {})}
            for row in values
        )
    scene_parts = tuple(AssemblyScenePart(
        part_key=p.part_key,render_data=p.render_data,
        x_profile=as_rows(p.x_profile),y_profile=as_rows(p.y_profile),
        placement=p.placement,offset=p.offset,
    ) for p in parts)
    f=Figure(figsize=(6,5))
    ax=f.add_subplot(111,projection="3d");ax.set_axis_off()
    render=Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    request=FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(
            assembly_parts=scene_parts,show_interference=True,
            preserve_endcap_core_origin=True,
        ),
        part_key="assembly",x_profile=(),y_profile=(),
        finished_dimensions=(s["w"],s["h"],s["d"]),thickness=s["t"],
    )
    tris=render.render(request)
    audit=render.last_all_parts_collision_audit
    assert tris and audit is not None
    assert "head" in audit.visible_keys
    assert "inner_door:upper:left_frame" in audit.visible_keys
    assert "inner_door:upper:right_frame" in audit.visible_keys
    assert "box_body:left_side" in audit.visible_keys
    assert "box_body:right_side" in audit.visible_keys
    assert any({p.left,p.right}=={"head","box_body:left_side"} for p in audit.unresolved)
    assert any({p.left,p.right}=={"head","inner_door:upper:left_frame"} for p in audit.unresolved)
    assert audit.unresolved
    # Orange caution overlays must not masquerade as verified RED cutting
    # interference or be silently treated as an all-clear.
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    assert any(isinstance(c,Line3DCollection) for c in ax.collections)
    assert any(getattr(t,"get_text",lambda:"")().find("未證實合法")>=0
               for t in ax.texts)
