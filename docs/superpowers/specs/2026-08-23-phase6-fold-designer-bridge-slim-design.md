# Phase6 Fold Designer Bridge 瘦身設計規格

## 目標

讓 `fold_designer_bridge.py` 回到 adapter 角色：負責把原始 Fold Designer 與 Phase6 主流程接起來，不再擁有 CornerType/EndCap FW/Fold Profile 的機械語意。

## 已核准 seam

1. **EndCap 狀態語意 seam**：`phase6_endcap_semantics.py`
   - `CornerTypeSelection` JSON-safe raw codec。
   - 箱體 assembly type 從 Head/Tail 上方 CornerType 推導。
   - assembly type 套回 raw corner state。
   - Head/Tail FW follow/override 狀態與有效 FW 解析。
   - UI label mapping 僅是這個語意的顯示對照。

2. **Fold Profile seam**：`phase6_fold_profiles.py`
   - 箱身 Fold Profile 建立/讀回/merge。
   - EndCap X/Y Fold Profile 建立/讀回。
   - linked EndCap mating chain。
   - outside-dimension compensation。
   - profile ↔ `FoldProfileSegment` adapter。
   - profile clone、角度/長度 UI 轉換與結構刪除規則。

3. **Fold Designer Bridge seam**：`fold_designer_bridge.py`
   - `Phase6FoldDesignerApp`、Tk monkey patch、designer transaction、scene/view adapter。
   - 可為舊 caller re-export 已移出的名稱，但不得再實作其規則。

## 所有權規則

- `gui.py` 不得再從 `fold_designer_bridge` 取得 EndCap/Fold domain functions；它直接 import 真正 owner。
- `fold_designer_bridge.py` 不得再定義已移出的 EndCap/Fold domain functions。
- Bridge compatibility re-export 只能是 import alias，不得有 wrapper body 或第二套分支。
- `phase6_endcap_semantics.py` 不 import Tk、GUI、renderer、ProjectSession、SettingsService。
- `phase6_fold_profiles.py` 不 import Tk、GUI、renderer；只依賴 EndCap semantics 與 AE contract type。
- 不變更 `.p6fold` schema，不變更使用者操作，不變更幾何公式。

## 相容策略

既有測試與外部程式可能仍使用：

```python
import fold_designer_bridge as bridge
bridge.build_linked_endcap_xy_profiles(...)
```

本輪保留這些名稱的 re-export，因此外部介面不破壞；新 production caller 必須改用 owner module。

## TDD 契約

- EndCap semantics 直接 module interface 與 bridge compatibility export 結果一致。
- Fold Profile 直接 module interface 與 bridge compatibility export 結果一致。
- linked 5-segment / arbitrary 20-segment mating chain 行為完全不變。
- OVERLAY EndCap X profile 仍只有 `endcap_w_flat`，無虛構 X bend。
- `gui.py` ownership guard：domain names 不得從 Bridge import。
- Bridge ownership guard：已移出 domain functions 不得在 Bridge 重新 `def`。

## 不做

- 不拆 3D renderer functions。
- 不重寫 `Phase6FoldDesignerApp` monkey patch 結構。
- 不改 Project/Settings/Workspace Controller。
- 不做 `.p6fold` schema 升版。
