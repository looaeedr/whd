# Phase6 成型 FW Registry / 3D Relief Source of Truth 設計

## 目標

把封頭／封尾上方裝配截角從 UI / CornerType 臨時計算提升為正式 3D 裝配幾何契約。OVERLAY 的 X 向避讓量必須由箱身 Fold Profile 折後的實際 FW 佔位決定，而不是名義 FW、EndCap nominal side fold 或舊 `.p6fold` 已提交 cut polygon。

## 已確認製造真值

以 `金庫型貼外.p6fold` 為標準 fixture：`W=400, T=2, FW(material)=25`。箱身 `fw_left/fw_right` 材料段為 25，兩側真折彎對 outside occupation 的補償合計為 4，因此成型 FW 為 29。OVERLAY 上方每側 X CUT 必須等於成型 FW 29；單側驗證 `29 + 371 = 400`，左右皆切後中央剩寬 342。OVERLAY 下方為獨立 CROSS/EXTRA_CUT，T=2、1.5T 時每側約 3，中央約 394。

## 架構

1. `phase6_fold_profiles.py` 提供唯一的箱身成型 FW 幾何解析函式，從目前 Fold Profile + T 重新計算，不信任持久化 `ui_len_add`。
2. Certified Relief Registry 的 OVERLAY rule 明確宣告 geometry input `BOX_BODY_FORMED_FW`，公式只描述「X relief 需達成 formed mating width」，不得寫死 29。
3. `ae_engine/certified_relief_registry.py` 的 evaluator 從 box body fold profile 解析左右 formed FW，再把其與 EndCap 自身 FW 分離：X relief basis 只補 `formed_fw - endcap_fw`，Y relief 仍使用 EndCap FW/ytop1 語意。
4. 3D assembly solver / resolved manufacturing geometry 是最終製造真值。已認證 rule 先產生 canonical relief，3D solver 做 collision shadow validation；若仍穿透，不能把錯誤 canonical geometry 當完成。
5. `.p6fold` 的 committed relief 只是一份可重播 cache。保存 `relief_contract_version`、registry `rule_id/revision`、box body formed-FW fingerprint、W/H/D/T/FW、assembly intent、box/endcap fold profiles。任一不合即失效並 fresh rebuild。
6. 2D、單板 3D、Assembly view、DXF/NC 與 Save/Reload 都只能消費同一份 `ResolvedManufacturingGeometry` / validated committed relief，不另算第二套截角。

## 不變量

- OVERLAY flat-X：EndCap 不存在左右 X BEND。
- OVERLAY top X CUT（每側）=`BoxBody formed FW occupation`。
- EndCap `frame_width` 仍是自己的材料/製造 FW，不得直接改成 formed FW，避免 Y relief 被放大。
- OVERLAY bottom relief 與 top assembly relief 分離；本 fixture bottom 保持 3/394/3。
- INSERT / INSERT_OVERLAY 的現有 folded-X 語意不得退化。
- Head / Tail 使用同一公式，僅 native orientation / placement 相反。
- Solver 前碰撞可顯示；solver 後必須零穿透。

## Persistence contract

Committed `assembly_relief.source` 新增：

- `relief_contract_version`: integer，首版為 2。
- `box_body_formed_fw`: `{left, right}`。
- `box_body_profile`: 完整 fold-profile fingerprint source。
- `registry_rules`: per-part `{rule_id, revision}`。

Replay 時必須重新從目前 box profile + T 算 formed FW，再與 source 比對。舊檔沒有 `relief_contract_version=2` 或沒有 formed-FW fingerprint，視為 stale cache；不得直接套 cuts。

## 驗收

1. 真實 `金庫型貼外.p6fold`：Head/Tail top=29/342/29；bottom=3/394/3。
2. `29 + 371 == 400` 單側 invariant。
3. 2D / single-part 3D / assembly manufacturing material 完全一致。
4. Save→Reload 後仍命中同一 registry rule / revision 且尺寸一致。
5. 修改 box FW、T、box profile 或 assembly intent 後，舊 committed relief 自動失效。
6. INSERT / OVERLAY / INSERT_OVERLAY registry-driven matrix 全部通過 Head/Tail、碰撞、零穿透、2D/3D/assembly、Save/Reload。
