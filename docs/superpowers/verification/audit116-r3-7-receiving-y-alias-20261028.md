---
whd_doc_role: CURRENT
whd_contract: audit116-r3-7-receiving-alias-upper-inner-door-y
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 原始 116 項 #39（R3-7）受電箱別名與內門 Y 投影補驗

**施工權威**：GitHub `looaeedr/whd` `localX@195ea7726cc8a7a81036d581c6cc4d447216dd00`。
**改動界線**：僅增測試，不能重寫內門座標或更動既有 1／2 層規格；正式 `X` 無當次 `/推推` 不得發布。

## SOURCE_READ_EVIDENCE 與明確缺口

- 已讀 `AGENTS.md`、`tests/test_deep_audit_round3_bugfixes.py::test_r3_7_receiving_alias_accepted_across_navigation_and_projection`，發現函式名稱及 docstring 宣稱三條路徑，但斷言僅直接呼叫 `operator_part_label` 與 `fixed_corner_summary`，**未呼叫實際 `_inner_door_y_basis`／`project_nfb_inner_door_nominal_y`**。
- 已讀 `phase6_part_navigation.operator_part_label`、`gui_modules/parts/panels/assembly_corner.fixed_corner_summary`、`ae_engine.receiving_nfb_y_projection._inner_door_y_basis/project_nfb_inner_door_nominal_y/invert_nfb_inner_door_unfolded_y` 及 `tests/test_issue1495_receiving_nfb_y_projection.py::receiving_snapshot`；最新 base 對舊 `8380c1ac` 演進 8 commits 並未更動上述來源。
- 原 Windows `AUDIT116_POSTMERGE_838_WINDOWS_REGRESSION.xml` 450/450 PASS，但 `test_r3_7_receiving_alias_accepted_across_navigation_and_projection` 約 0.002 秒的 PASS **不構成第三條內門 Y 路徑被驗收**。
- 上層受電箱物理權威：W800／H1600／D350、T2、上門 1100＋下門 500、內門 `upper`、單層 Y550 或雙層 Y290／Y790，自頂面投影至有識別碼的實際內門板件。

## 新增可驗證斷言

新測試 `test_r3_7_receiving_alias_preserves_real_upper_inner_door_y_projection` 以 `apply_family_defaults` 建立實體資料後，僅將 `model` 改為 `RECEIVING`，與 `受電箱` 比對單層 1 點及雙層 2 點的完整投影結果；重點包括板件 `inner_door:upper:panel`、cell `0:0`、世界座標、成型內面／展開 UV、反算回箱頂 Y，以及不修改輸入 Snapshot。錯誤家族 `金庫型` 必須 fail closed。

## 閘門與簽核邊界

必須以精確 PR HEAD 的 **Product Regression 五個必要工作全部綠燈**，再回讀提交與 GitHub `localX`，才能說已交付這段新增自動化保護。它仍屬 **GEOMETRY_ONLY_NOT_NFB_CUTTING_CERTIFIED**，沒有證明現場 GUI、實際 NFB 開孔 DXF、CADCraft 或工廠 NC；116 項真實人工簽核不能因此增加。

若獨立 Y 正反算測試 RED，先查明 current family alias 的實際物理 Owner，於相同專屬分支最小修復，不可修改 golden 值或刪除失敗斷言湊綠燈。
