# Box Body / EndCap 3D 干涉退讓設計

## 目的

本設計承接既有 `PartSpec -> PartRenderData` 製造幾何邊界，新增第一階段的 3D 干涉求解能力。範圍只包含：

```text
Box Body <-> EndCap / Tail
```

不處理 Door、Base Plate、Indicator Box，也不改 GUI 或 3D renderer 的製造 ownership。

核心決策：

```text
Box Body = RETAIN
EndCap / Tail = CUT
```

也就是箱身幾何保留，封頭與封尾依實際裝配干涉產生 relief。這是現有金庫型 EndCap relief 的自然演進：從固定 2D 公式，升級為由 3D 裝配事實反推 2D CUTTING。

---

## 現況

目前程式已有幾個必須保留的 seam：

- `manufacturing_api.resolve_endcap_request()` 是 EndCap 的 PartSpec / Fold Profile / CornerType 正規化入口。
- `manufacturing_api.build_part_render_data()` 是 2D、3D、DXF 共用的已解析製造幾何出口。
- `phase6_final_scene_view.py` 只消費 `PartRenderData`，不得解析 CornerType、重建 CUTTING 或呼叫製造引擎。
- `gui.py::_authoritative_render_data()` 是 GUI 內部唯一 render provider。
- 現有 EndCap / Box Body relief 仍主要是 2D Shapely difference 與規則式 CornerType composition，尚未有真正 collision / interference solver。

因此，新 solver 不能成為與 `PartRenderData` 競爭的第二套幾何真值。它必須在 `ae_engine` 製造解析流程內部工作，最後仍輸出同一份 `PartRenderData`。

---

## 新增 Module

第一階段建議新增：

```text
ae_engine/assembly_collision.py
```

這個 Module 的 Interface 只接受已解析製造資料，不接受 GUI state、Canvas 座標或 Fold Designer draft。

概念 Interface：

```python
def solve_boxbody_endcap_relief(
    *,
    box_body: PartRenderData | BoxBodyStructureRenderData,
    endcap: PartRenderData,
    box_body_profile: tuple[FoldProfileSegment, ...],
    endcap_x_profile: tuple[FoldProfileSegment, ...],
    endcap_y_profile: tuple[FoldProfileSegment, ...],
    ownership: AssemblyOwnershipPolicy,
) -> EndCapReliefSolution:
    ...
```

實作名稱可調整，但責任必須固定：

1. 從已解析 material + fold guides 建立求解用 3D solid / 2.5D solid。
2. 檢查 Box Body 與 EndCap/Tail 的 assembly collision。
3. 產生 collision region。
4. 套用 ownership：Box Body retain，EndCap/Tail cut。
5. 將 cut region 反投影回 EndCap/Tail 2D material plane。
6. 產生 relief candidate。
7. 回傳可套用到 EndCap/Tail CUTTING 的結果。

---

## 3D Solid 策略

第一版不引入完整 CAD kernel。採用 2.5D solid：

- 由 `PartRenderData.material` 取得 2D material polygon。
- 由 Fold Profile 與 `fold_guides` 折成裝配位置。
- 板厚以簡化 prism / swept surface 表達，足以判斷箱身與封頭/封尾的實體重疊。

這個模型只用於 collision solving，不取代 `phase6_final_scene_view.py` 的顯示 mesh。

原因：

- 現有 renderer 已明確是 consumer，不應變成 manufacturing solver。
- 2.5D solid 可先驗證 ownership、反投影與求解迴圈，不需要一次引入沉重 CAD dependency。
- 若未來需要曲面、折彎半徑或更精確厚度，可以在此 Module 內替換 implementation，而不改外部 Interface。

---

## Pipeline

第一階段資料流固定為：

```text
PartSpec / Fold Profile / CornerType
        ↓
AE resolver
        ↓
Nominal EndCap/Tail PartRenderData
Box Body PartRenderData
        ↓
assembly_collision solver
        ↓
EndCap/Tail ReliefCandidate
        ↓
套回 EndCap/Tail CUTTING
        ↓
重建 EndCap/Tail PartRenderData
        ↓
再做 collision verification
        ↓
PASS 或回報 solver failure
```

下游 GUI、3D renderer、DXF exporter 仍只消費最後的 `PartRenderData`。

---

## Ownership Policy

第一版 ownership policy 寫死為窄範圍 Factory Policy，不做全域通則：

```text
Box Body role: RETAIN
EndCap/Tail role: CUT
```

禁止把此規則推廣到 Door、Base Plate、Indicator Box 或未知箱型。

未來若新增第二箱型，必須以新的 Factory Policy 明確宣告 ownership，不能沿用金庫型或本階段預設。

---

## Relief Candidate 約束

Relief candidate 必須同時滿足：

- 製造 gap：collision region 外擴指定 clearance。
- 最小切除：不得因數值雜訊切出碎片。
- RETAIN 約束：不得改動 Box Body material。
- CUT 約束：只能修改 EndCap/Tail material。
- EXTRA_CUT 偏好：若候選切除落在既有多切方向，優先擴大既有 relief，而不是新增孤立小切口。
- 組合方式約束：INSERT、OVERLAY、INSERT_OVERLAY 不得被 solver 反向改寫；solver 只能切 material，不能改 CornerType 語意。

第一版可先只支援 rectangular / orthogonal relief candidate，因為目前 EndCap relief 與 Box Body 結構都是正交板件關係。

---

## 驗證策略

先寫 failing tests，再改 production code。

最低測試：

1. Box Body 與 nominal EndCap/Tail 在已知案例產生 collision region。
2. `Box Body = RETAIN`：求解前後 Box Body `material.bounds` 與 scene CUTTING 不變。
3. `EndCap/Tail = CUT`：求解後 EndCap/Tail material 面積減少，且 CUTTING 包含 relief。
4. Relief candidate 可反投影回 EndCap/Tail 2D plane，且不產生 invalid polygon。
5. 重建後再跑 collision verification，結果 pass。
6. solver failure 必須是明確錯誤，不得靜默輸出仍撞的 DXF。
7. `phase6_final_scene_view.py` 測試保護 renderer 仍不呼叫 solver 或解析 CornerType。

---

## 不做事項

第一階段不做：

- 不改 GUI 操作流程。
- 不改 `phase6_final_scene_view.py` 成 solver。
- 不導入完整 CAD kernel。
- 不支援所有板件通用 collision。
- 不改 Door / Base Plate / Indicator Box。
- 不改 project file schema。
- 不刪除既有 EndCap 2D relief；新 solver 先作為 EndCap/Tail assembly relief 的下一層求解能力。

---

## 完成定義

第一階段完成時必須成立：

- collision solver 只存在 `ae_engine` 製造邊界內。
- Box Body retain / EndCap cut 有測試保護。
- 最終 2D、3D、DXF 仍消費同一份 `PartRenderData`。
- EndCap/Tail 的 relief 不再只能靠預先推導公式表達，至少有一條測試案例由 collision region 反推 2D CUTTING。
- 若求解後仍撞，系統回報 failure，不輸出偽 PASS 幾何。
