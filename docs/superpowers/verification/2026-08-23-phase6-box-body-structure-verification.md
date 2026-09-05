# Phase6 箱身多結構型態驗證紀錄 — 2026-08-23

## 基準與查核來源

- 唯一程式基準：`PHASE6_HOLE_EDITOR_CANVAS_VIEW_FULL_20260823_160603 (1).zip`
- Code-audited 規格：`docs/superpowers/specs/2026-08-23-phase6-box-body-structure-buildable-spec.md`
- Code audit 紀錄：`docs/superpowers/verification/2026-08-23-phase6-box-body-structure-code-audit.md`
- `config.ini` 明確不修改。

## Code-audit 後補強

### 1. 側背分離 3D 組裝

- 修正右側板後折的鏡射方向與 assembly transform。
- 左／後／右三片組裝後不得把箱體 W / D envelope 向外撐大。
- W=1200、D=400、T=2 的 regression 直接驗證 assembled mesh 不超出原成型包外範圍。

### 2. Operation-aware feature clipping

跨 W seam 的 feature 不再把完整 primitive 複製給相鄰板件，而是先依原始 Source of Truth 解析，再與每片實際 material boundary 求交：

- CUTTING：裁成封閉 CUTTING profile，可影響 material subtraction。
- BLIND_HOLE：裁切後仍為 BLIND_HOLE，不升級成 CUTTING。
- MARKING / DATUM：保留原 layer，只保留實際線稿，不建立假 CUTTING closure。
- layered profile：每個 sub-layer 各自裁切並保持 layer / closed 語意。
- 完全落在單片內的 CIRCLE / RECT 仍保留原 primitive，不做不必要近似。

### 3. Corrupt W state fail closed

- W 二分若保存的 `W左 + W右 != W`，resolver 直接拒絕產生幾何。
- W 三分若左右不相等或三段總和不等於 W，resolver 直接拒絕。
- GUI 人工編輯仍在 commit seam 做補全與 reject/revert；resolver 不再 silent repair corrupt/direct-API state。

### 4. Legacy `.p6fold` migration

- 舊檔沒有 `box_body_structure`：仍解析為一體成型。
- 舊檔缺 structure lock 時，只在 migration 當下沿用既有 model editability：已知基準型號 locked；`自訂` / legacy `未知類型` unlocked。
- 一旦新檔已保存 explicit active type / lock / configs，重載完全以保存值為準，不再從 model 覆寫。

### 5. CROSS / RETAIN canonical semantics

- W seam 封頭尾與底板的 0.5T 單邊留肉量改由既有 `CROSS + RETAIN + CornerDirection + amount_t` 語意解析。
- 左右／上下只負責幾何 placement；單邊留肉量不再另造第二套 T 公式。

### 6. 正常全域 W commit 與 strict resolver 分離

- 使用者已設定 W 二分／W 三分後再修改總 W，於 GUI commit seam 依各型態最後 driver 重算補全尺寸。
- 新 W 若讓保存 driver 無法形成合法分件，拒絕該次 W 並恢復上一個合法值。
- resolver 本身仍保持 fail closed，不因這個正常 UI 行為重新引入 silent repair。

## 測試證據

### Audit contract 專項

```text
PYTHONPATH=. xvfb-run -a python -m pytest -q tests/test_phase6_box_body_audit_contract.py

13 passed
```

### 箱身結構專項（含真實 Tk GUI）

```text
PYTHONPATH=. xvfb-run -a python -m pytest -q \
  tests/test_phase6_box_body_structure.py \
  tests/test_phase6_box_body_audit_contract.py

38 passed
```

### 完整原始 suite

```text
PYTHONPATH=. xvfb-run -a python -m pytest -q

395 passed, 2 skipped, 4 failed
```

4 個 failure 全部為既有硬編碼外部 fixture：

```text
FileNotFoundError: /mnt/data/自訂.p6fold
```

### 原始 `160603` 基準對照

在完全未修改的原始 `160603` 基準包上單獨執行同 4 個節點，結果同樣為 `4 failed`，原因同樣是 `/mnt/data/自訂.p6fold` 不存在，因此不是本輪回歸。

### 完整可執行回歸

```text
PYTHONPATH=. xvfb-run -a python -m pytest -q \
  --deselect=tests/test_phase6_linked_fold_chain_and_parts.py::test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain \
  --deselect=tests/test_phase6_linked_fold_chain_and_parts.py::test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine \
  --deselect=tests/test_phase6_linked_fold_chain_and_parts.py::test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width \
  --deselect=tests/test_phase6_linked_fold_chain_and_parts.py::test_real_delete_confirm_readd_linked_tail_confirm_roundtrip

395 passed, 2 skipped, 4 deselected, 0 failed
```

### 語法

```text
python -m compileall -q .
```

通過。

## Code / Spec review

- 更新過期註解：跨 seam feature 現在明確描述為 actual material clipping，不再宣稱完整 CIRCLE 會同時存在於兩片。
- `CONTEXT.md` 移除已過期的「規則尚待確認」文字；implementation/migration 決策留在 Buildable Spec / verification，不污染領域 glossary。
- 未新增只為縮檔案或降行數的 module；本輪只在既有箱身 structure state 與 resolved geometry seam 補強。

## config.ini

- 原始基準 SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
- 本輪工作樹 SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
- byte compare：相同。
- 結論：未修改。
