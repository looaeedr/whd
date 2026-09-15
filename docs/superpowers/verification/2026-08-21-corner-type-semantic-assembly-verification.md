# 截角類型語意與裝配驗證紀錄

## 驗證範圍

本紀錄驗證以下文件所描述的實作：

- `docs/superpowers/specs/2026-08-21-corner-type-semantic-assembly-design.md`
- `docs/superpowers/plans/2026-08-21-corner-type-semantic-assembly-implementation.md`

## 必須成立的行為

- 正式截角類型為：十字截角／貼外型／嵌入型／嵌入貼外型；程式內部代碼分別為 `CROSS / OVERLAY / INSERT / INSERT_OVERLAY`。
- 舊 `C01~C04` 能轉換成新的製造語意。
- **正確二級 CUTTING = 側折 + 嵌入留肉量**；`FW - 嵌入留肉量` 只代表兩級之間剩餘材料。
- 箱身高度依封頭／封尾截角裝配語意得到 `H-2T / H-T / H`。
- 箱身孔位與面特徵使用同一份上／下裝配偏移。
- GUI、3D 折彎設計器 Bridge 與 INI 都能保存完整截角參數。
- 新 GUI 不顯示舊 C 代碼或 `0°/90°` 截角旋轉操作。
- 已知固定板件仍可看見截角摘要；共享指示燈板件維持不可編輯。
- `fold_designer_original.py` 製造幾何保持不變，只增加文字倍率。
- 使用者可見的新截角介面與接手文件使用繁體中文。

## 回歸測試

主要測試：

```bash
PYTHONPATH=. python -m pytest -q \
  tests/test_corner_semantics.py \
  tests/test_corner_ui_integration.py \
  tests/test_traditional_chinese_handoff.py \
  tests/test_endcap_regression_and_text_scale.py \
  tests/test_custom_model_inheritance.py
```

預期：全部通過。

## Python 編譯驗證

```bash
python -m py_compile \
  ae_engine/ae.py \
  ae_engine/contracts.py \
  ae_engine/corner_type_ui.py \
  ae_engine/manufacturing_api.py \
  ae_engine/sheetmetal_features.py \
  ae_engine/sheetmetal_geometry.py \
  ae_engine/sheetmetal_part_adapters.py \
  gui.py phase6_settings_center.py fold_designer_bridge.py fold_designer_original.py
```

預期：結束碼為 0。

## 製造幾何 smoke test

當 `H=600, T=2`，封頭與封尾都設定為純嵌入：

- 箱身 DXF 的 CUTTING 高度必須是 `600mm`，不能仍是 `596mm`。

金庫型預設封頭尾在 `FW=25, T=2, 側折=15` 時：

- 拓撲維持 5 條 BEND。
- 嵌入貼外第二級位置為 `16mm`。
- 第二級深度為 `4mm`（`2T`）。

## Renderer 製造幾何不變

`fold_designer_original.py` 只允許加入文字縮放倍率；折彎輪廓、3D/2D 幾何與操作模型不得改變。

## Patch 完整性

最終 patch 必須從使用者本次上傳的精確來源產生，套用到乾淨基準後，再將所有變更檔逐位元與交付樹比對。

## 最新完整驗證結果 — 2026-08-21

截角語意與 GUI 回歸測試：

```text
36 passed（含自訂繼承、字級與封頭尾回歸）
```

製造驗證：

```text
VAULT_ENDCAP_BENDS 5
TOP_SECONDARY_LEFT 16.0
TOP_SECONDARY_DEPTH_LEFT 4.0
```

Python 編譯完成且結束碼為 0。

繁體中文防退化測試包含：截角名稱、GUI 操作文字、Superpowers/交付文件章節與語言規則。

完整 patch 以 2026-08-21 使用者最新上傳檔為乾淨基準，共 23 個變更／新增檔；套用後逐檔比對一致。

Renderer 差異只允許 `ui_text_scale` 與 `fontsize`／刻度字級倍率，不允許幾何公式差異。

## 行尾注意事項

使用者上傳的部分引擎檔案使用 CRLF。交付時保留原始行尾，不為了讓 `git diff --check` 安靜而整檔轉成 LF，避免產生無關的整檔差異。Patch 驗證應以本次上傳精確基準及逐位元比對為準。

## 文字大小驗證

- 文字大小：小 / 中 / 大。
- Tk 測試驗證 `Arial 10` 會依序得到 `10 / 12 / 14`。
- 既有 Canvas 文字與切換後新建立的 Canvas 文字都會跟隨倍率。
- 3D 折彎設計器實際啟動驗證：`小=1.0`、`中=1.2`、`大=1.4`，`state.ui_text_scale` 與控制器一致。
- Matplotlib 2D 尺寸、孔位文字、標題與 3D 刻度由 `state.ui_text_scale` 控制。

## 自訂模式驗證

新增 `tests/test_custom_model_inheritance.py`，驗證：

- 新 UI 名稱固定為「自訂」。
- 舊 `未知類型` 字串仍相容判定為自訂。
- 金庫型 → 自訂會複製封頭／封尾／門／底板目前固定截角規則。
- W/H 等尺寸、折彎值、已建立孔位／Feature 物件不因模式切換被重建。
- 3D Bridge 從已知型號切入自訂時重新以目前已知規則為起點，不恢復舊自訂截角草稿。
- 實際 Tk smoke：建立主 GUI、由金庫型切換自訂，再執行使用者 traceback 的 `draw_box_body()` 路徑，結果正常。

最新測試（Xvfb）：

```text
36 passed
GUI_CUSTOM_SMOKE_PASS 自訂 INSERT_OVERLAY extra_cut
```

## 2026-08-23 後續修正驗證

本輪新增驗證範圍：

- `OVERLAY` 的 Head/Tail 不生成左右 X 向 BEND，Fold Designer 不提供 X 軸折彎頁。
- 使用者明確選擇 `OVERLAY` 時，下方預設為 `CROSS + EXTRA_CUT + WIDTH + 1.5T`。
- 主 GUI 與 Fold Designer 的 explicit selection 都會要求重新套用該預設。
- 普通載入／刷新保留使用者已修改的下方截角；`HEIGHT / BOTH / 其他 amount / CROSS+STANDARD` 都不得被洗回 1.5T。
- 自訂模式不顯示基準檔專屬固定孔／開孔設定。
- 對稱折彎的成對刪除具交易一致性。
- 3D Fold Designer 使用 modal transaction，主 2D 不可同時操作。
- `config.ini` 與 0311 基準逐位元一致。

TDD focused regression：

```text
80 passed
```

完整 Xvfb pytest（只 deselect 4 個硬編碼 `/mnt/data/自訂.p6fold`、目前環境不存在的既有 fixture）：

```text
207 passed, 2 skipped, 4 deselected
```

Python 編譯：

```bash
python -m py_compile gui.py fold_designer_bridge.py \
  ae_engine/corner_type_ui.py ae_engine/manufacturing_api.py ae_engine/ae.py
```

結果：結束碼 0。

`config.ini` SHA256：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```

此值與 0311 完整包一致。
## 2026-08-23 07:44 — OVERLAY EndCap 422 structural blank 回歸

根因分成兩層：

1. `fold_designer_bridge.build_endcap_xy_profiles()` 在 OVERLAY 時雖移除 X angle，卻把舊 INSERT 型 `yl1 + (W-4T) + yr1` 加總成 flat span，`400/2/15/15` 因而仍為 `422`。
2. `ae_engine.sheetmetal_part_adapters.build_unknown_endcap_result()` 的 CUTTING/material structural blank 同樣仍使用 `W-4T+|yl1|+|yr1|`；Fold Profile 只替換 BEND primitive，無法改掉已建好的 422 外框。

TDD：

- Bridge regression 先得到 `Obtained: 422 / Expected: 400`。
- AE structural regression 先得到 `result.width = 422 / Expected: 400`。
- 修正後：OVERLAY `endcap_w_flat=W`；自訂 EndCap top CornerType 兩側皆為 OVERLAY 時，structural `total_width=W`、`left_fold=right_fold=0`，structural bends 不含 `left/right`。

真檔 `自訂(4).p6fold`：

```text
assembly = 貼外
Head X profile = [(400, no angle)]
Tail X profile = [(400, no angle)]
Head material bounds = 400 × 284
Tail material bounds = 400 × 284
主 GUI 封頭/尾展開 = 400.00 × 284.00 mm
```

最終完整 Xvfb 回歸：`208 passed, 2 skipped, 4 deselected`。


## 2026-08-23 08:15 — 浮點顯示 / 下方截角縮圖 / Physical Presence 全鏈驗證

本輪同時驗證三組尚未封包的修正：

1. UI 近整數浮點殘差：`400.0000000000006 -> 400`，合法 `400.25` 保留；只改文字格式，不改幾何。
2. CornerType preview：上方維持垂直翻轉；下方／左下／右下恢復原始方向；只改 canvas transform。
3. 刪除板件 physical presence 全鏈：`existing_parts` 與 export checkbox 分離。

TDD 新增/更新 regression：

- 刪除板件後，左側 result rows 與輸出 checkbox rows 使用 `pack_forget` 完整消失，不留佔位。
- stale export checkbox 即使仍為 True，只要 physical presence=false，DXF export 不得呼叫 manufacturing export。
- stashed `part_profiles` 可以保留以供重新新增，但 deleted Head/Tail 不得因此建立 FinalScene/RenderData。
- 單純取消 DXF checkbox 不得從後續 Fold Designer snapshot 的 `existing_parts` 刪掉實體板件。
- Indicator Box 舊主畫面入口在尚無 exact workspace 時仍可建立 box+small-door；已有 `.p6fold` / 3D workspace 後則由 exact `existing_parts` 決定，不因 stale toggle 復活。

使用真檔 `/mnt/data/自訂(4).p6fold` 驗證：

```text
existing_parts = box_body, head, tail
左側 result rows：box_body/endcap = visible；door/base/indicator = hidden，零佔位
右側 2D tabs：box_body/head/tail = normal；door/base_plate = hidden
DXF selector rows：只剩 box_body/head/tail
Door/Base result value = "-"
重新建立 Fold Designer snapshot：existing_parts 仍只有 box_body/head/tail
Head/Tail 展開維持 400.00 × 284.00 mm
```

完整 Xvfb regression（只 deselect 4 個硬編碼 `/mnt/data/自訂.p6fold` 的既有 fixture）：

```text
216 passed, 2 skipped, 4 deselected
```

編譯：

```bash
python -m py_compile gui.py fold_designer_bridge.py phase6_project_file.py ae_engine/*.py
```

結果：exit code 0。

`config.ini` SHA256（本輪前後一致）：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```
