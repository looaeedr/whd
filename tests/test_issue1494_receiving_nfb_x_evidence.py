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
    (800, 2, [360.0]), (800, 3, [180.0, 180.0]),
])
def test_approved_relative_table_does_not_become_absolute_x(width, count, distances):
    item = next(r for r in evidence()['records']
                if (r['box_outer_width_mm'], r['nfb_count']) == (width, count))
    assert item['nominal_adjacent_center_distances_mm'] == distances
    assert item['gate'] == 'OPEN-X-ROW'
    assert item['x_status'] == 'PREVIEW_ONLY'
    for field in ('certified_x_revision', 'blank_x_origin', 'finished_face_x_origin',
                  'box_world_x_origin', 'blank_to_finished_face_x',
                  'finished_face_to_box_world_x'):
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


def test_uploaded_w800_three_dxf_measures_local_centers_from_its_side_lines():
    fixture = json.loads((ROOT / 'tests/fixtures/receiving_nfb_w800_three_source.json')
                         .read_text(encoding='utf-8'))
    entities = {e['handle']: e for e in fixture['entities']}
    left = entities[fixture['blank_left_handle']]
    right = entities[fixture['blank_right_handle']]
    assert left['start'][0] == left['end'][0]
    assert right['start'][0] == right['end'][0]
    origin = left['start'][0]
    assert right['start'][0] - origin == pytest.approx(723.0)
    centers = []
    for handles in fixture['aperture_side_handles']:
        sides = [entities[h] for h in handles]
        assert all(s['start'][0] == s['end'][0] for s in sides)
        side_x = sorted({s['start'][0] for s in sides})
        assert len(side_x) == 2
        assert side_x[1] - side_x[0] == pytest.approx(28.0)
        centers.append(sum(side_x) / 2.0 - origin)
    assert centers == pytest.approx([181.5, 361.5, 541.5])
    assert [b-a for a,b in zip(centers, centers[1:])] == pytest.approx([180.0,180.0])
    # Translate the entire source drawing: local X must stay identical.
    shift = 10000.0
    translated = [(c+origin+shift)-(origin+shift) for c in centers]
    assert translated == pytest.approx(centers)
    row = next(r for r in evidence()['records']
               if r['box_outer_width_mm'] == 800 and r['nfb_count'] == 3)
    assert row['source_dxf_sha256'] == fixture['source_sha256']
    assert row['source_geometry_observation']['centers_relative_to_source_left'] == pytest.approx(centers)
    assert row['x_status'] == 'PREVIEW_ONLY'
    assert row['blank_to_finished_face_x'] is None
    assert row['finished_face_to_box_world_x'] is None


def _w800_three_dxf_fixture():
    return json.loads(
        (ROOT / "tests/fixtures/receiving_nfb_w800_three_source.json")
        .read_text(encoding="utf-8")
    )


def _receiving_w800_t2_snapshot(*, left_neighbor_width=None):
    """Physical Receiving inner-door state; no independent NFB placement."""
    from ae_engine.cabinet_types.receiving import apply_family_defaults

    data = apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    if left_neighbor_width is None:
        data["door_layout_columns"] = [[800.0, [1100.0, 500.0]]]
        cell_key = "0:0"
    else:
        data["w"] = left_neighbor_width + 800.0
        data["door_layout_columns"] = [
            [left_neighbor_width, [1100.0, 500.0]],
            [800.0, [1100.0, 500.0]],
        ]
        cell_key = "1:0"
    data["multi_door_enabled"] = True
    data["door_layout_scope"] = "receiving-main"
    data["inner_doors"] = [{
        "stable_id": "upper", "cell_key": cell_key,
        "included_frame_sides": ["top", "left", "right"],
    }]
    return data


def test_w800_three_a1_is_dxf_side_line_not_certified_cutting_left():
    """A 723-mm open source side pair cannot certify the manufactured CUTTING."""
    source = _w800_three_dxf_fixture()
    entities = {item["handle"]: item for item in source["entities"]}
    left = entities[source["blank_left_handle"]]
    right = entities[source["blank_right_handle"]]
    assert (source["blank_left_handle"], source["blank_right_handle"]) == ("A1", "A0")
    assert left["type"] == right["type"] == "LINE"
    assert left["layer"] == right["layer"] == "0"
    assert left["color"] == right["color"] == 7
    assert right["start"][0] - left["start"][0] == pytest.approx(723)
    assert source["source_semantics"] == (
        "USER_SUPPLIED_PLACEMENT_EVIDENCE_NOT_CLOSED_MANUFACTURING_DXF"
    )
    obs = evidence()["w800_t2_three_hole_observation"]
    assert obs["source_dxf_sha256"] == source["source_sha256"]
    assert obs["source_outline_is_723_cutting_left_verified"] is False
    assert obs["certified_x_revision"] is None
    assert obs["not_exportable_as_manufacturing_x"] is True


@pytest.mark.parametrize(
    "left_neighbor_width,expected_center_world_x",
    [(None, 0.0), (400.0, 200.0)],
)
def test_w800_three_shadow_roundtrip_reuses_real_inner_door_placement(
    left_neighbor_width, expected_center_world_x,
):
    """Candidate only: use canonical part placement, not a separate NFB offset."""
    from ae_engine.cabinet_types import policy
    from ae_engine.assembly_placement import resolve_inner_door_panel_placement
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    state = _receiving_w800_t2_snapshot(left_neighbor_width=left_neighbor_width)
    panel = policy.derive_inner_door_panels(state)[0]
    placement = resolve_inner_door_panel_placement(state, "upper")
    render = build_inner_door_panel_render_data(panel)
    cutting = [p for p in render.scene.primitives
               if isinstance(p, PolylinePrimitive)
               and p.layer.upper() == "CUTTING" and p.closed]
    assert len(cutting) == 1
    cutting_x = [float(pt.x) for pt in cutting[0].points]
    assert max(cutting_x) - min(cutting_x) == pytest.approx(723.0)
    assert panel.stable_id == placement.stable_id == "inner_door:upper:panel"
    assert panel.width == pytest.approx(689.0)
    assert panel.unfolded_width == pytest.approx(723.0)
    assert placement.anchor == "inner_door_frame_opening:upper"
    assert placement.world_offset[0] == pytest.approx(expected_center_world_x)

    source = _w800_three_dxf_fixture()
    by_handle = {item["handle"]: item for item in source["entities"]}
    left_x = by_handle[source["blank_left_handle"]]["start"][0]
    right_x = by_handle[source["blank_right_handle"]]["start"][0]
    centers = []
    for handles in source["aperture_side_handles"]:
        sides = [by_handle[h]["start"][0] for h in handles]
        centers.append((min(sides) + max(sides)) / 2)
    assert right_x - left_x == pytest.approx(panel.unfolded_width)

    # NON-MANUFACTURING witness only. The source CUTTING identity, developed
    # face projection and owner-approved X orientation remain unverified.
    # Never persist these conditional world values to the capability registry.
    half = panel.unfolded_width / 2
    candidate_world = [
        placement.world_offset[0] + (center - left_x - half)
        for center in centers
    ]
    assert candidate_world == pytest.approx([
        expected_center_world_x - 180, expected_center_world_x,
        expected_center_world_x + 180,
    ])
    reverse_source = [
        (world - placement.world_offset[0]) + half + left_x
        for world in candidate_world
    ]
    assert reverse_source == pytest.approx(centers)
    obs = evidence()["w800_t2_three_hole_observation"]
    assert obs["box_world_centers_mm"] is None
    assert obs["certified_x_revision"] is None
    row = next(item for item in evidence()["records"]
               if (item["box_outer_width_mm"], item["nfb_count"]) == (800, 3))
    assert row["x_status"] == "PREVIEW_ONLY"
    assert row["blank_to_finished_face_x"] is None
    assert row["finished_face_to_box_world_x"] is None
