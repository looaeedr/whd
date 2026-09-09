---
name: 驗證板件與DXF
description: 使用者要求驗目前板件、指定板件、全部板件、DXF反驗證或 Save→Reload 驗收時，對 current production state 執行 canonical geometry、2D/3D、DXF reopen、multipart physical-part 與 persistence parity；中隔另加 relief/placement/fixed-hole diagnostics。
---

# 驗證板件與 DXF

## 何時使用

使用者要求下列任一工作時，直接執行本 Skill，不要只解釋：

- `驗目前板件` / `驗這個板件` / `查目前板件對不對`
- `驗箱身` / `驗中隔` / `驗封頭` / `驗封尾` / `驗門` / `驗底板`
- `驗全部板件` / `完整驗收全部板件`
- `DXF反驗證` / `驗輸出的DXF` / `驗全部DXF`
- `Save→Reload 驗收` / `存檔再讀回來驗`

## 支援板件

至少涵蓋目前 canonical manufacturing part identities：

- `box_body`
- multipart physical pieces，例如 `box_body:left_side / box_body:back / box_body:right_side`
- `box_body:divider:*` / Receiving divider
- `head`
- `tail`
- `door` 與 dynamic `door_c*_r*`
- `base_plate` 與 dynamic `base_plate_c*_r*`
- `indicator_box`
- `indicator_door`
- `inner_door:*`
- 其他由 workspace/manufacturing resolver 實際產生的 dynamic physical-part IDs

禁止用 `PART_LABELS` 或 GUI 固定白名單冒充 physical-part authority；expected parts 必須從 current workspace / resolved manufacturing output 取得。

## 驗證模式

### A. 驗目前 / 指定板件

**不需要先存 `.p6fold`。** 直接從 current production state 驗：

1. canonical `PartRenderData` / Final Material；
2. material bounds / span / closed contour；
3. authoritative holes/features；
4. fold guides / BEND；
5. 2D / 3D / DXF 是否使用同一 resolved geometry；
6. 該板件若有 placement / assembly contract，再驗 world placement / contact / illegal penetration。

### B. DXF 反驗證

不需要先存專案，但必須真的輸出 DXF：

1. canonical manufacturing geometry → 實際 `.dxf`；
2. `ezdxf.readfile()` 重開輸出的檔案；
3. 重新抽 `CUTTING / BEND / holes / layers`；
4. normalize 後 compare canonical；
5. 多件式/動態板件同時驗 `expected physical parts == actual exported DXF files`。

錯誤至少包括：

`MISSING_PART / EXTRA_PART / CUTTING_MISMATCH / BEND_MISMATCH / HOLE_MISMATCH / LAYER_MISMATCH / UNCLOSED_CONTOUR / SERIALIZATION_ERROR`。

### C. 完整板件驗收

A + B + Save→Reload parity：

1. current state 直接驗；
2. DXF export → reopen → compare；
3. `.p6fold` Save → Reload；
4. Reload 後重建 canonical manufacturing output；
5. 比 Final Material、holes/features、BEND、placement、dynamic IDs、physical-part count；
6. `config.ini` SHA256 前後一致。

### D. 驗全部板件

從 current workspace 列舉所有 existing physical parts，逐件跑 A/B；再跑 C 的 project parity。任何一件少檔、多檔、stale dynamic ID、geometry mismatch 都使整體 FAIL。

## 板件專用加強驗證

### Receiving Divider / 中隔

除通用驗證外，必須再驗：

- `W - 2T` / Final Material span；
- fixed-hole authoritative DXF feature datum；
- Ø6.4 hole count/diameter/physical-edge offset；
- collision/backprojection relief；
- true-thickness skin→solid sweep；
- FW face flush / core inward / authoritative placement；
- pre/post collision、illegal penetration=0、retained mating contact；
- head/tail shared datum parity。

### Multipart BoxBody

- 每個 physical piece 都有 stable identity / own geometry / own DXF；
- Receiving 三件式至少能辨識 `left_side / back / right_side`；
- aggregate `box_body` 不得取代逐片 manufacturing acceptance；
- exported DXF count 必須等於 resolved physical-piece count。

### Head / Tail

- Head/Tail 分開驗，不得用一端 PASS 推定另一端；
- mirror/native orientation、FW / Corner policy、BEND 與 holes 均以各自 resolved output 驗證。

### Door / Base Plate / Indicator / Inner Door

- 依 current resolved part identity 驗 Final Material、holes/features、BEND、DXF reopen；
- dynamic rows/columns 必須使用 stable IDs，family/project reload 後不得殘留 stale IDs。

## 通用正式測試族

DXF / multipart / production export 基礎：

```text
tests/test_dxf_acceptance.py
tests/test_multipart_dxf_acceptance.py
tests/test_resolved_manufacturing_export.py
tests/test_resolved_manufacturing_geometry.py
tests/test_manufacturing_api_finished_face_contract.py
```

Project / Save→Reload / dynamic IDs：

```text
tests/test_issue41_persistence_parity.py
tests/test_issue45_dynamic_parts_2d_roundtrip.py
tests/test_phase6_project_controller.py
tests/test_phase6_project_file.py
tests/test_phase6_project_ownership.py
tests/test_phase6_project_session.py
```

中隔加強族：

```text
tests/test_issue38_receiving_divider_baseline.py
tests/test_issue39_divider_relief.py
tests/test_issue40_divider_6p4_shared_datum.py
tests/test_phase6_t16_receiving_placement.py
tests/test_dm3_divider_canonical_relief_contract.py
tests/test_dm4_divider_resolved_sinks.py
```

實際任務仍需依 requested part 與 current source seam 擴充 targeted tests；禁止因這份清單沒有列到就跳過該板件真正 owner。

## 必須回報

不要只回 PASS。至少回：

- branch / tested head / run_id / terminal status；
- requested part IDs / resolved physical part IDs；
- 每個板件的 PASS/FAIL；
- Final Material bounds/span；
- hole/feature count、尺寸、datum；
- BEND count/endpoint parity；
- DXF reopen 結果；
- multipart expected/actual file count；
- placement/collision（若適用）；
- Save→Reload parity（若要求完整驗收）；
- `config.ini` before/after SHA。

中隔再追加 middle segment、FW planes、illegal penetration、retained contact、skin→solid areas 等 diagnostics。

## Remote QA 硬規則

- 建立 remote run 後鎖同一 `run_id + head_sha` 輪詢到 `completed`；`queued/in_progress` 不得停。
- Install/Preflight/import/dependency failure 不能冒充產品 FAIL。
- 一次性 workflow/evidence 用完刪除並遠端反讀確認不存在。
- 驗收後 production/test blob 有 drift，原 GREEN 失效並重跑。

## Validation / Production 邊界

驗證只判對錯，不能反向成為 production 計算來源。pytest expected、DXF reopen 量測值、boolean fringe、collision probe、bbox、單次差值皆不是 manufacturing authority。

## UI 邊界

本 Skill 是 AI / 工程 QA 入口，不代表 GUI 已新增「驗證板件」按鈕。若要 GUI 一鍵驗證，另開 UI 功能工單。


## 自動交接硬閘門：Focused QA 不得取代成品板件驗收

本 Skill 不只在使用者明確說「驗板件」時執行。只要本輪修改會影響下列任一條 production seam，**在合併／關單／release 前必須自動交接到本 Skill**：

- physical-part identity / dynamic part / multipart topology；
- 2D 預覽、3D FinalScene、2D↔3D navigation / sync；
- manufacturing Final Material / holes / BEND / placement；
- DXF export / physical-piece file set；
- Save→Reload / project persistence；
- GUI 或 Bridge 只是 View/adapter，但修改結果會改變操作員看到或選到的實體板件。

### 不可替代規則

- issue-specific / focused regression 只證明該 bug seam；**不能因為 focused QA GREEN 就宣告成品驗收完成**。
- Headless/Tk/assembly/navigation contract GREEN 也不能自動替代 DXF reopen、physical-piece enumeration、Save→Reload 或 requested-part parity。
- 若只改單一板件且影響範圍明確，至少跑「驗該板件」；若同時跨 2D/3D/DXF/persistence、dynamic IDs 或 multipart，必須升級為「完整板件驗收」。
- 若 remote QA 已建立，仍遵守 monitoring-remote-qa：鎖定 run_id + head_sha 輪詢到 terminal，cleanup 後 drift audit 無 production/test drift 才能接受。
- 驗收數字仍只作判定，不得回灌 production。

### 合併前最小證據

至少留下：

1. focused/issue-specific QA 結果；
2. 本 Skill 的 requested physical parts 與 resolved physical IDs；
3. 2D/3D parity；
4. DXF reopen（若該任務碰 physical geometry / export / multipart）；
5. Save→Reload（若該任務碰 persistence / active physical child / dynamic topology）；
6. config.ini before/after SHA；
7. tested head → cleaned head drift audit。

缺少本 Skill 的成品驗收證據時，狀態只能是 **focused GREEN / final acceptance pending**，不得標記 ACCEPTED。
