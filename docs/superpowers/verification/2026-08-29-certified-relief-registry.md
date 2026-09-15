# 2026-08-29 已認證截角資料庫完整化驗證

## 驗證目標
確認 Phase6 已切換為 **Certified-first / 3D-fallback / 3D-shadow-validation**：已知公式不再被 3D solver 覆蓋；金庫型與受電箱固定截角、標準 Assembly Intent、linked-FW 實檔案例都由可版本化 registry 保護。

## Active Registry
### Fixed Corner Policy
- Vault：EndCap、Door、Indicator Box、Indicator Door、Base Plate。
- 受電箱：EndCap、Door、Indicator Box、Indicator Door、Base Plate；family-specific，不靜默借用 Vault。

### EndCap TOP Assembly Relief
- `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1` — CERTIFIED，linked-FW INSERT。
- `ENDCAP_TOP_INSERT_STANDARD_V1@1` — CERTIFIED，標準 `ytop1` INSERT。
- `ENDCAP_TOP_OVERLAY_STANDARD_V1@1` — CERTIFIED，flat-X OVERLAY。
- `ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1@1` — CERTIFIED，標準二級 INSERT_OVERLAY。
- `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1` — CERTIFIED，linked-FW 二級 INSERT_OVERLAY；來源為既有 C04 製造契約。

## Fresh Verification

```text
py_compile production modules: PASS

collision / backprojection / registry:
87 passed

FinalScene / assembly 3D / shared dimensions:
61 passed, 2 skipped

Tk return-to-2D + corner dimension controls (xvfb):
8 passed

registry-driven GUI matrix (fresh independent xvfb process):
INSERT          1 passed
OVERLAY         1 passed
INSERT_OVERLAY  1 passed

receiving family geometry + GUI family switch:
9 passed

project controller / project session:
11 passed
```

這些群組互不重複計算時合計 **179 passed / 2 skipped / 0 functional failures**。兩個 skip 是非 Tk 環境下的 display-dependent 視圖案例；Tk 專項已另外用 xvfb 執行並通過。

## 實檔驗證
### 自訂(9).p6fold
- intent：INSERT。
- Head/Tail：`ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1` / `CERTIFIED`。
- semantic assembly joint：Head physical bottom、Tail physical top。
- 實際 relief：左右 `38×27`，無 secondary stage。
- collision overlay：170 segments，確實顯示 pre-solve collision evidence。
- 2D vs assembly material diff：0。
- 2D vs single-3D material diff：0。
- Save/Reload 後 rule_id/revision/trust 完整保留，material diff：0。

### 自訂(10).p6fold
- intent：INSERT_OVERLAY。
- Head/Tail：`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1` / `CERTIFIED`。
- 公式：`primary_u=side_fold+FW`、`primary_v=FW-1T`、`secondary_u=side_fold+0.5T`、`secondary_depth=2T`。
- T=2 fixture 實際 relief：`40×23 + 16×4`；此數字不是 registry dead dimension。
- collision overlay：198 segments。
- 2D vs assembly material diff：0。
- 2D vs single-3D material diff：0。
- Save/Reload 後 rule_id/revision/trust 完整保留，material diff：0。

## 安全契約驗證
- fallback OFF 仍執行 CERTIFIED lookup；只禁止 registry MISS 的 3D discovery。
- `ENGINE_CONFLICT` 保留 certified canonical material，不採用 shadow candidate。
- `REGISTRY_AMBIGUOUS` 直接拋錯，不偷偷 fallback。
- stale certified revision 不 replay。
- Promotion UI 只產生 manifest，`mutates_registry=False`。
- GUI matrix 直接由 active Certified Relief Registry 列舉 Assembly Intent；新增 active intent 後自動進 gate。
- fixed-policy adapter / known-model state 已由 family-aware registry 供應；legacy C01~C04 僅保留 compatibility。

## Config
`config.ini` 與 20260829_082214 基準 SHA256 完全相同：
`980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`

## 封包
預定同時間戳：`20260829_131622`。最終 ZIP 的 unzip / extracted SHA256 驗證結果寫入 `DELIVERY_README.md`。


## 最終 Fresh Gate（2026-08-29 13:39 Asia/Taipei）

- `python -m compileall -q ae_engine fold_designer_bridge.py phase6_final_scene_view.py gui.py phase6_project_controller.py phase6_project_file.py phase6_project_session.py`：PASS。
- Certified Registry / collision / backprojection / intent matrix：`87 passed`。
- Registry-driven 真 Tk GUI matrix：`3 passed`（INSERT / OVERLAY / INSERT_OVERLAY）。
- Assembly 3D / corner dimensions / FinalScene ownership / return-to-2D：`38 passed`。
- Project controller/session + receiving family suite：`29 passed`；另有 2 條 stale GUI test 在本版與 `082214` 基準包都同樣失敗（舊測試仍對 `Menubutton` 讀 `Combobox.values`、舊切換事件假設），判定為既有測試債務，未修改正確 UI/製造邏輯。
- `自訂(9).p6fold` fresh real-file gate：Head/Tail `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1` / CERTIFIED，兩側 `38×27`，2D vs assembly material diff=0，Save/Reload rule metadata 完整。
- `自訂(10).p6fold` fresh real-file gate：Head/Tail `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1` / CERTIFIED，兩側 `40×23 + 16×4`，2D vs assembly material diff=0，Save/Reload rule metadata 完整。
- `config.ini`：與 `082214` 基準 SHA256 相同 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。

最終交付封包時間戳固定為 `20260829_133925`；最終 ZIP 解壓逐檔 SHA256 結果會在封包完成後回寫本文件與 `DELIVERY_README.md`。


## 封包 Completion Gate
- FULL manifest：681 files。
- UPDATE manifest：28 files（相對 `082214` 基準真實新增／修改；不含 `config.ini`）。
- 第一輪實際解壓逐檔 SHA256：FULL `681/681`、UPDATE `28/28`；missing=0、mismatch=0、extra=0。
- `unzip -t`：FULL / UPDATE 均 `No errors detected`。
- 文件 completion 狀態回寫後，使用同一 `20260829_133925` 時間戳重新封包，交付前再執行同一逐檔檢查。


## 2026-08-29 15:xx — INSERT 單級拓撲與 linked-FW C04 修正

- 純 `INSERT` 與 `OVERLAY` 是**單級截角**；資料模型現在會強制清除任何殘留 `secondary_retain_t` / `secondary_depth_t`。
- Certified Registry 增加 topology boundary validation：`INSERT` / `OVERLAY` 規則若回傳二級 geometry，直接拒絕，不得成為 canonical material。
- 撤銷錯誤的 linked-FW `INSERT_OVERLAY` 推導 `16×23 + 14×4`。既有 2026-08-21 C04 製造契約明確規定第二級 CUTTING = `side_fold + 0.5T`；第一級 X = `side_fold + FW`。
- 因此 T=2、side_fold=15、FW=25、無獨立 ytop1 的 linked-FW fixture 正確為 **`40×23 + 16×4`**。有 ytop1=16 的標準 C04 fixture 為 **`40×39 + 16×4`**。
- `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1` 信任等級改為 `CERTIFIED`，證據來源改為既有 C04 製造規格，不再以錯誤 3D 候選升格。
- 實際 `自訂(10)` 切換為純 INSERT 後：Head/Tail = **38×27，secondary=None**；Save/Reload 後仍保持單級。
