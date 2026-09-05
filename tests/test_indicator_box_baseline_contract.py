from dataclasses import fields
from pathlib import Path
import ast

import ezdxf
import pytest

from ae_engine import ae
from ae_engine.contracts import IndicatorBoxPartSpec, ManufacturingContext
from ae_engine import manufacturing_api


def _make_indicator_box_baseline(root: Path):
    base = root / '基準檔' / '指示燈'
    base.mkdir(parents=True, exist_ok=True)
    path = base / '盒子.dxf'
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    # Baseline one-group overall size 326 x 445, folds 49 mm.
    msp.add_lwpolyline(
        [(0, 0), (326, 0), (326, 445), (0, 445)],
        close=True,
        dxfattribs={'layer': 'CUTTING'},
    )
    for x in (49, 277):
        msp.add_line((x, 0), (x, 445), dxfattribs={'layer': 'BEND'})
    for y in (49, 396):
        msp.add_line((0, y), (326, y), dxfattribs={'layer': 'BEND'})
    # Fixed baseline-only manufacturing hole on the right flange.
    msp.add_circle((300, 20), 4.0, dxfattribs={'layer': 'CUTTING'})
    # Stale one-group indicator hole; stretched data must replace dynamic indicator content.
    msp.add_circle((191, 133.5), 15.5, dxfattribs={'layer': 'CUTTING'})
    doc.saveas(path)
    (base / '小門.dxf').write_text('shared-small-door', encoding='utf-8')
    return path


def test_indicator_box_spec_declares_baseline_model_name():
    assert 'model_name' in {f.name for f in fields(IndicatorBoxPartSpec)}


def test_indicator_box_expected_baseline_is_indicator_box_file(tmp_path):
    baseline = _make_indicator_box_baseline(tmp_path)
    spec = IndicatorBoxPartSpec(layer_groups=(2,), thickness=2.0)
    expected = manufacturing_api.expected_baseline_path_for(
        spec, ManufacturingContext(resource_root=tmp_path)
    )
    assert expected == baseline


def test_stretched_indicator_box_uses_baseline_fixed_features_and_dynamic_indicators(tmp_path, monkeypatch):
    _make_indicator_box_baseline(tmp_path)
    monkeypatch.setattr(ae, 'get_resource_path', lambda relative: str(tmp_path / relative))

    data = ae.get_stretched_indicator_box_data(None, [2], 2.0)

    assert data.params['w'] == pytest.approx(396.0)
    assert data.params['h'] == pytest.approx(445.0)
    assert data.metadata['baseline_filename'] == '盒子.dxf'

    circles = [p for p in data.scene.primitives if p.__class__.__name__ == 'CirclePrimitive']
    light_holes = [p for p in circles if p.radius == pytest.approx(15.5)]
    fixed_holes = [p for p in circles if p.radius == pytest.approx(4.0)]
    assert len(light_holes) == 6, '2 groups must create 6 current indicator holes, not retain stale baseline layout'
    assert len(fixed_holes) == 1, 'baseline-only fixed manufacturing hole must be preserved'


def test_indicator_box_api_exports_through_stretched_baseline_path(tmp_path, monkeypatch):
    baseline = _make_indicator_box_baseline(tmp_path)
    called = {}

    def fake_export(filepath, model_name, layer_groups, T_val=2.0, draw_stock=False, user_features=None, corner_policy=None):
        called.update(model_name=model_name, groups=tuple(layer_groups), t=T_val)
        Path(filepath).write_text('ok', encoding='utf-8')

    monkeypatch.setattr(ae, 'export_stretched_indicator_box_dxf', fake_export, raising=False)
    spec = IndicatorBoxPartSpec(layer_groups=(2,), thickness=2.0)
    result = manufacturing_api.generate_part(
        spec, tmp_path / 'out.dxf', ManufacturingContext(resource_root=tmp_path)
    )

    assert called == {'model_name': None, 'groups': (2,), 't': 2.0}
    assert result.used_baseline is True
    assert result.baseline_path == str(baseline)
    assert result.expected_baseline_path == str(baseline)


def test_indicator_box_api_real_export_contains_baseline_and_current_indicators(tmp_path):
    baseline = _make_indicator_box_baseline(tmp_path)
    spec = IndicatorBoxPartSpec(layer_groups=(2,), thickness=2.0)
    output = tmp_path / 'indicator_box_out.dxf'

    result = manufacturing_api.generate_part(
        spec, output, ManufacturingContext(resource_root=tmp_path)
    )

    doc = ezdxf.readfile(output)
    circles = list(doc.modelspace().query('CIRCLE'))
    light_holes = [e for e in circles if abs(float(e.dxf.radius) - 15.5) < 0.15]
    fixed_holes = [e for e in circles if abs(float(e.dxf.radius) - 4.0) < 0.15]
    assert len(light_holes) == 6
    assert len(fixed_holes) == 1
    assert result.used_baseline is True
    assert result.baseline_path == str(baseline)


def test_indicator_box_missing_required_baseline_is_explicit(tmp_path):
    spec = IndicatorBoxPartSpec(layer_groups=(2,), thickness=2.0)
    with pytest.raises(FileNotFoundError, match='shared_baseline_model'):
        manufacturing_api.generate_part(
            spec, tmp_path / 'out.dxf', ManufacturingContext(resource_root=tmp_path)
        )


def test_indicator_box_positional_feature_compatibility_is_preserved():
    marker = object()
    spec = IndicatorBoxPartSpec((2,), 2.0, (marker,))
    assert spec.features == (marker,)
    assert spec.model_name is None


def _gui_method_source(name):
    path = Path(__file__).parents[1] / 'gui.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'BoxCalculatorGUI')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method)


def test_gui_indicator_box_page_loads_baseline_plus_dynamic_layout():
    spec_source = _gui_method_source('_indicator_box_part_spec')
    context_source = _gui_method_source('_indicator_component_editor_contexts')
    assert 'model_name=None' in spec_source
    assert 'get_stretched_indicator_box_data' in context_source
    assert '盒子.dxf' in context_source
    assert 'box_baseline_scene = box_data.scene' in context_source
    assert '盒體（公式）' not in context_source
