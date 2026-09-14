import ast
import pathlib
import subprocess

PARENT = 'origin/refactor/issue208-layout-presentation-20260914'
NAME = '_phase6_logical_part_present'

parent = subprocess.check_output(
    ['git', 'show', f'{PARENT}:gui.py'], text=True, encoding='utf-8'
)
current = pathlib.Path('gui.py').read_text(encoding='utf-8')
module_source = pathlib.Path('gui_modules/part_panels.py').read_text(encoding='utf-8')


def find_class_method(source, class_name, method_name):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)


def find_top_function(source, name):
    tree = ast.parse(source)
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


parent_method = find_class_method(parent, 'BoxCalculatorGUI', NAME)
moved = find_top_function(module_source, NAME)

# Move-only semantic/source contract: same signature and body AST; decorator/class indentation are intentionally excluded.
if ast.dump(parent_method.args, include_attributes=False) != ast.dump(moved.args, include_attributes=False):
    raise SystemExit('projector signature changed during extraction')
if [ast.dump(n, include_attributes=False) for n in parent_method.body] != [ast.dump(n, include_attributes=False) for n in moved.body]:
    raise SystemExit('projector body changed during extraction')

current_tree = ast.parse(current)
current_cls = next(n for n in current_tree.body if isinstance(n, ast.ClassDef) and n.name == 'BoxCalculatorGUI')
if any(isinstance(n, ast.FunctionDef) and n.name == NAME for n in current_cls.body):
    raise SystemExit('old projector method body still exists in BoxCalculatorGUI')

binding_ok = False
for node in current_cls.body:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        continue
    target = node.targets[0]
    if not isinstance(target, ast.Name) or target.id != NAME:
        continue
    if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name) or node.value.func.id != 'staticmethod':
        continue
    if len(node.value.args) == 1 and isinstance(node.value.args[0], ast.Name) and node.value.args[0].id == '_phase6_logical_part_present_impl':
        binding_ok = True
if not binding_ok:
    raise SystemExit('BoxCalculatorGUI static compatibility binding missing')

expected_import = 'from gui_modules.part_panels import (\n    _phase6_logical_part_present as _phase6_logical_part_present_impl,\n)'
if current.count(expected_import) != 1:
    raise SystemExit('part_panels compatibility import is not exactly one canonical import')

for path in pathlib.Path('gui_modules').rglob('*.py'):
    text = path.read_text(encoding='utf-8')
    if 'import gui' in text or 'from gui import' in text:
        raise SystemExit(f'forbidden gui_modules -> gui import: {path}')

print('t5_first_slice_source_contract=GREEN')
print('t5_first_slice_compatibility=GREEN')
print('import_direction=GREEN')
