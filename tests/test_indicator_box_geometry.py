import ae_engine.ae as ae


def first_cutting(data):
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    return next(p for p in data.scene.primitives if isinstance(p, PolylinePrimitive) and p.layer == 'CUTTING')


def test_indicator_box_preserves_47_49_geometry_at_t2():
    geom = ae.get_indicator_box_data([2, 3], T_val=2.0)
    poly = first_cutting(geom)
    w, h = geom.params['w'], geom.params['h']
    assert [(p.x, p.y) for p in poly.points[:4]] == [(47.0, 0.0), (w - 47.0, 0.0), (w - 47.0, 49.0), (w, 49.0)]
    from ae_engine.sheetmetal_drawing import LinePrimitive
    bends = [p for p in geom.scene.primitives if isinstance(p, LinePrimitive) and p.layer == 'BEND'][:4]
    assert (bends[0].p1.x, bends[0].p1.y, bends[0].p2.x, bends[0].p2.y) == (49.0, 0.0, 49.0, h)


def test_indicator_box_corner_tracks_thickness_instead_of_fixed_47():
    geom = ae.get_indicator_box_data([1], T_val=1.5)
    poly = first_cutting(geom)
    w = geom.params['w']
    assert (poly.points[0].x, poly.points[0].y) == (47.5, 0.0)
    assert (poly.points[1].x, poly.points[1].y) == (w - 47.5, 0.0)
