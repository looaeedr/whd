from pathlib import Path

path = Path('gui.py')
text = path.read_text(encoding='utf-8')

old = '''    @staticmethod
    def _phase6_logical_part_present(existing_parts, logical_key):
        """Project dynamic physical stable IDs into the legacy top-level UI groups.

        The physical IDs remain authoritative; this helper only answers whether a
        logical main-GUI group should be visible.
        """
        existing = set(str(key) for key in (existing_parts or ()))
        key = str(logical_key or "")
        if key == "door":
            return "door" in existing or any(item.startswith("door_c") for item in existing)
        if key == "base_plate":
            return "base_plate" in existing or any(item.startswith("base_plate_c") for item in existing)
        if key == "box_body":
            return "box_body" in existing or any(item.startswith("box_body:") for item in existing)
        return key in existing

'''

anchor = 'from gui_modules.layout import _project_toolbar_presentation\n\n\n'
compat_import = (
    anchor
    + 'from gui_modules.part_panels import (\n'
    + '    _phase6_logical_part_present as _phase6_logical_part_present_impl,\n'
    + ')\n\n\n'
)
replacement = '    _phase6_logical_part_present = staticmethod(_phase6_logical_part_present_impl)\n\n'

if text.count(old) != 1:
    raise SystemExit(f'expected exactly one logical-part method body, got {text.count(old)}')
if text.count(anchor) != 1:
    raise SystemExit(f'expected exactly one layout import anchor, got {text.count(anchor)}')
if '_phase6_logical_part_present_impl' in text:
    raise SystemExit('compatibility import/binding already exists')

text = text.replace(anchor, compat_import, 1)
text = text.replace(old, replacement, 1)
path.write_text(text, encoding='utf-8')
