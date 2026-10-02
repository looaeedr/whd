from __future__ import annotations

from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2


def test_multi_door_feature_maps_use_formal_part_identity_and_isolate_cells():
    from ae_engine.sheetmetal_part_adapters import (
        door_layout_feature_map_to_part_features,
        door_part_features_to_layout_feature_map,
    )

    upper = CircleFeature(20.0, FeatureAnchor.PANEL_CENTER, Vec2(1.0, 2.0))
    lower = CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(3.0, 4.0))
    columns = [(800.0, [1100.0, 500.0])]
    formal = door_layout_feature_map_to_part_features(
        columns,
        {"0:0": [upper], "0:1": [lower]},
    )
    assert formal == {"door_c1_r1": [upper], "door_c1_r2": [lower]}
    formal["door_c1_r1"].append(lower)
    assert formal["door_c1_r2"] == [lower]

    restored = door_part_features_to_layout_feature_map(columns, formal)
    assert restored["0:0"] == [upper, lower]
    assert restored["0:1"] == [lower]


def test_receiving_two_door_assembly_offsets_are_distinct_and_front_placed():
    import fold_designer_bridge as bridge

    snapshot = {
        "w": 800.0,
        "h": 1600.0,
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "t": 2.0,
        "fw": 25.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
    }
    upper = bridge._phase6_door_part_assembly_placement(snapshot, "door_c1_r1")
    lower = bridge._phase6_door_part_assembly_placement(snapshot, "door_c1_r2")
    assert upper[0] == lower[0] == "front"
    assert upper[1] != lower[1]
    assert upper[1] == (0.0, 250.0, 0.0)
    assert lower[1] == (0.0, -550.0, 0.0)


def test_project_file_roundtrip_preserves_per_door_features(tmp_path):
    import phase6_project_file as project

    upper = CircleFeature(20.0, FeatureAnchor.PANEL_CENTER, Vec2(1.0, 2.0))
    lower = CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(3.0, 4.0))
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "w": 800.0,
            "h": 1600.0,
            "d": 350.0,
            "t": 2.0,
            "multi_door_enabled": True,
            "door_layout_columns": [[800.0, [1100.0, 500.0]]],
            "part_features": {
                "door_c1_r1": [upper],
                "door_c1_r2": [lower],
            },
        },
    }
    path = project.write_project(tmp_path / "receiving-two-door.p6fold", payload)
    loaded = project.read_project(path)["snapshot"]
    assert loaded["part_features"]["door_c1_r1"] == [upper]
    assert loaded["part_features"]["door_c1_r2"] == [lower]
    assert loaded["part_features"]["door_c1_r1"] is not loaded["part_features"]["door_c1_r2"]
