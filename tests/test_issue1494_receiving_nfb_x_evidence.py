"""#1494: real blank geometry and source counterexamples do not grant X approval."""
from pathlib import Path
import json
import math
import pytest

ROOT = Path(__file__).resolve().parents[1]

def evidence():
    return json.loads((ROOT / 'docs/receiving-nfb-x-evidence.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('width,count,distances', [
    (600, 2, [180.0]), (750, 2, [310.0]),
    (800, 2, [325.0]), (800, 3, [180.0, 180.0]),
])
def test_approved_relative_table_does_not_become_absolute_x(width, count, distances):
    item = next(r for r in evidence()['records']
                if (r['box_outer_width_mm'], r['nfb_count']) == (width, count))
    assert item['nominal_adjacent_center_distances_mm'] == distances
    assert item['gate'] == 'OPEN-X-ROW'
    assert item['x_status'] == 'PREVIEW_ONLY'
    for field in ('certified_x_revision', 'blank_x_origin', 'finished_face_x_origin',
                  'box_world_x_origin', 'blank_to_finished_face_x',
                  'finished_face_to_box_world_x', 'source_dxf_sha256'):
        assert item[field] is None, f'{field} needs owner-approved source proof'
    assert item['missing_evidence']

@pytest.mark.parametrize('width', [600, 750, 800])
def test_one_hole_has_no_w_over_two_default(width):
    item = next(r for r in evidence()['records']
                if (r['box_outer_width_mm'], r['nfb_count']) == (width, 1))
    assert item['gate'] == 'OPEN-X-ONE'
    assert item['nominal_adjacent_center_distances_mm'] is None
    assert item['blank_x_origin'] is None
    assert item['box_world_x_origin'] is None
    assert item['x_status'] == 'PREVIEW_ONLY'


def test_w800_known_numbers_measure_real_cutting_without_certifying_dxf_origin():
    from ae_engine.cabinet_types.receiving import apply_family_defaults
    from ae_engine.cabinet_types import policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    snapshot = apply_family_defaults({'model': '金庫型', 'w': 400.0, 'h': 600.0,
                                     'd': 250.0, 't': 2.0, 'fw': 25.0})
    panel = policy.derive_inner_door_panels(snapshot)[0]
    assert panel.width == pytest.approx(689.0)
    assert panel.thickness == pytest.approx(2.0)
    render = build_inner_door_panel_render_data(panel)
    outlines = [p for p in render.scene.primitives
                if isinstance(p, PolylinePrimitive) and p.layer.upper() == 'CUTTING']
    assert len(outlines) == 1
    xs = [p.x for p in outlines[0].points]
    assert max(xs) - min(xs) == pytest.approx(723.0)
    observation = evidence()['w800_t2_three_hole_observation']
    centers = observation['reported_centers_from_drawing_left_mm']
    assert [b - a for a, b in zip(centers, centers[1:])] == [180.0, 180.0]
    assert sum(centers) / 3 == 723.0 / 2 == 361.5
    # The physical blank and mathematical symmetry prove neither source
    # boundary identity nor a translation to box world X.
    assert observation['source_outline_is_723_cutting_left_verified'] is False
    assert observation['box_world_centers_mm'] is None
    assert observation['certified_x_revision'] is None


def test_real_361_point_5_dxf_dimensions_are_vertical_counterexamples():
    fixture = json.loads((ROOT / 'tests/fixtures/receiving_nfb_x_negative_source.json')
                         .read_text(encoding='utf-8'))
    assert len(fixture['dimensions']) == 2
    for dim in fixture['dimensions']:
        start, end = dim['extension_start'], dim['extension_end']
        angle = math.radians(dim['rotation_degrees'])
        measured = abs((end[0] - start[0]) * math.cos(angle)
                       + (end[1] - start[1]) * math.sin(angle))
        assert measured == pytest.approx(dim['measured_distance_mm'], abs=1e-7)
        assert measured == pytest.approx(361.5, abs=0.01)
        assert abs(end[0] - start[0]) < 0.1
        assert abs(end[1] - start[1]) > 361.0
    assert fixture['neighbor_outline']['width_mm'] == 650.0
    assert fixture['neighbor_outline']['width_mm'] != 723.0


def test_evidence_ids_are_distinct_and_cannot_act_as_certified_revisions():
    data = evidence()
    records = data['records']
    assert len({r['rule_id'] for r in records}) == len(records) == 7
    assert all(r['revision'] and r['certified_x_revision'] is None for r in records)
    assert data['purpose'] == 'EVIDENCE_ONLY_NOT_MANUFACTURING_CAPABILITY_REGISTRY'
    assert data['unsupported_combination_policy'] == 'PREVIEW_ONLY_NO_DEFAULT_CENTER'
