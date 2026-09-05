# 05 — Next Steps

## 已完成
- `ae.py` direct exporters 已變成 parameter adaptation → `_build_*_scene()` → `_save_scene_dxf()`。
- stretched exporters 使用同一 save path；stretched box 最終委派公式化 BoxBody exporter。
- `export_part_dxf(part_type, filepath, **kwargs)` 已成為 canonical dispatcher。
- `tail` dispatcher 會自動加入 `is_tail=True`。
- fresh verification：97/97 PASS。

## 下一個真正階段：第二箱型
目前不要再為金庫型繼續抽象。拿到第二種箱型的實際 DXF / 1.csv / 製造規則後：
1. 先辨識是否可重用 FourSideFlange / StripFoldChain。
2. 再判斷現有 Factory Policy 是否可重用。
3. 只有新的物理干涉、裝配關係或 topology 才新增 Rule/Policy。
4. 禁止直接複製 Vault 的 0.5T / 2T clearance。
5. 新箱型先新增 regression baseline，再開始實作。
