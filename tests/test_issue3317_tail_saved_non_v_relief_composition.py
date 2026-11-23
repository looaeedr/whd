# -*- coding: utf-8 -*-
"""#3317: a resolved non-V USER_ADDED/EndCap cut must survive V GUI preview."""
from shapely.geometry import Point, Polygon, box
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_collision import apply_verified_joint_cut_to_part
from ae_engine.assembly_scene_part import AssemblyScenePart
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
from ae_engine.sheetmetal_geometry_core import GeometryError
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project
from tests.test_issue3317_tail_gui_lower_v import _real_source

# A genuine side-wall notch unrelated to the two bottom V wedge cutouts.
NON_V_CUT = box(-1., 110., 6., 122.)
V_CONFLICT_CUT = box(-1., 54., 6., 60.)


def _solved_via_existing_relief_engine(raw, cut):
    part = AssemblyScenePart(
        part_key="tail", render_data=raw,
        x_profile=(), y_profile=(), placement="tail",
        offset=(0., 0., 0.),
    )
    solved = apply_verified_joint_cut_to_part(part, cut).render_data
    assert solved.material.symmetric_difference(
        material_polygon_from_final_scene(solved.scene)
    ).area < 1e-6
    return solved


def _has_inside_skin_at(triangles, *, yz=(116., 12.)):
    # Original side flange UV=(3,116) -> actual sharp world (15,116,12).
    for tri in triangles:
        if all(abs(p[0] - 15.) < 1e-6 for p in tri):
            yz_face = Polygon([(v[1], v[2]) for v in tri])
            if yz_face.area > 1e-9 and yz_face.buffer(1e-6).covers(Point(*yz)):
                return True
    return False


def test_non_sample_existing_cut_survives_original_v_save_reload_original(tmp_path):
    spec, raw = _real_source(w=620., d=185., t=2.)
    solved = _solved_via_existing_relief_engine(raw, NON_V_CUT)
    assert raw.material.difference(solved.material).area == pytest.approx(72.)
    assert solved.material.intersection(NON_V_CUT).area == pytest.approx(0.)
    values = {
        "model": "金庫型", "w": 620., "h": 600., "d": 185.,
        "t": 2., "fw": 25., "yl1": 15., "yr1": 15.,
        "ytop1": 16., "ybottom1": 48.,
    }
    original = api.commit_operator_tail_lower_v_choice(
        values, "original", tail_scene_values=values,
    )
    assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in original
    clean_v = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice="v90",
    )
    assert _has_inside_skin_at(api.tail_lower_v_preview_mesh(clean_v))
    selected = api.commit_operator_tail_lower_v_choice(
        original, "v90", tail_scene_values=values,
    )
    filename = write_project(tmp_path / "tail_620x185_with_relief.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": selected,
    })
    restored_snapshot = read_project(filename)["snapshot"]
    preview = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice=restored_snapshot[api.TAIL_LOWER_V_SNAPSHOT_KEY],
        resolved_render_data=solved,
    )
    assert preview.metadata["tail_lower_v_preview_only"] is True
    assert preview.metadata["tail_lower_v_independent_relief_replayed"] is True
    assert preview.material.intersection(NON_V_CUT).area == pytest.approx(0.)
    assert preview.material.symmetric_difference(
        material_polygon_from_final_scene(preview.scene)
    ).area < 1e-6
    physical = api.project_independent_part_view_mesh(
        "tail", preview, x_profile=(), y_profile=(), thickness=2.,
    )
    assert tuple(physical.triangles) == api.tail_lower_v_preview_mesh(preview)
    assert not _has_inside_skin_at(physical.triangles)
    assert preview.material.bounds == clean_v.material.bounds
    with pytest.raises(ValueError, match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(preview)
    original_again = api.commit_operator_tail_lower_v_choice(
        restored_snapshot, "original", tail_scene_values=values,
    )
    assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in original_again
    # Normal mode keeps the original already-resolved sheet, not raw Factory.
    assert solved.material.intersection(NON_V_CUT).area == pytest.approx(0.)


def test_conflicting_existing_relief_is_rejected_not_discarded():
    spec, raw = _real_source(w=620., d=185., t=2.)
    solved = _solved_via_existing_relief_engine(raw, V_CONFLICT_CUT)
    with pytest.raises(GeometryError, match="V_MITER_REPLAY_CONFLICTS_WITH_LOWER_V_CUTTING"):
        api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90", resolved_render_data=solved,
        )
