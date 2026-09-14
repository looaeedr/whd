from pathlib import Path
import textwrap

GUI = Path('gui.py')
MODULE = Path('gui_modules/project_actions.py')

IMPORT_ANCHOR = '''from gui_modules.part_panels import (\n    _phase6_logical_part_present as _phase6_logical_part_present_impl,\n)\n'''
IMPORT_BLOCK = '''from gui_modules.project_actions import (\n    save_phase6_project_as as _save_phase6_project_as_impl,\n    save_phase6_project as _save_phase6_project_impl,\n    open_phase6_project as _open_phase6_project_impl,\n    load_phase6_project as _load_phase6_project_impl,\n)\n'''
START = '    def save_phase6_project_as(self, *, _active_part_hint=None):\n'
END = '    def _apply_original_fold_designer_snapshot(self, snapshot):\n'
ALIASES = '''    save_phase6_project_as = _save_phase6_project_as_impl\n    save_phase6_project = _save_phase6_project_impl\n    open_phase6_project = _open_phase6_project_impl\n    load_phase6_project = _load_phase6_project_impl\n\n'''
MODULE_HEADER = '''\"\"\"Global Phase6 project-file action wrappers.\n\nThese functions are methods by descriptor binding when assigned on\nPhase6ApplicationHost. They do not own project state, schema, persistence\nordering, or ProjectSession; those remain in Phase6ProjectController and the\nexisting application orchestrator.\n\"\"\"\n\nfrom pathlib import Path\nfrom tkinter import filedialog, messagebox\n\nfrom phase6_project_file import PROJECT_EXTENSION as PHASE6_PROJECT_EXTENSION\n\n\n'''

source = GUI.read_text(encoding='utf-8')

already_imported = IMPORT_BLOCK in source
already_aliased = all(line in source for line in (
    '    save_phase6_project_as = _save_phase6_project_as_impl',
    '    save_phase6_project = _save_phase6_project_impl',
    '    open_phase6_project = _open_phase6_project_impl',
    '    load_phase6_project = _load_phase6_project_impl',
))

if MODULE.exists() or already_imported or already_aliased:
    if not (MODULE.exists() and already_imported and already_aliased):
        raise SystemExit('partial T6 Move-Only state detected; fail closed')
    module_source = MODULE.read_text(encoding='utf-8')
    for name in ('save_phase6_project_as', 'save_phase6_project', 'open_phase6_project', 'load_phase6_project'):
        if f'def {name}(' not in module_source:
            raise SystemExit(f'partial project_actions module: missing {name}')
    print('IDEMPOTENT: Move-Only extraction already applied')
    raise SystemExit(0)

if IMPORT_ANCHOR not in source:
    raise SystemExit('part_panels import anchor missing; gui.py drifted')
if START not in source or END not in source:
    raise SystemExit('project-action method boundary missing; gui.py drifted')

start = source.index(START)
end = source.index(END, start)
method_block = source[start:end]
module_functions = textwrap.dedent(method_block).rstrip() + '\n'

MODULE.parent.mkdir(parents=True, exist_ok=True)
MODULE.write_text(MODULE_HEADER + module_functions, encoding='utf-8')

source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + '\n\n' + IMPORT_BLOCK, 1)
source = source[:start] + ALIASES + source[end:]
GUI.write_text(source, encoding='utf-8')

print('APPLIED: moved save/open/load wrappers only')
print('HOLD: snapshot composition, loaded path property, apply snapshot, controller/session/schema')
