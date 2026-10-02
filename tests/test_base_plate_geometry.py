import ae_engine.ae as ae



def test_base_plate_adapter_matches_existing_cross_shape():
    outline, bends, g = ae._make_base_plate_geometry(500.0, 400.0, 2.0, 55.0, 55.0, 55.0, 55.0, 15.0)
    w = 500.0 - 55.0 - 55.0 + 30.0
    h = 400.0 - 55.0 - 55.0 + 30.0
    assert [(p.x,p.y) for p in outline] == [
        (15.0,0.0),(w-15.0,0.0),(w-15.0,15.0),(w,15.0),
        (w,h-15.0),(w-15.0,h-15.0),(w-15.0,h),(15.0,h),
        (15.0,h-15.0),(0.0,h-15.0),(0.0,15.0),(15.0,15.0),(15.0,0.0)
    ]
    bm={b.name:((b.p1.x,b.p1.y),(b.p2.x,b.p2.y)) for b in bends}
    assert bm['bottom']==((15.0,15.0),(w-15.0,15.0))
    assert bm['left']==((15.0,15.0),(15.0,h-15.0))
