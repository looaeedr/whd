# 2026-08-30 Phase6 GUI / 3D 完整性最終驗證

## 範圍

本輪針對操作員實際回報的 GUI / 2D / 3D 同步缺陷進行資料鏈收尾，不另建第二套製造公式：

- 切換「受電箱」後，可見結構列與 canonical Family state 同步固定為「三件式（側背分離）」。
- 封頭／封尾切換 OVERLAY 後，workspace 與 active editor 的 X profile 同步替換為 flat-X，不殘留單邊或 stale X BEND。
- 二件式、三件式箱身逐 physical piece 顯示 canonical 展開尺寸；操作員畫面不顯示淨面積與 raw English part ID。
- 單板 3D 與組合 3D 圖面本身直接顯示同一份 canonical 展開尺寸文字。
- 組合板件區使用可捲動 Canvas + 垂直捲軸，滑鼠位於內容列時可滾動。
- 截角資料庫／Joint 操作介面以繁中 label 顯示；stable rule ID / enum / formula token 僅保留於資料層。
- 主 2D 預覽保留獨立上方標註帶與右側尺寸通道；文字不得互相重疊，也不得覆蓋材料。
- pre-solve collision evidence 保持預設開啟；post-solve 仍要求零非法穿透。

## 新增契約測試

`tests/test_phase6_gui_3d_integrity_20260830.py` 鎖定：

1. 多片展開料逐片顯示、無淨面積／raw ID。
2. Registry / Joint token 的操作員繁中映射。
3. 動態切換受電箱後 Family state 與可見結構同步。
4. OVERLAY live rebuild 同步 active editor + workspace flat-X。
5. 組合板件區 scrollbar / mouse wheel 契約。
6. 共用 2D viewport 保留標註與尺寸 lane。
7. 單板／組合 3D 接收 canonical 展開料文字並直接畫在 3D 圖面。
8. Registry form 不向操作員露出 stable English rule ID / evaluator token。
9. 真 Tk 箱身 2D Canvas bbox：說明、截角尺寸、開孔提示彼此不重疊且不覆蓋材料。

## Fresh 驗證證據

開發工作樹在本輪程式修正完成後已取得以下 fresh 結果：

- GUI / 3D 完整性新增契約：9 passed（其中真 Canvas bbox 亦通過）。
- 二／三件式箱身結構：20 headless passed；真 Tk 分件案例逐項通過。
- OVERLAY formed-FW / flat-X / post-solve zero penetration：3 passed；Registry GUI matrix INSERT / OVERLAY / INSERT_OVERLAY：3 passed。
- Certified Registry / Collision / WRAP / Assembly Intent 核心矩陣：137 passed。
- FinalScene / 3D cutting / dimensions：71 headless passed；2 個真 Tk 案例另行 fresh 通過。
- ProjectSession / Tail / diagnostics：17 passed。
- `.p6fold` Project Save→Reload：9 passed + 10 passed，合計 19 passed。
- 實際 OVERLAY 3D 視覺 gate：Head/Tail X profile 僅 `endcap_w_flat`；Registry 命中 `ENDCAP_TOP_OVERLAY_STANDARD_V1@2`；Head/Tail post-solve residual=0；pre-solve collision probe 與紅色干涉顯示存在。

## Baseline / 環境分離

- 部分 Tk / Matplotlib 測試若未掛 DISPLAY 或未註冊 `Axes3D` 會在測試環境先失敗；相同案例已用 Xvfb / 正常 3D projection 路徑分離重跑，不把環境失敗當程式成功或失敗。
- 既存 ytop1 committed-relief 舊測試已對照 20260830_025948 原包，原包本來即失敗，不列為本輪 regression。
- 舊 UI 測試若仍要求顯示「淨面積」，與本輪正式操作契約衝突，已以新契約取代；production 不恢復淨面積顯示。

## 最終 Release Gate

正式交付必須再由 release staging 完成：

1. FULL 使用 canonical `config.ini`；UPDATE 禁止包含 `config.ini`。
2. UPDATE baseline 固定為 `PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355(3).zip`。
3. FULL / UPDATE 共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳。
4. ZIP CRC、檔案集合與逐檔 SHA256 對來源一致。
5. UPDATE 疊到 canonical baseline 並執行 cleanup 後，必須與 FULL 得到 0 missing / 0 extra / 0 SHA mismatch。
6. freshly extracted FULL 必須再跑 GUI/Registry/OVERLAY/結構/3D/Save-Reload responsibility gate。

未完成上述 6 項前，不得宣稱正式交付完成。

## 正式封包第一輪 Fresh-Extract Gate（20260830_131634）

第一輪正式 FULL / UPDATE 建立後，已從 freshly extracted FULL 與 canonical baseline + UPDATE overlay 實際驗證：

- Python compile：304 files，0 error。
- Release / Skill policy：17 passed。
- FULL：743 packaged files；UPDATE：460 cumulative files；UPDATE 不含 `config.ini`。
- FULL / UPDATE ZIP CRC：PASS。
- FULL `config.ini` 與 UPDATE-overlay `config.ini` SHA256 均為 `5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`。
- UPDATE cleanup 實際移除 canonical baseline 舊 `skills/`；`.agents/skills/` 保留。
- UPDATE overlay production parity（依 `excluded_update_roots=[BACKUP]` 政策）：563 vs 563，0 missing / 0 extra / 0 SHA mismatch。
- FULL 比 production overlay 多出的 180 檔全部只位於 `BACKUP` / `BACKUP_*` 歷史備份目錄；這些目錄依 release policy 明確只屬 FULL，不進 UPDATE，沒有 production payload 差異。
- Registry / Collision / WRAP / Assembly Intent fresh FULL 核心責任 gate：118 passed。
- GUI / 3D 完整性：9 passed。
- Registry GUI matrix：3 passed；OVERLAY formed-FW / flat-X / zero penetration：3 passed。
- 箱身結構：20 headless passed + 5 real Tk passed。
- 3D renderer / FinalScene / cutting / dimensions：81 headless passed + 3 real Tk passed。
- 另修正 `tests/test_phase6_3d_single_source_renderer.py` 無 DISPLAY skip 分支缺少 `import pytest` 的測試 harness 缺陷；修正後同一 3D 批次為 81 passed / 3 skipped，三個 GUI 案例在 Xvfb 逐一通過。
- `.p6fold` Save→Reload / Project file：9 passed + 10 passed = 19 passed。

GUI 測試在 Xvfb 下若 assertion 已完成但 Matplotlib / Tk 非 daemon teardown 資源不退出，最終 gate 以 `pytest.main()` 的正式 return code 為準後立即結束 harness；assertion failure 仍會原樣回傳非零，不把 teardown hang 當通過。

以上證據回寫後，FULL / UPDATE 必須使用同一 `20260830_131634` 時間戳重封，並再次做 CRC / SHA / overlay parity 與 final freshly-extracted smoke，才是最終交付包。
