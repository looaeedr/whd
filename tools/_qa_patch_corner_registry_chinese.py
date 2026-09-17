from pathlib import Path

p = Path('fold_designer_bridge.py')
text = p.read_text(encoding='utf-8')


def ensure_replace(old: str, new: str) -> None:
    global text
    if old not in text:
        if new in text:
            return
        raise SystemExit(f'neither old nor accepted new form found: {old!r}')
    if text.count(old) != 1:
        raise SystemExit(f'expected exactly one old match: {old!r}')
    text = text.replace(old, new, 1)


for old, new in (
    ('"reserve_u": "X預留",', '"reserve_u": "橫向預留",'),
    ('"reserve_v": "Y預留",', '"reserve_v": "縱向預留",'),
    ('"fold_u": "X向折邊",', '"fold_u": "橫向折邊",'),
    ('"fold_v": "Y向折邊",', '"fold_v": "縱向折邊",'),
):
    ensure_replace(old, new)

if '"RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字標準"' not in text:
    old = '    "RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",'
    new = old + '\n    "RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字標準",'
    ensure_replace(old, new)

if '_PHASE6_SOURCE_DISPLAY_TOKENS =' not in text:
    marker = 'def _phase6_bind_translated_var(raw_var, display_var, to_display, to_raw):'
    if text.count(marker) != 1:
        raise SystemExit('translated-var authority marker missing or ambiguous')
    source_projection = '''_PHASE6_SOURCE_DISPLAY_TOKENS = {
    "linked-FW": "連動框寬",
    "FW": "框寬",
    "3D": "立體",
    "2D": "平面",
}


def _phase6_source_display(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(raw, label)
    return text


def _phase6_source_raw(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(label, raw)
    return text


'''
    text = text.replace(marker, source_projection + marker, 1)

if 'self.relief_registry_source_display_var' not in text:
    old = '    entry("公式來源／備註", self.relief_registry_source_var)'
    new = '''    self.relief_registry_source_display_var = original.tk.StringVar(master=form)
    _phase6_bind_translated_var(
        self.relief_registry_source_var, self.relief_registry_source_display_var,
        _phase6_source_display, _phase6_source_raw,
    )
    entry("公式來源／備註", self.relief_registry_source_display_var)'''
    if text.count(old) != 1:
        raise SystemExit('source presentation field marker missing or ambiguous')
    text = text.replace(old, new, 1)

required_markers = (
    'win.title("截角資料庫／組合接合")',
    '"CERTIFIED_FROM_3D": "立體驗證認證"',
    '"RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字標準"',
    'entry("第一級橫向公式", self.relief_registry_primary_u_display_var)',
    '("預覽立體組合",lambda:_phase6_registry_preview_assembly_3d(self))',
)
missing = [marker for marker in required_markers if marker not in text]
if missing:
    raise SystemExit(f'expected Chinese presentation markers missing: {missing!r}')

p.write_text(text, encoding='utf-8')
print('patched', p)
