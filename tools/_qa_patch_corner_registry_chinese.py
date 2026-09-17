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

# Registry values loaded by the Receiving divider rule are valid internal
# tokens.  Localize only their operator projection.
operator_anchor = '    "HEAD_OR_TAIL": "封頭／封尾",'
operator_rows = (
    '    "DIVIDER": "中隔",',
    '    "ENDS": "封頭／封尾",',
    '    "receiving_divider_four_segment": "受電箱中隔四段式",',
    '    "cross_slot_min_y": "十字槽最小縱向",',
)
missing_operator_rows = [row for row in operator_rows if row not in text]
if missing_operator_rows:
    if text.count(operator_anchor) != 1:
        raise SystemExit('operator-label insertion anchor missing or ambiguous')
    text = text.replace(
        operator_anchor,
        operator_anchor + '\n' + '\n'.join(missing_operator_rows),
        1,
    )

# The branch already owns a Chinese label for this stable rule id.  Accept it;
# never add a duplicate dict key just to satisfy QA.
divider_marker = '"RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字截角（標準）"'
if divider_marker not in text:
    raise SystemExit('existing Chinese divider rule projection is missing')

source_block_new = '''_PHASE6_SOURCE_DISPLAY_TOKENS = {
    "CornerType": "截角類型",
    "linked-FW": "連動框寬",
    "STANDARD": "標準",
    "manufacturing": "製造",
    "contract": "契約",
    "projection": "投影",
    "Registry": "資料庫",
    "formed": "成形",
    "shadow": "陰影",
    "evidence": "證據",
    "CROSS": "十字",
    "C04": "型號04",
    "X/Y": "橫向／縱向",
    "1T": "1板厚",
    ".dxf": "圖檔",
    "band": "帶區",
    "base": "基底",
    "face": "面",
    "HIT": "命中",
    "mm": "毫米",
    "3D": "立體",
    "2D": "平面",
}


def _phase6_source_display(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(raw, label)
    text = _phase6_operator_text(text)
    text = _phase6_formula_display(text)
    return text


def _phase6_source_raw(value):
    text = str(value or "")
    # Reverse source-specific phrases first so compound labels are not partially
    # consumed by the generic formula aliases.
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(label, raw)
    reverse_operator = sorted(
        ((label, raw) for raw, label in _PHASE6_OPERATOR_LABELS.items()),
        key=lambda item: len(item[0]), reverse=True,
    )
    for label, raw in reverse_operator:
        text = text.replace(label, raw)
    reverse_parts = sorted(
        ((label, raw) for raw, label in PART_LABELS.items()),
        key=lambda item: len(item[0]), reverse=True,
    )
    for label, raw in reverse_parts:
        text = text.replace(label, raw)
    return _phase6_formula_raw(text)
'''

if '_PHASE6_SOURCE_DISPLAY_TOKENS =' in text:
    start = text.index('_PHASE6_SOURCE_DISPLAY_TOKENS =')
    end_marker = '\n\ndef _phase6_bind_translated_var(raw_var, display_var, to_display, to_raw):'
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit('existing source-display block has no translated-var boundary')
    text = text[:start] + source_block_new + text[end:]
else:
    marker = 'def _phase6_bind_translated_var(raw_var, display_var, to_display, to_raw):'
    if text.count(marker) != 1:
        raise SystemExit('translated-var authority marker missing or ambiguous')
    text = text.replace(marker, source_block_new + '\n\n' + marker, 1)

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
    divider_marker,
    'entry("第一級橫向公式", self.relief_registry_primary_u_display_var)',
    '("預覽立體組合",lambda:_phase6_registry_preview_assembly_3d(self))',
    '"CornerType": "截角類型"',
    '"DIVIDER": "中隔"',
    '"receiving_divider_four_segment": "受電箱中隔四段式"',
    'text = _phase6_operator_text(text)',
    'text = _phase6_formula_display(text)',
)
missing = [marker for marker in required_markers if marker not in text]
if missing:
    raise SystemExit(f'expected Chinese presentation markers missing: {missing!r}')

p.write_text(text, encoding='utf-8')
print('patched', p)
