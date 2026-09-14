import ast
import pathlib
import subprocess

PARENT = 'origin/refactor/issue207-pure-drawing-move-20260914'
NAME = '_project_toolbar_presentation'

parent = subprocess.check_output(
    ['git', 'show', f'{PARENT}:gui.py'], text=True, encoding='utf-8'
)
current = pathlib.Path('gui.py').read_text(encoding='utf-8')
layout = pathlib.Path('gui_modules/layout.py').read_text(encoding='utf-8')


def func_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node)


expected = func_segment(parent, NAME)
moved = func_segment(layout, NAME)
if expected != moved:
    raise SystemExit('moved toolbar presentation source differs from accepted T3 parent')

current_tree = ast.parse(current)
if any(
    isinstance(item, ast.FunctionDef) and item.name == NAME
    for item in current_tree.body
):
    raise SystemExit('toolbar presentation body still exists in gui.py')

compat = 'from gui_modules.layout import _project_toolbar_presentation'
if current.count(compat) != 1:
    raise SystemExit(f'compatibility import count != 1: {current.count(compat)}')

for module_path in pathlib.Path('gui_modules').rglob('*.py'):
    text = module_path.read_text(encoding='utf-8')
    if 'import gui' in text or 'from gui import' in text:
        raise SystemExit(f'forbidden gui_modules -> gui import: {module_path}')

changed = subprocess.check_output(
    ['git', 'diff', '--name-only', f'{PARENT}...HEAD'],
    text=True,
    encoding='utf-8',
).splitlines()
allowed_production = {'gui.py', 'gui_modules/layout.py'}
for path in changed:
    if path.startswith('.scratch/issue208'):
        continue
    if path == 'docs/superpowers/plans/2026-09-14-gui-layout-presentation-move.md':
        continue
    if path in {
        '.github/workflows/issue208-t4-preflight.yml',
        '.github/workflows/issue208-t4-apply-move.yml',
    }:
        continue
    if path not in allowed_production:
        raise SystemExit(f'unexpected T4 diff: {path}')

print('move_only_source_contract=GREEN')
print('import_direction=GREEN')
print('allowed_diff=GREEN')
