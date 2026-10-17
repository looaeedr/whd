"""CADCraft opt-in Hole Editor preview: real DXF, no authority change."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, RectFeature, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_preview_bridge import (
    CadcraftPreviewError,
    build_hole_editor_cadcraft_scene,
    find_cadcraft_gui,
    open_hole_editor_cadcraft_preview,
)


def _context():
    surface = feature_surface_from_rect(
        "hole-editor-test", Vec2(0.0, 0.0), Vec2(100.0, 80.0)
    )
    features = [
        CircleFeature(
            diameter=10.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(25.0, 30.0), layer="CUTTING",
        ),
        RectFeature(
            width=20.0, height=12.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(70.0, 45.0), layer="CUTTING",
        ),
    ]
    return surface, features


def test_cadcraft_preview_exports_actual_hole_editor_coordinates_without_committing(tmp_path):
    surface, features = _context()
    original_features = tuple(features)
    exe = tmp_path / "cadcraft.exe"
    exe.write_bytes(b"not a real executable: launcher is injected")
    seen = []
    def launch(argv):
        seen.append(list(argv))

    path = open_hole_editor_cadcraft_preview(
        surface=surface, features=features, width=100.0, height=80.0,
        executable=str(exe), output_dir=tmp_path, launcher=launch,
    )
    assert path.exists() and seen == [[str(exe), str(path)]]
    doc = ezdxf.readfile(path)
    entities = tuple(doc.modelspace())
    assert entities and all(e.dxf.layer == "CHECK" for e in entities)
    circles = [e for e in entities if e.dxftype() == "CIRCLE"]
    assert len(circles) == 1
    assert tuple(circles[0].dxf.center[:2]) == pytest.approx((25.0, 30.0))
    assert circles[0].dxf.radius == 5.0
    assert len([e for e in entities if e.dxftype() == "LWPOLYLINE"]) == 2
    assert tuple(features) == original_features
    assert not any(p.suffix == ".p6fold" for p in tmp_path.iterdir())


def test_cadcraft_preview_preserves_existing_baseline_and_uses_check_for_active_holes():
    surface, features = _context()
    baseline = DrawingScene()
    baseline.add_line((0, 20), (100, 20), layer="BEND")
    previous = tuple(baseline.primitives)
    scene = build_hole_editor_cadcraft_scene(
        surface=surface, features=features, width=100, height=80,
        baseline_scene=baseline,
    )
    assert tuple(baseline.primitives) == previous
    assert scene.primitives[0] is previous[0]
    assert len([p for p in scene.primitives if p.layer == "BEND"]) == 1
    assert len([p for p in scene.primitives if p.layer == "CHECK"]) == 2


def test_cadcraft_preview_is_opt_in_and_missing_binary_does_not_write(tmp_path):
    surface, features = _context()
    missing = tmp_path / "not-installed.exe"
    with pytest.raises(CadcraftPreviewError, match="找不到"):
        open_hole_editor_cadcraft_preview(
            surface=surface, features=features, width=100, height=80,
            executable=str(missing), output_dir=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_cadcraft_preview_rejects_unsafe_features_and_never_overwrites_original(tmp_path):
    surface, features = _context()
    bad = [
        CircleFeature(
            diameter=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(300, 300),
        )
    ]
    with pytest.raises(CadcraftPreviewError, match="定位驗證"):
        build_hole_editor_cadcraft_scene(
            surface=surface, features=bad, width=100, height=80,
        )
    with pytest.raises(CadcraftPreviewError, match="DrawingScene"):
        build_hole_editor_cadcraft_scene(
            surface=surface, features=features, width=100, height=80,
            baseline_scene=object(),
        )
    # A failed external app launch removes its partial preview, not user data.
    exe = tmp_path / "cadcraft.exe"
    exe.write_bytes(b"fake")
    canonical = tmp_path / "baseline.dxf"
    canonical.write_bytes(b"USER_DATA")
    def fails(_argv):
        raise OSError("CADCraft failed to launch")
    with pytest.raises(OSError, match="failed to launch"):
        open_hole_editor_cadcraft_preview(
            surface=surface, features=features, width=100, height=80,
            executable=str(exe), output_dir=tmp_path, launcher=fails,
        )
    assert canonical.read_bytes() == b"USER_DATA"
    assert not tuple(tmp_path.glob("whd-inspection-*.dxf"))
