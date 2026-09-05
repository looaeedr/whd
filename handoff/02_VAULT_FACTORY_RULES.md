# 02 — Vault Factory Rules

目前確認的是**金庫型**規則，不是所有鈑金箱通則。

## End Cap / Tail

Top chain：`[ytop1, FW]`，`ytop1` 不可硬寫 16。

Primary relief：
- left X = `FW + abs(yl1)`
- right X = `FW + abs(yr1)`
- Y = `ytop1 + FW - T`

Secondary relief：
- left X = `abs(yl1) + 0.5T`
- right X = `abs(yr1) + 0.5T`
- depth = `2T`
- 直角階梯

Bottom relief：
- left/right X = `abs(side_fold) + 0.5T`
- Y = `ybottom1 + 0.5T`
- 無第二級

禁止恢復：
- `zl1/zr1 + FW + T`
- `side_fold - 0.5T`
- 固定 `+0.5 mm`

左右必須允許非對稱。

## 2026-08-17 CornerType 內部映射（輸出規則不變）

金庫型仍是固定 Factory Policy，GUI 不得讓使用者改 CornerType：

- Door / Indicator Box / Indicator Door → `C02 單邊留肉 1T`
- Base Plate → `C01 標準截角`
- End Cap/Tail bottom → `C03 雙向多切 0.5T`
- End Cap/Tail top → `C04 雙段截角`

舊式 `fold-T`、`fold+0.5T`、`fold+FW` 不再作為角類型公式直接散落於 adapter；現在由 Fold Geometry + CornerType residual 組合得到相同最終尺寸。`ReliefConfig` 僅保留為 Vault Factory Policy 的窄範圍 clearance override，不能把 Vault 規則推廣到未知箱型。
