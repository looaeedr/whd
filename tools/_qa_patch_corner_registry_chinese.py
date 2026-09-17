from pathlib import Path

p = Path('fold_designer_bridge.py')
text = p.read_text(encoding='utf-8')

replacements = [
    ('"CERTIFIED_FROM_3D": "3D 驗證認證",', '"CERTIFIED_FROM_3D": "立體驗證認證",'),
    ('"PROVISIONAL_3D": "3D 暫定",', '"PROVISIONAL_3D": "立體暫定",'),
    ('"RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",', '"RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",\n    "RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字標準",'),
    ('"ytop1_present": "有上折",\n    "ytop1_absent": "無獨立上折",\n    "ybottom1_present": "有下折",\n    "x_folded": "X向有折",\n    "x_flat": "X向平板",', '"ytop1_present": "有上折",\n    "ytop1_absent": "無獨立上折",\n    "ybottom1_present": "有下折",\n    "x_folded": "橫向有折",\n    "x_flat": "橫向平板",\n    "top_edge": "上側邊",\n    "bottom_edge": "下側邊",\n    "left_edge": "左側邊",\n    "right_edge": "右側邊",\n    "top_mating_zone": "上側接合區",\n    "bottom_mating_zone": "下側接合區",\n    "left_mating_zone": "左側接合區",\n    "right_mating_zone": "右側接合區",'),
    ('"reserve_u": "X預留",', '"reserve_u": "橫向預留",'),
    ('"reserve_v": "Y預留",', '"reserve_v": "縱向預留",'),
    ('"fold_u": "X向折邊",', '"fold_u": "橫向折邊",'),
    ('"fold_v": "Y向折邊",', '"fold_v": "縱向折邊",'),
    ('win.title("PHASE6 截角資料庫 / 組合接合")', 'win.title("截角資料庫／組合接合")'),
    ('entry("第一級 X 公式", self.relief_registry_primary_u_display_var)', 'entry("第一級橫向公式", self.relief_registry_primary_u_display_var)'),
    ('entry("第一級 Y 公式", self.relief_registry_primary_v_display_var)', 'entry("第一級縱向公式", self.relief_registry_primary_v_display_var)'),
    ('entry("第二級 X 公式", self.relief_registry_secondary_u_display_var)', 'entry("第二級橫向公式", self.relief_registry_secondary_u_display_var)'),
    ('"側折：封頭／封尾 X 向側邊折彎基底；貼外沒有 X 折時為 0。",', '"側折：封頭／封尾橫向側邊折彎基底；貼外沒有橫向折彎時為 0。",'),
    ('"上折：封頭／封尾 Y 向第一折尺寸。",', '"上折：封頭／封尾縱向第一折尺寸。",'),
    ('"第一級 X/Y：主要截角的 X/Y 切除量；第二級 X/深度：二級截角的內側位置與深度。",', '"第一級橫向／縱向：主要截角的橫向／縱向切除量；第二級橫向／深度：二級截角的內側位置與深度。",'),
    ('("預覽2D",lambda:_phase6_registry_preview_2d(self)),', '("預覽平面",lambda:_phase6_registry_preview_2d(self)),'),
    ('("預覽組合3D",lambda:_phase6_registry_preview_assembly_3d(self)),', '("預覽立體組合",lambda:_phase6_registry_preview_assembly_3d(self)),'),
    ('f"公式矩陣通過：{len(samples)} cases；3D零穿透="', 'f"公式矩陣通過：{len(samples)} 組；立體零穿透="'),
    ('"候選專屬組合3D驗證："', '"候選專屬立體組合驗證："'),
    ('f"組合3D驗證失敗：{exc}"', 'f"立體組合驗證失敗：{exc}"'),
    ('raise ValueError("只有 USER_ADDED Joint 可以刪除")', 'raise ValueError("只有使用者新增的接合規則可以刪除")'),
    ('raise ValueError("相同 AssemblyJoint 已存在")', 'raise ValueError("相同接合規則已存在")'),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one match, got {count}: {old!r}')
    text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
print('patched', p)
