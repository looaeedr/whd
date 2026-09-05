# Phase6 全域專案操作＋CornerType 參數鎖驗證 — 2026-08-23

## 驗證範圍

1. 主視窗左上角提供 `開啟專案 / 儲存專案 / 另存新檔`。
2. 3D Footer 不承擔 `.p6fold` 專案讀／存；3D 視窗左上角另有全域 `開啟專案 / 儲存專案 / 另存新檔`，modal 期間仍可使用。
3. GUI 開啟、儲存、另存與既有 Windows 雙擊／argv 共用 authoritative project format / loader。
4. CornerType 細參數在主 2D 與 3D 預設鎖定並**實際零佔位隱藏**；鎖鈕文字明確可見，解鎖／重新鎖定不改 Corner state。
5. 已知盤型 CornerType 類型固定，但同 type 細參數可解鎖修改並 Save/Load round-trip。
6. 已知盤型 corner policy 必須進入 2D/3D/baseline manufacturing，同時保留基準 DXF 的固定孔、MARKING 與 secondary features。
7. 指示燈盒／指示燈小門維持固定唯讀，不能解鎖。
8. `existing_parts`、先前 OVERLAY=400、浮點顯示、上下截角小圖方向與其他既有回歸不得退化。

## TDD / Focused 驗證

- 新增主 GUI / 3D parameter lock regression；2026-08-23 10:xx 補 visual/layout contract，直接驗證 lock button 與 `winfo_manager()`。
- 新增 global project controls 與 Save/Save As/Open round-trip regression。
- 新增 known-model same-type fine parameter persistence / factory type enforcement regression。
- 新增 known baseline structural override 保留 secondary entities regression。
- Focused regression：`102 passed`。

## 完整回歸

執行環境：Xvfb + `PYTHONPATH=.`。

結果（2026-08-23 10:34 最終程式狀態）：

```text
234 passed
2 skipped
4 deselected
```

4 個 deselected 為既有測試硬編碼 `/mnt/data/自訂.p6fold`，本輪沒有以替代 fixture 假裝通過。

## 編譯／設定檔邊界

- `python -m py_compile gui.py fold_designer_bridge.py ae_engine/manufacturing_api.py ae_engine/ae.py`：通過。
- `config.ini` SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，本輪不得修改。

## 最終契約

```text
Project scope
├─ 主視窗左上：開啟專案 / 儲存專案 / 另存新檔
├─ 3D 視窗左上：開啟專案 / 儲存專案 / 另存新檔
└─ Page/Footer scope：套用 / 確定 / 取消

Corner parameter scope
├─ 自訂：類型依既有權限，細參數需解鎖
├─ 已知：類型固定，細參數可解鎖
└─ 固定共享件：完全唯讀
```
