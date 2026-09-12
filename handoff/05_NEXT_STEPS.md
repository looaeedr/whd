<!-- WHD_DOC_ROLE role=HISTORICAL contract=roadmap-snapshot -->
> **[roadmap snapshot]** 此檔保留當時 evidence / roadmap / API 盤點；**不參與 current routing**，不得以檔名中的 `CURRENT`、`目前`、`Next Steps` 或舊架構語氣覆蓋現行 authority。
> Current authority：`個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`；製造架構/API：`個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`。

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
