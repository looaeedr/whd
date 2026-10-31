# -*- coding: utf-8 -*-
"""GUI PAD 3D never reuses a stale source or silently hides its failure."""
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.receiving_nfb_pad_preview_cache import (
    pad_preview_source_fingerprint,
)


def test_pad_cache_changes_with_tooling_csv_and_real_base_shape(tmp_path,monkeypatch):
    import ae_engine.receiving_nfb_numeric_catalog as catalog
    import ae_engine.receiving_nfb_pad_generator as generator
    import ae_engine.receiving_nfb_pad_preview_cache as cache

    # Test the same file-backed source graph without touching the project DB.
    source=tmp_path/"base"
    (source/"基準檔/開孔/NFB").mkdir(parents=True)
    tooling=source/"基準檔/開孔/NFB/墊高片共用加工規則.json"
    tooling.write_text('{"source":"first"}',encoding="utf-8")
    csv=tmp_path/"active_model.csv"
    csv.write_bytes(b"one")
    monkeypatch.setattr(cache,"__file__",str(source/"ae_engine"/"receiving_nfb_pad_preview_cache.py"))
    monkeypatch.setattr(catalog,"brand_csv_path",lambda _brand:csv)
    snap={"model":"受電箱","nfb_config":{"holes":[
        {"model_filename":"nfbv5:士林:100HN-s"}]}}
    def part(material):
        return SimpleNamespace(
            part_key="base_plate",offset=(0.,120.,-140.),
            render_data=SimpleNamespace(material=material,fold_guides=(),
                unfolded_topology="root",metadata={"nfb_v5_pad_square_owners":()}))
    a=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    csv.write_bytes(b"two")
    b=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    assert b!=a
    tooling.write_text('{"source":"second"}',encoding="utf-8")
    c=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    assert c!=b
    d=pad_preview_source_fingerprint(snap,(part(box(0,0,99,100)),))
    assert d!=c
    csv.unlink()
    with pytest.raises(FileNotFoundError):
        pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))


def test_gui_exposes_pad_failure_as_visible_warning_not_success():
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    adapter=Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter.last_formed_pad_display_blocker="PAD_BASE_LOCATOR_SQUARES_NOT_SAME_OWNER"
    assert "PAD_BASE_LOCATOR_SQUARES_NOT_SAME_OWNER" in (
        " ".join(adapter._pad_display_warnings())
    )
    adapter.last_formed_pad_display_blocker=None
    assert adapter._pad_display_warnings()==()


def _pad_base_with_real_cutting_scene(scene):
    return SimpleNamespace(
        part_key="base_plate", placement="set-1", rotation=(0, 0, 0),
        offset=(0., 120., -140.),
        render_data=SimpleNamespace(
            material=box(0, 0, 100, 100), scene=scene,
            fold_guides=(), unfolded_topology="root",
            metadata={"nfb_v5_pad_square_owners": (("pad-1", 4),)},
        ),
    )


def test_pad_preview_fingerprint_rechecks_real_cutting_squares_not_only_material():
    """An altered physical CUTTING square must invalidate a previously verified PAD."""
    from ae_engine.sheetmetal_drawing import DrawingScene

    scene=DrawingScene()
    scene.add_polyline(((10, 10), (16, 10), (16, 16), (10, 16)),
                       layer="CUTTING", closed=True, color=30)
    base=_pad_base_with_real_cutting_scene(scene)
    snapshot={"model": "受電箱", "nfb_config_submitted": True}
    original=pad_preview_source_fingerprint(snapshot, (base,))

    # A projected source scene can become stale independently from a cached
    # material polygon or owner-count metadata (e.g. a shifted locator cut).
    scene.primitives.clear()
    missing=pad_preview_source_fingerprint(snapshot, (base,))
    scene.add_polyline(((20, 10), (26, 10), (26, 16), (20, 16)),
                       layer="CUTTING", closed=True, color=30)
    shifted=pad_preview_source_fingerprint(snapshot, (base,))
    assert original != missing
    assert missing != shifted
    assert original != shifted


def test_native_pad_preview_cache_revalidates_when_cutting_scene_changes(monkeypatch):
    """Do not reuse a green 3D PAD skin after actual Base locator cuts vanish."""
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    import ae_engine.receiving_nfb_pad_assembly_preview as live

    scene=DrawingScene()
    scene.add_polyline(((10, 10), (16, 10), (16, 16), (10, 16)),
                       layer="CUTTING", closed=True, color=30)
    base=_pad_base_with_real_cutting_scene(scene)
    snapshot={"model": "受電箱", "nfb_config_submitted": True}
    calls=[]
    safe_skin=SimpleNamespace(
        parent_base_id="base_plate", manufacturing_ready=False,
        assembly_contact_certified=False,
    )

    def recheck(_snapshot, _parts):
        calls.append(len(scene.primitives))
        if not scene.primitives:
            raise ValueError("PAD_BASE_FOUR_LOCATOR_SQUARES_NOT_REAL_CUTTING")
        return (safe_skin,)

    monkeypatch.setattr(live, "build_committed_pad_assembly_display", recheck)
    adapter=Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_pad_display_cache=None
    adapter.last_formed_pad_display_blocker=None
    assert adapter._formed_pad_assembly_preview(
        snapshot, {"base_plate"}, (base,)
    ) == (safe_skin,)

    scene.primitives.clear()
    # Same material.wkb/fold/metadata/snapshot but lost CUTTING geometry.
    # The second invocation MUST reach the actual verification path.
    assert adapter._formed_pad_assembly_preview(
        snapshot, {"base_plate"}, (base,)
    ) == ()
    assert calls == [1, 0]
    assert "PAD_BASE_FOUR_LOCATOR_SQUARES_NOT_REAL_CUTTING" in (
        adapter.last_formed_pad_display_blocker
    )


def test_pad_cache_ignores_independent_fixing_plate_child_but_checks_real_tier_base():
    """Only actual Base parents own PAD locator geometry (not EAR child parts)."""
    from ae_engine.sheetmetal_drawing import DrawingScene

    snapshot={"model":"受電箱","nfb_config_submitted":True}
    base=_pad_base_with_real_cutting_scene(DrawingScene())
    unrelated=SimpleNamespace(
        part_key="base_plate:fixing_plate:left",
        render_data=SimpleNamespace(material=None),
    )
    expected=pad_preview_source_fingerprint(snapshot,(base,))
    assert pad_preview_source_fingerprint(snapshot,(base,unrelated))==expected

    # A genuine two-tier parent must still be included, including its cuts.
    tier=_pad_base_with_real_cutting_scene(DrawingScene())
    tier.part_key="base_plate:nfb_layer:0"
    with_tier=pad_preview_source_fingerprint(snapshot,(base,tier))
    assert with_tier!=expected
    tier.render_data.material=box(0,0,99,100)
    assert pad_preview_source_fingerprint(snapshot,(base,tier))!=with_tier


def test_pad_gui_cache_does_not_hide_valid_skin_because_unrelated_ear_has_no_material(monkeypatch):
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    import ae_engine.receiving_nfb_pad_assembly_preview as live

    base=_pad_base_with_real_cutting_scene(DrawingScene())
    ear=SimpleNamespace(
        part_key="base_plate:fixing_plate:left",
        render_data=SimpleNamespace(material=None),
    )
    safe_skin=SimpleNamespace(
        parent_base_id="base_plate", manufacturing_ready=False,
        assembly_contact_certified=False,
    )
    called=[]
    def verified_pad(_snapshot,_parts):
        called.append(True)
        return (safe_skin,)
    monkeypatch.setattr(live,"build_committed_pad_assembly_display",verified_pad)
    adapter=Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_pad_display_cache=None
    adapter.last_formed_pad_display_blocker=None
    result=adapter._formed_pad_assembly_preview(
        {"model":"受電箱","nfb_config_submitted":True},
        {"base_plate"},(base,ear),
    )
    assert result==(safe_skin,)
    assert called==[True]
    assert adapter.last_formed_pad_display_blocker is None


@pytest.mark.parametrize("invalid_material", (object(), "not-a-geometry"))
def test_pad_preview_cache_rejects_corrupt_physical_base_material_at_source(invalid_material):
    """The optional 3D PAD must fail closed before accessing geometry internals."""
    from ae_engine.sheetmetal_drawing import DrawingScene

    base = _pad_base_with_real_cutting_scene(DrawingScene())
    base.render_data.material = invalid_material
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    with pytest.raises(ValueError, match="PAD_PREVIEW_PARENT_MATERIAL_INVALID"):
        pad_preview_source_fingerprint(snapshot, (base,))


def test_pad_3d_adapter_hides_corrupt_base_material_and_exposes_blocker():
    """One invalid provider material must not crash the entire assembly 3D."""
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter

    base = _pad_base_with_real_cutting_scene(DrawingScene())
    base.render_data.material = object()
    adapter = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_pad_display_cache = None
    adapter.last_formed_pad_display_blocker = None
    assert adapter._formed_pad_assembly_preview(
        {"model": "受電箱", "nfb_config_submitted": True},
        {"base_plate"}, (base,),
    ) == ()
    assert adapter.last_formed_pad_display_blocker == "PAD_PREVIEW_PARENT_MATERIAL_INVALID"
    assert "PAD_PREVIEW_PARENT_MATERIAL_INVALID" in " ".join(
        adapter._pad_display_warnings()
    )
