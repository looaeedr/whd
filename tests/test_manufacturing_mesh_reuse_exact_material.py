"""The mesh reuse decorator must preserve the opt-in exact-material mode."""
from shapely.geometry import box

from ae_engine.assembly_mesh_reuse import mesh_build_scope, reuse_local_mesh


def test_legacy_strict_builder_does_not_receive_inactive_exact_material():
    calls = []

    @reuse_local_mesh
    def build(material, x_profile, y_profile, *, fold_exemptions=(), fold_guides=()):
        calls.append((fold_exemptions, fold_guides))
        return object()

    material = box(0, 0, 20, 30)
    xp, yp = ({'len': 20},), ({'len': 30},)
    # Both default and explicit False must retain the old strict signature.
    build(material, xp, yp)
    build(material, xp, yp, exact_material=False)
    assert len(calls) == 2
    with mesh_build_scope():
        first = build(material, xp, yp)
        assert build(material, xp, yp, exact_material=False) is first
    assert calls == [((), ())] * 3


def test_preview_and_exact_have_separate_cache_entries_in_one_scope():
    calls = []

    @reuse_local_mesh
    def build(material, x_profile, y_profile, *, fold_exemptions=(),
              fold_guides=(), exact_material=False):
        calls.append(exact_material)
        return (exact_material, object())

    material = box(0, 0, 20, 30)
    xp, yp = ({'len': 20},), ({'len': 30},)
    with mesh_build_scope():
        preview = build(material, xp, yp)
        exact = build(material, xp, yp, exact_material=True)
        assert preview[0] is False and exact[0] is True
        assert preview is not exact
        assert build(material, xp, yp, exact_material=False) is preview
        assert build(material, xp, yp, exact_material=True) is exact
        assert calls == [False, True]
    with mesh_build_scope():
        # Exact-first ordering must also remain distinct, without leaking the
        # previous scope's cached objects.
        next_exact = build(material, xp, yp, exact_material=True)
        next_preview = build(material, xp, yp, exact_material=False)
        assert next_exact[0] is True and next_preview[0] is False
        assert next_exact is not exact and next_preview is not preview
        assert build(material, xp, yp, exact_material=True) is next_exact
        assert build(material, xp, yp) is next_preview
    assert calls == [False, True, True, False]


def test_exact_material_forwarded_without_cache_alongside_tip_extension():
    calls = []

    @reuse_local_mesh
    def build(material, x_profile, y_profile, *, fold_exemptions=(),
              fold_guides=(), **kwargs):
        calls.append(kwargs)
        return object()

    material = box(0, 0, 20, 30)
    xp, yp = ({'len': 20},), ({'len': 30},)
    tip = (('x', 10., 0., 30.),)
    first = build(material, xp, yp, exact_material=True)
    second = build(material, xp, yp, exact_material=True,
                   fold_tip_continuity=tip)
    assert first is not second
    build(material, xp, yp, exact_material=False, fold_tip_continuity=tip)
    build(material, xp, yp)
    assert calls == [
        {'exact_material': True},
        {'exact_material': True, 'fold_tip_continuity': tip},
        {'fold_tip_continuity': tip},
        {},
    ]
