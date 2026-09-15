# T11 Cabinet Family Preset Switching Contract

## 使用者確認的唯一切換規則

1. **已知盤型 → 已知盤型**：切到哪一型，就完整套用該型自己的 canonical preset；不得沿用或記住上一輪該 family 的人工 runtime 編輯值。
2. **已知盤型 → 自訂**：自訂沒有 factory preset，直接沿用切換當下目前值，作為自訂起點。
3. **自訂 → 已知盤型**：重新套用目標已知盤型 canonical preset；自訂值不得倒灌已知盤型。
4. `Project Save/Reload`、3D live snapshot apply、一般 redraw/refresh **不是盤型切換事件**，不得因此重套 fresh preset 或洗掉已保存專案狀態。
5. Main 2D 與 3D Designer 必須使用同一份 known-family preset source；不得一邊用 factory defaults、一邊用 last runtime cache。
6. 供 3D 切換使用的 known-family runtime preset metadata 只存在執行期，**不得序列化進 `.p6fold`**。
7. `config.ini` 不因盤型切換而修改。

## 目前已知盤型

- 金庫型：使用主 GUI 啟動時已確立的 canonical Vault preset（含 settings / structure / topology state）。
- 受電箱：以 canonical base preset 為基底，再由 `ae_engine.cabinet_types.receiving.apply_family_defaults()` 套用 Receiving family defaults（目前 W/H/D = 800/1600/350、FW=29，以及 Receiving 固定結構與 door layout）。
- 自訂：不是 known family preset；只有它採 carry-forward semantics。

## 禁止

- 禁止 `_cabinet_family_runtime[family] = current_edits` 這類「離開時保存、切回時恢復」已知 family session cache。
- 禁止把「只有自訂沿用」誤寫成「所有 family 共用 W/H/D/T」。
- 禁止 3D 從 Receiving 切回 Vault 時只改尺寸卻保留 Receiving `three_piece_side_back_split` 結構。
- 禁止將 `_runtime_family_presets` 寫入 project snapshot。

## 驗收

- Vault → Receiving：套 Receiving preset。
- Receiving 人工修改 → Vault：套 Vault preset，不保留 Receiving edits。
- Vault 人工修改 → Receiving：仍套 Receiving preset，不保留上一輪 Receiving edits。
- Known → Custom：W/H/D/T/FW 等當下值保留。
- Custom → Known：重套目標 known preset。
- 3D Receiving → Vault：尺寸、FW、assembly intent、box-body structure、multi-door/inner-door topology 一起回 Vault preset。
- Save/Reload round-trip 保存專案當下 state，不受 fresh family preset 干擾。
