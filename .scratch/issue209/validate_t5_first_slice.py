import ast
import pathlib
import subprocess

PARENT_SHA = 'a098498d7459e974bbf18a5573e6b209eaeb4404'
OWNER = 'Phase6ApplicationHost'
NAME = '_phase6_logical_part_present'

parent = subprocess.check_output(
    ['git', 'show', f'{PARENT_SHA}:gui.py'], text=True, encoding='utf-8'
)
current = pathlib.Path('gui.py').read_text(encoding='utf-8')
module_source = pathlib.Path('gui_modules/part_panels.py').read_text(encoding='utf-8')


def find_class(source, class_name):
    tree = ast.parse(source)
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)


def find_class_method(source, class_name, method_name):
    cls = find_class(source, class_name)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)


def find_top_function(source, name):
    tree = ast.parse(source)
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


parent_method = find_class_method(parent, OWNER, NAME)
moved = find_top_function(module_source, NAME)

parent_args = ast.dump(parent_method.args, include_attributes=False)
moved_args = ast.dump(moved.args, include_attributes=False)
if parent_args != moved_args:
    print('PARENT_ARGS', parent_args)
    print('MOVED_ARGS', moved_args)
    raise SystemExit('projector signature changed during extraction')

parent_body = [ast.dump(n, include_attributes=False) for n in parent_method.body]
moved_body = [ast.dump(n, include_attributes=False) for n in moved.body]
if parent_body != moved_body:
    print('PARENT_BODY')
    for row in parent_body:
        print(row)
    print('MOVED_BODY')
    for row in moved_body:
        print(row)
    raise SystemExit('projector body changed during extraction')

current_owner = find_class(current, OWNER)
if any(isinstance(n, ast.FunctionDef) and n.name == NAME for n in current_owner.body):
    raise SystemExit(f'old projector method body still exists in {OWNER}')

binding_ok = False
for node in current_owner.body:
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
    raise SystemExit(f'{OWNER} static compatibility binding missing')

expected_import = 'from gui_modules.part_panels import (\n    _phase6_logical_part_present as _phase6_logical_part_present_impl,\n)'
if current.count(expected_import) != 1:
    raise SystemExit('part_panels compatibility import is not exactly one canonical import')

box_cls = find_class(current, 'BoxCalculatorGUI')
if not any(isinstance(base, ast.Name) and base.id == OWNER for base in box_cls.bases):
    raise SystemExit('BoxCalculatorGUI no longer inherits Phase6ApplicationHost')

for path in pathlib.Path('gui_modules').rglob('*.py'):
    text = path.read_text(encoding='utf-8')
    if 'import gui' in text or 'from gui import' in text:
        raise SystemExit(f'forbidden gui_modules -> gui import: {path}')

print(f'accepted_parent={PARENT_SHA}')
print(f'owner={OWNER}')
print('t5_first_slice_source_contract=GREEN')
print('t5_first_slice_compatibility=GREEN')
print('import_direction=GREEN')
