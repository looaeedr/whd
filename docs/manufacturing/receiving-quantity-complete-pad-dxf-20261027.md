---
whd_doc_role: CURRENT
whd_contract: issue1490-quantity-complete-pad-selected-dxf
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1490：數量及多連模式原 GUI 完整 NFB DXF 必須包含來源認證 PAD

## 2026-10-27 Windows 實際失敗證據
R5-2600 的真正 `BoxCalculatorGUI.export_selected_dxf()`：在舊版已提交兩個不同深度的 V5 NFB，3D 顯示一片實體 PAD，但完整選取箱身＋內門＋底板後，Quantity CSV export 只輸出 13 個 Q-group DXF，沒有為 PAD 建立製造需求。程序回報成功，形成實際漏件。這不是 hashed Q-group 檔名錯誤，而是製造數量 demands 缺失。

## 唯一來源、合法修復範圍
- 不新增 GUI 按鈕，不更改門片、底板、固定片、PAD 成形公式，也不硬寫 PAD 數量。
- 僅當操作者選擇 BODY／DOOR／BASE 且該 Quantity 版本是 current committed CSV V5 時，使用既有 `verified_pad_base_physical_sheets(snapshot, original.parts, allow_empty=True)` 核對實體 Base、PAD physical ID、四孔 CUTTING、兩 BEND、全厚度接觸／基座碰撞、來源層 owner。
- **逐版本**依已保存 QuantityModel 的 `version_id`、piece_count 建立真實 PAD 需求，交回現行等價幾何分組、Q3 標註、每份 DXF 原子 staging、`ezdxf` 重開核對。可等價合併，但不能遺失實體 owner 與件數。
- PAD 來源驗證在建立輸出資料夾之前完成；任一版本 stale／缺 Base 或 inner door，整批 fail closed、不得出半包。
- 部分選件不主張「整箱」，保持既有部分輸出；與 Set/Bay 原本來源完整出圖共用的來源規則一致。
- 仍不放寬 generic MFG2／NC／焊接工藝守衛，也不將本交付冒升級成全設備認證；正式 X 需使用者當次 /推推。

## 多連 Set/Bay 相同的完整來源契約
- 已提交 CSV V5 的每個現行實體 Bay 具有自己的 Base/PAD 裝配、真實材質與 `receiving_instance_namespace`，不能以第一個 Bay 的 PAD 代替第二個 Bay。
- 原 `export_current_receiving_multibay_dxf` 在全部選擇 BODY/DOOR/BASE 時，對各 Bay 獨立執行同一 `verified_pad_base_physical_sheets`，只將真實 PAD 原始場景加入原子 DXF 輸出及讀回，並以 Bay namespace 對應檔案。兩個 Bay 的 PAD 各自輸出，不偽造組數或重複名稱。
- 缺選 Base/內門或第二 Bay PAD 來源失效，應在建立目錄前整批拒絕；局部選件保持既有合法出口。
- `tests/test_issue1502_current_csv_multi_bay_once.py` 實際兩 Bay 回歸需驗證兩個獨立 PAD DXF 各 5 CUTTING、2 BEND；源失效原子禁止輸出。

## 驗證收據
- 原 GUI 同一份本機來源：修正前 13 個 Q-group DXF，修正後 14 個，新增真 PAD：5 CUTTING、2 BEND、1 CHECK，ezdxf 全檔重新讀取通過。
- Windows 原生 PAD 2D/3D、Save/Reload 及原 NFB 圖包：既有測試通過。
- `tests/test_issue1490_quantity_complete_pad_export.py`：兩個 Quantity 版本 Q3 + Q2 的真 PAD＋Base 原來源、所有實體件數、任一版本來源失效原子零輸出，以及部分選件路徑。
- `tests/test_issue1502_quantity_current_csv_full_batch.py` 原先排除 5 個 PAD 的斷言補強為 source-derived 實體 PAD 數量，未刪除舊測試。

## Release gate
新分支 → Windows GUI 實測及 regressions → exact SHA Product CI → GitHub localX，未獲 /推推 不觸及正式 X。
