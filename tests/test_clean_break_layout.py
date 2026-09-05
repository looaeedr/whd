from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
OLD_ROOT_SHIMS = (
    'ae.py', 'contracts.py', 'manufacturing_api.py', 'sheetmetal_geometry.py',
    'sheetmetal_features.py', 'sheetmetal_part_adapters.py', 'sheetmetal_drawing.py',
    'hole_catalog.py',
)
OLD_ROOT_MODULES = {
    'ae', 'contracts', 'manufacturing_api', 'sheetmetal_geometry', 'sheetmetal_features',
    'sheetmetal_part_adapters', 'sheetmetal_drawing', 'hole_catalog',
}

def _old_imports(path: Path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    found=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name in OLD_ROOT_MODULES]
        elif isinstance(node, ast.ImportFrom) and (node.module or '') in OLD_ROOT_MODULES:
            found.append(node.module)
    return found

def test_ae_project_has_only_ae_engine_core():
    assert all(not (ROOT / name).exists() for name in OLD_ROOT_SHIMS)
    assert (ROOT / 'ae_engine' / 'ae.py').is_file()

def test_ae_python_sources_do_not_use_root_compatibility_imports():
    # BACKUP/ 和 tmp/ 是存檔目錄，不在掃描範圍內
    EXCLUDED_DIRS = {'BACKUP', 'tmp'}
    offenders=[]
    for path in ROOT.rglob('*.py'):
        if 'ae_engine' in path.parts:
            continue
        if any(part in EXCLUDED_DIRS or part.startswith('BACKUP') for part in path.parts):
            continue
        if _old_imports(path): offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_ae_engine_uses_package_relative_core_imports_only():
    import ast
    old = {
        "ae", "contracts", "manufacturing_api", "sheetmetal_geometry",
        "sheetmetal_features", "sheetmetal_part_adapters", "sheetmetal_drawing", "hole_catalog",
    }
    offenders = []
    for path in (ROOT / "ae_engine").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in old:
                        offenders.append((str(path.relative_to(ROOT)), node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "") in old:
                offenders.append((str(path.relative_to(ROOT)), node.lineno, node.module))
    assert offenders == []
