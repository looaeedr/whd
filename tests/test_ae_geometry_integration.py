
import pytest
import ae_engine.ae as ae


def _coords(points):
    return {(round(float(x), 6), round(float(y), 6)) for x, y in points}


def test_endcap_contour_helper_uses_confirmed_geometry_engine_rules():
    pts = ae.get_end_cap_contour_points(
        w=400.0,
        d=250.0,
        t=2.0,
        fw=25.0,
        yl1=15.0,
        yr1=15.0,
        ytop1=16.0,
        ybottom1=15.0,
    )
    total_depth = ae.calculate_y_depth(16.0, 15.0, 250.0, 2.0, 25.0)
    coords = _coords(pts)

    # bottom = fold + 0.5T = 16
    assert (16.0, 0.0) in coords
    assert (0.0, 16.0) in coords

    # primary = fold + FW = 40, primary height = 39
    assert (40.0, total_depth) in coords
    assert (40.0, total_depth - 39.0) in coords

    # secondary = fold + 0.5T = 16, depth = 2T = 4
    assert (16.0, total_depth - 39.0) in coords
    assert (16.0, total_depth - 43.0) in coords


def test_relief_defaults_are_factor_based():
    cfg = ae.RELIEF_CONFIG
    assert cfg.top_secondary_x_factor == 0.5
    assert cfg.top_secondary_depth_factor == 2.0
    assert cfg.bottom_x_factor == 0.5
    assert cfg.bottom_y_factor == 0.5


def test_stretched_export_passes_fw_and_tail_to_geometry_loader(monkeypatch, tmp_path):
    captured = {}

    class StopAfterCapture(RuntimeError):
        pass

    def fake_loader(
        model_name, W_val, H_val, D_val, T_val, FW_val=None, is_tail=False,
        corner_policy=None, x_topology="folded",
        box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    ):
        captured.update(
            model_name=model_name,
            W_val=W_val,
            H_val=H_val,
            D_val=D_val,
            T_val=T_val,
            FW_val=FW_val,
            is_tail=is_tail,
            corner_policy=corner_policy,
            x_topology=x_topology,
            box_body_formed_fw_left=box_body_formed_fw_left,
            box_body_formed_fw_right=box_body_formed_fw_right,
        )
        raise StopAfterCapture()

    monkeypatch.setattr(ae, "get_stretched_end_cap_data", fake_loader)

    with pytest.raises(StopAfterCapture):
        ae.export_stretched_end_cap_dxf(
            str(tmp_path / "x.dxf"),
            "金庫型",
            W_val=600.0,
            H_val=500.0,
            D_val=150.0,
            T_val=2.0,
            FW_val=27.0,
            is_tail=True,
        )

    assert captured["FW_val"] == 27.0
    assert captured["is_tail"] is True
    assert captured["x_topology"] == "folded"
    assert captured["corner_policy"] is None


def test_door_adapter_matches_current_default_structural_geometry():
    outline, bends, _ = ae._make_door_geometry(
        W_val=400.0,
        H_val=600.0,
        T_val=2.0,
        FW_val=25.0,
        gap_w=3.5,
        gap_h=3.5,
        fold_left=19.0,
        fold_right=15.0,
        fold_top=15.0,
        fold_bottom=15.0,
    )
    blank_w, blank_h = ae.calculate_door_blank_size(
        400.0, 600.0, 2.0, 25.0, 3.5, 3.5, 19.0, 15.0, 15.0, 15.0
    )
    assert [(p.x, p.y) for p in outline] == [
        (17.0, 0.0),
        (blank_w - 13.0, 0.0),
        (blank_w - 13.0, 15.0),
        (blank_w, 15.0),
        (blank_w, blank_h - 15.0),
        (blank_w - 13.0, blank_h - 15.0),
        (blank_w - 13.0, blank_h),
        (17.0, blank_h),
        (17.0, blank_h - 15.0),
        (0.0, blank_h - 15.0),
        (0.0, 15.0),
        (17.0, 15.0),
        (17.0, 0.0),
    ]
    bend_map = {b.name: ((b.p1.x, b.p1.y), (b.p2.x, b.p2.y)) for b in bends}
    assert bend_map["left"] == ((19.0, 0.0), (19.0, blank_h))
    assert bend_map["right"] == ((blank_w - 15.0, 0.0), (blank_w - 15.0, blank_h))
    assert bend_map["bottom"] == ((17.0, 15.0), (blank_w - 13.0, 15.0))
    assert bend_map["top"] == ((17.0, blank_h - 15.0), (blank_w - 13.0, blank_h - 15.0))


def test_stretched_door_uses_shared_door_geometry_builder(monkeypatch):
    calls = []
    real = ae._make_door_geometry

    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(ae, "_make_door_geometry", wrapped)
    import ezdxf as real_ezdxf
    monkeypatch.setattr(ae, "ezdxf", real_ezdxf)
    geom = ae.get_stretched_door_data(
        "金庫型",
        W_val=400.0,
        H_val=600.0,
        T_val=2.0,
        FW_val=25.0,
        fl_val=19.0,
        fr_val=15.0,
        ft_val=15.0,
        fb_val=15.0,
    )

    assert calls, "stretched door must use the same structural builder as direct door"
    expected_outline, expected_bends, _ = real(
        400.0, 600.0, 2.0, 25.0,
        ae.door_gap_w_def, ae.door_gap_h_def,
        19.0, 15.0, 15.0, 15.0,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    structural = [p for p in geom.scene.primitives if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"]
    assert [(round(p.x, 6), round(p.y, 6)) for p in structural[0].points] == [
        (round(p.x, 6), round(p.y, 6)) for p in expected_outline
    ]


def test_box_body_adapter_replaces_manual_x1_x8_accumulation():
    chain = ae._make_box_body_chain(
        w=600.0, h=500.0, d=150.0, t=2.0, fw=25.0,
        zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=9.0,
        include_right_fw=True,
    )
    bends = ae.build_strip_bend_segments(chain)
    assert [b.p1.x for b in bends] == [16.0, 37.0, 63.0, 210.0, 807.0, 954.0, 980.0, 1001.0]
    assert chain.total_width == ae.calculate_z_length(15.0,20.0,15.0,20.0,9.0,600.0,150.0,2.0,25.0)


def test_stretched_box_body_uses_shared_strip_chain_builder(monkeypatch, tmp_path):
    calls=[]
    real=ae._make_box_body_chain
    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(ae, '_make_box_body_chain', wrapped)

    import ezdxf as real_ezdxf
    monkeypatch.setattr(ae, 'ezdxf', real_ezdxf)
    base_root = tmp_path / '基準檔'
    model_dir = base_root / '測試型'
    model_dir.mkdir(parents=True)
    doc = real_ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(1008,0),(1008,496),(0,496),(0,0)], dxfattribs={'layer':'CUTTING'})
    for x in [15,35,60,206,802,948,973,993]:
        msp.add_line((x,0),(x,496), dxfattribs={'layer':'BEND'})
    doc.saveas(model_dir / '箱身.dxf')

    monkeypatch.setattr(ae, 'get_resource_path', lambda rel: str(base_root) if rel == '基準檔' else str(tmp_path / rel))
    geom=ae.get_stretched_box_body_data('測試型', 600.0, 500.0, 150.0, 2.0, FW_val=25.0, z_comp_val=0.0)
    assert calls, 'stretched box body must use shared strip-chain builder'
    from ae_engine.sheetmetal_drawing import LinePrimitive
    bend_lines=[p for p in geom.scene.primitives if isinstance(p, LinePrimitive) and p.layer=='BEND']
    params=geom.params
    chain=real(600.0,500.0,150.0,2.0,params['fw'],params['zl1'],params['zl2'],params['zr1'],params['zr2'],params['z_comp'], len(bend_lines)==8)
    expected=[b.p1.x for b in ae.build_strip_bend_segments(chain)]
    actual=[line.p1.x for line in bend_lines[:len(expected)]]
    assert actual==expected



def test_resolved_feature_serializer_preserves_cutting_and_marking_layers():
    from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect
    from ae_engine.sheetmetal_geometry import Vec2

    class FakeMsp:
        def __init__(self):
            self.circles = []
            self.lines = []
            self.polylines = []

        def add_circle(self, center, radius, dxfattribs=None):
            self.circles.append((center, radius, dxfattribs or {}))

        def add_line(self, p1, p2, dxfattribs=None):
            self.lines.append((p1, p2, dxfattribs or {}))

        def add_lwpolyline(self, points, dxfattribs=None, close=False):
            self.polylines.append((list(points), dxfattribs or {}, close))

    msp = FakeMsp()
    features = [
        ResolvedCircle(Vec2(10, 20), 5, layer='CUTTING'),
        ResolvedCircle(Vec2(30, 40), 6, layer='MARKING', add_centerline=True),
        ResolvedRect(Vec2(50, 60), 20, 10, layer='CUTTING'),
    ]
    from ae_engine.sheetmetal_drawing import DrawingScene, resolved_features_to_primitives
    scene = DrawingScene()
    scene.extend(resolved_features_to_primitives(features))
    ae._add_drawing_scene_to_dxf(msp, scene)

    assert msp.circles[0][2]['layer'] == 'CUTTING'
    assert msp.circles[1][2]['layer'] == 'MARKING'
    assert len(msp.lines) == 1
    assert msp.lines[0][2]['layer'] == 'MARKING'
    assert len(msp.polylines) == 1
    assert msp.polylines[0][1]['layer'] == 'CUTTING'


def test_endcap_scene_builder_uses_shared_part_adapter():
    import inspect
    builder_src = inspect.getsource(ae._build_end_cap_scene)
    exporter_src = inspect.getsource(ae.export_end_cap_dxf)
    assert "build_endcap_result" in builder_src
    assert "_build_end_cap_scene" in exporter_src
    assert "_save_scene_dxf" in exporter_src


def test_base_plate_scene_builder_uses_shared_mounting_hole_resolver():
    import inspect
    import ae_engine.ae as ae
    builder_src = inspect.getsource(ae._build_base_plate_scene)
    exporter_src = inspect.getsource(ae.export_base_plate_dxf)
    assert 'bend + 15.0' not in builder_src
    assert 'resolve_base_plate_mounting_holes' in builder_src
    assert '_build_base_plate_scene' in exporter_src
    assert '_save_scene_dxf' in exporter_src


def test_door_exporters_do_not_rederive_indicator_position_constants():
    import inspect
    import ae_engine.ae as ae
    for func in (ae.export_door_dxf, ae.get_stretched_door_data, ae.export_stretched_door_dxf):
        src = inspect.getsource(func)
        assert 'cx_min = 191.0' not in src
        assert 'dy_top_light = (133.5' not in src
        assert 'offset_x_phys' not in src
        assert 'H_active = 280.0' not in src


def test_endcap_scene_builder_uses_shared_fixed_feature_resolver():
    import inspect
    import ae_engine.ae as ae
    builder_src = inspect.getsource(ae._build_end_cap_scene)
    exporter_src = inspect.getsource(ae.export_end_cap_dxf)
    # T6: _build_end_cap_scene 已升級為呼叫 resolve_endcap_fixed_features_for_model
    # 以支援依 model_name 路由 Vault vs Receiving 固定特徵，不再直接呼叫 Vault 專用函式
    assert 'resolve_endcap_fixed_features_for_model' in builder_src
    assert '_build_end_cap_scene' in exporter_src
    combined = builder_src + exporter_src
    assert 'lx = notch_tl_x + 10.5' not in combined
    assert 'rx = (total_width - notch_tr_x) - 10.5' not in combined
    assert 'sq_pts = [' not in combined
    assert '10.5' not in combined


def test_drawing_primitive_serializer_preserves_geometry_and_attributes():
    from ae_engine.sheetmetal_drawing import PolylinePrimitive, LinePrimitive, TextPrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    class FakeMsp:
        def __init__(self):
            self.polylines=[]; self.lines=[]; self.texts=[]
        def add_lwpolyline(self, points, close=False, dxfattribs=None):
            self.polylines.append((list(points), close, dxfattribs or {}))
        def add_line(self, p1, p2, dxfattribs=None):
            self.lines.append((p1,p2,dxfattribs or {}))
        def add_mtext(self, text, dxfattribs=None):
            self.texts.append((text,dxfattribs or {}))

    msp=FakeMsp()
    primitives=(
        PolylinePrimitive((Vec2(0,0),Vec2(10,0),Vec2(0,0)), 'STOCK', color=4),
        LinePrimitive(Vec2(1,2), Vec2(3,4), 'CHECK', 2),
        TextPrimitive('hello', Vec2(5,6), 'CHECK', 15.0, 5, 2),
    )
    from ae_engine.sheetmetal_drawing import DrawingScene
    scene = DrawingScene()
    scene.extend(primitives)
    ae._add_drawing_scene_to_dxf(msp, scene)
    assert msp.polylines == [([(0,0),(10,0),(0,0)], False, {'layer':'STOCK','color':4})]
    assert msp.lines == [((1,2),(3,4),{'layer':'CHECK','color':2})]
    assert msp.texts == [('hello', {'layer':'CHECK','insert':(5,6),'char_height':15.0,'attachment_point':5,'color':2})]


def test_drawing_scene_serializer_handles_all_primitives_and_marking_defaults():
    from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive, TextPrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    class FakeMsp:
        def __init__(self):
            self.polylines=[]; self.lines=[]; self.circles=[]; self.texts=[]
        def add_lwpolyline(self, points, close=False, dxfattribs=None):
            self.polylines.append((list(points), close, dxfattribs or {}))
        def add_line(self, p1, p2, dxfattribs=None):
            self.lines.append((p1,p2,dxfattribs or {}))
        def add_circle(self, center, radius, dxfattribs=None):
            self.circles.append((center,radius,dxfattribs or {}))
        def add_mtext(self, text, dxfattribs=None):
            self.texts.append((text,dxfattribs or {}))

    scene = DrawingScene()
    scene.extend((
        PolylinePrimitive((Vec2(0,0), Vec2(10,0)), 'CUTTING'),
        LinePrimitive(Vec2(1,2), Vec2(3,4), 'MARKING'),
        CirclePrimitive(Vec2(5,6), 2.5, 'MARKING'),
        TextPrimitive('check', Vec2(7,8), 'CHECK', 12.0, 5, 2),
    ))
    msp=FakeMsp()
    ae._add_drawing_scene_to_dxf(msp, scene)
    assert msp.polylines[0][2] == {'layer':'CUTTING'}
    assert msp.lines[0][2] == {'layer':'MARKING','color':211}
    assert msp.circles[0][2] == {'layer':'MARKING','color':211}
    assert msp.texts[0][1]['layer'] == 'CHECK'
    assert msp.texts[0][1]['color'] == 2


def test_setup_dxf_layers_creates_blind_hole_layer():
    import ezdxf
    import ae_engine.ae as ae
    doc = ezdxf.new('R2010')
    ae.setup_dxf_layers(doc)
    layer = doc.layers.get('BLIND_HOLE')
    assert layer.dxf.color == 1
    assert layer.dxf.linetype == 'CONTINUOUS'
