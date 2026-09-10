---
name: 截角資料入口收斂
description: Use when moving WHD legacy 2D/unfold entry into Fold Designer 截角資料 mode, including authoritative part projection, multipart selection, unfold view adapter, legacy Notebook removal, and parity validation.
---

# 截角資料入口收斂 Skill

## 目的

把舊主視窗獨立 2D Notebook 入口收斂進 Fold Designer，但**不能**因此建立第二份 2D 狀態、第二個 manufacturing solver 或弱化既有展開圖功能。

## 執行前硬閘門

1. 先跑 `tools/phase6_skill_preflight.py --task <完整任務>`。
2. 讀完所有 REQUIRED SKILLS / REQUIRED REFERENCES 並留下 `READ_REFERENCE:` evidence。
3. 修改檔案名確定後，再以全部 changed files 重跑 preflight。
4. 每次施工從最新 production target 開新分支，不直接改 target。

## SSOT 契約

唯一合法資料鏈：

```text
Project / Workspace authoritative state
 -> stable physical part identity
 -> PartSpec / Resolved Manufacturing Geometry
 -> authoritative PartRenderData / FinalScene
 -> 3D View + Unfold View
```

禁止：

- `2d_parts` / `corner_parts` 之類第二份板件存在狀態；
- 用顯示 label 當 identity；
- 新 View 自己重算 CUTTING / BEND / holes / CornerType；
- 從 3D renderer / bbox / screenshot 反推 2D；
- validation expected value 回灌 production；
- legacy widget 與新 widget 互相抄值作為同步機制。

## Navigation 契約

- Fold Designer 板件選單新增「截角資料」。
- 「截角資料」是 mode，不是 part。
- 進入後左側列出 authoritative workspace 當下實際存在的正式板件。
- 點板件後，同一 Fold Designer 圖區切到該板件既有展開圖，不跳回舊主視窗 Notebook、不另開新 2D window。
- 「功能不變，只改入口」：原本展開圖的材料外框、截角、孔、BEND、尺寸、標註、互動都保留。

## Stable identity / stale selection

- stable authoritative part key 是唯一 identity。
- refresh 時若 selected key 仍存在則保留。
- key 已從 authoritative parts 消失時，立即丟棄 stale selection 並從 current parts 重新 resolve；不得保留 ghost UI state。

## Multipart BoxBody

- operator 頂層可保持單一「箱身」。
- physical children 各自保留 stable identity。
- 進入箱身展圖時：優先沿用 `_phase6_box_body_active_piece_key` 且它仍存在；否則取 `_phase6_box_body_piece_keys(available_parts)` 的第一個 child。
- physical-child editor 只能是同一 resolved aggregate manufacturing result 的 sink；禁止 second BoxBody solve。

## View-only hard gate

mode switch、selection callback、StringVar trace、View destroy/recreate 不得改：

- manufacturing state；
- existing_parts / available_parts；
- CornerType；
- Fold Profile；
- holes/features；
- Save/Reload payload。

雙 View 過渡期固定走：

```text
authoritative mutation -> invalidate -> legacy View refresh + new View refresh
```

另外，**authoritative state 更新成功不等於 View 已同步**。任何 external sync / authoritative commit 完成後：

- 若「截角資料」View 當下可見，必須在 apply/commit 完成後刷新一次；
- hidden View 不主動刷新；
- replayed / stale revision 不得重刷；
- repeated authoritative revisions 必須一個 commit 對應一次 visible refresh；
- 仍然禁止 widget-to-widget sync，refresh 只能重新讀 authoritative projection/render data；
- View refresh / recreate 本身不得寫回 manufacturing state。

## 舊 2D 移除順序

固定：**先接 -> 驗 parity -> 再刪**。

T7 前不得提前移除 legacy 入口。最終 dead-code gate：

- 使用者無法再進入舊 2D Notebook；
- production navigation 不再依賴 `tab_z/tab_head/tab_tail/tab_door/tab_base_plate`；
- 沒有 dangling callback / stale tab-selection glue；
- shared renderer/helper 若仍服務新 View 可保留，不可因刪舊 UI 誤刪共用能力。

## 測試要求

1. Controller / Adapter contract：authoritative keys、selection lifecycle、multipart、existing render-data sink。
2. Tk headless interaction：mode/part 切換、dynamic add-remove、stale-selection recovery。
3. 小型 Xvfb smoke：真實 Fold Designer widget wiring。
4. Save->Reload parity。
5. `驗證板件與DXF`：dynamic physical parts、DXF reopen、2D/3D canonical parity。
6. `config.ini` SHA256 前後不變。
7. T6 必驗 visible external-sync refresh、hidden no-refresh、replayed revision no-op、repeated revisions 一次一刷，以及 View recreate 不改 state。
8. 最終 Combined Acceptance 後才允許整合 production target。

## 永久防錯

- `READ SKILL != EXECUTE SKILL`；沒有實際 preflight/evidence/角色轉移/checkpoint/QA，不得宣稱已派工或已完成。
- Validation 只能判定對錯，不能成為 production 計算來源。
- 新發現的規則/踩坑同步 Skill、AI knowledge/library、durable agent-readable docs；禁止只留在聊天。
- authoritative state 與 View freshness 是兩個不同 invariant；驗資料同源時也要另外驗 visible View refresh。
