from pathlib import Path
import json
import pytest

from tools.phase6_release import load_mandatory_update_files, collect_update_paths


def test_registry_gate_files_are_mandatory_update_artifacts():
    root = Path(__file__).resolve().parents[1]
    required = load_mandatory_update_files(root)
    assert 'tests/test_phase6_assembly_intent_registry_matrix.py' in required
    assert 'tests/test_phase6_assembly_registry_gui_matrix.py' in required
    for rel in required:
        assert (root / rel).is_file(), rel


def test_unchanged_mandatory_gate_files_are_still_in_update(tmp_path):
    source = tmp_path / 'source'
    baseline = tmp_path / 'baseline'
    source.mkdir()
    baseline.mkdir()
    required = [
        'tests/test_phase6_assembly_intent_registry_matrix.py',
        'tests/test_phase6_assembly_registry_gui_matrix.py',
    ]
    for rel in required:
        (source / rel).parent.mkdir(parents=True, exist_ok=True)
        (baseline / rel).parent.mkdir(parents=True, exist_ok=True)
        (source / rel).write_text('same', encoding='utf-8')
        (baseline / rel).write_text('same', encoding='utf-8')
    (source / '修改日誌').mkdir()
    (baseline / '修改日誌').mkdir()
    (source / '修改日誌/20260829.md').write_text('new log', encoding='utf-8')
    (baseline / '修改日誌/20260829.md').write_text('old log', encoding='utf-8')

    paths = collect_update_paths(source, baseline, required)
    assert set(required).issubset(paths)
    assert '修改日誌/20260829.md' in paths


def test_missing_mandatory_gate_file_blocks_update(tmp_path):
    source = tmp_path / 'source'
    baseline = tmp_path / 'baseline'
    source.mkdir()
    baseline.mkdir()
    with pytest.raises(FileNotFoundError, match='mandatory update artifact'):
        collect_update_paths(source, baseline, ['tests/missing_gate.py'])


def test_write_update_zip_uses_collector_and_contains_mandatory(tmp_path):
    import zipfile
    from tools.phase6_release import write_update_zip

    source = tmp_path / 'source'
    baseline = tmp_path / 'baseline'
    source.mkdir()
    baseline.mkdir()
    required = [
        'tests/test_phase6_assembly_intent_registry_matrix.py',
        'tests/test_phase6_assembly_registry_gui_matrix.py',
    ]
    for rel in required:
        (source / rel).parent.mkdir(parents=True, exist_ok=True)
        (baseline / rel).parent.mkdir(parents=True, exist_ok=True)
        (source / rel).write_text('same', encoding='utf-8')
        (baseline / rel).write_text('same', encoding='utf-8')
    (source / 'changed.py').write_text('new', encoding='utf-8')
    (baseline / 'changed.py').write_text('old', encoding='utf-8')

    out = tmp_path / 'update.zip'
    paths = write_update_zip(source, baseline, out, required)
    assert out.is_file()
    assert set(required).issubset(paths)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert set(required).issubset(names)
    assert 'changed.py' in names
