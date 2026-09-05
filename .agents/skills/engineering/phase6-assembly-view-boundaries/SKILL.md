---
name: phase6-assembly-view-boundaries
description: Use when modifying Phase6 組合圖、3D assembly rendering、Assembly Joint、collision/relief diagnostics、operator status UI，或修正組合圖出現不該出現的診斷圖元與控制項時。
---

# Phase6 組合圖／診斷邊界

## 核心原則

**正式組合圖是操作員製造視圖，不是 Solver / Registry 的 Debug Console。**

Joint Registry、collision solver、legacy migration、pre/post penetration 等診斷資料可以存在於內部 `ResolvedManufacturingGeometry`，但不得因為資料存在就自動變成正式組合圖的線、箭頭、文字、下拉選單或狀態尾碼。

## 必守邊界

1. **正式組合圖只畫製造必要內容**：板件實體、正式折彎資訊、操作員要求的碰撞顯示、正式截角尺寸與必要狀態。
2. **Joint 診斷預設不進 operator assembly scene**：Registry status、preserve/relief、pre/post pair count、direction vector、penetration debug segments 等只留在專用診斷入口。
3. **不要用「刪 UI」代替「隔離診斷層」**：若問題是 debug overlay 混入正式視圖，修在 render/query 邊界；不得順手刪除原本正常的板件控制、尺寸、狀態、單板功能或其他無關 GUI。
4. **不要夾帶無關修正**：修組合圖診斷污染時，不得順手改 Door、Base Plate、單板 FinalScene、Save/Reload 或其他 production data path，除非它們有獨立失敗證據與獨立測試。
5. **Legacy / migrated Joint 是內部相容資料**：不能因為存檔內有 legacy Joint 就自動長出診斷圖層或工程用控制項。
6. **USER_ADDED Joint 仍保留完整求解能力**：診斷資料不得因 operator view 隔離而被丟失；需要查看時由專用 Registry / Joint 診斷入口查詢，不從正式組合圖偷渡。

## 修改前必做 Inventory

對同一份實際 `.p6fold` 記錄：

- 板件清單與數量；
- 組合圖可見控制項；
- 材料面積／piece 數；
- 3D triangle / edge 或等價幾何摘要；
- 碰撞線數與碰撞顯示開關；
- 截角尺寸文字；
- Joint diagnostics 數量只作內部資料檢查。

修改後逐項比對。**除本次明確要移除的診斷污染外，任何 operator 功能或幾何摘要減少都視為回歸。**

## 正確修法

當正式組合圖出現 Joint/Registry 雜訊時：

- 保留 solver / registry 的 diagnostics Source of Truth；
- 在 operator assembly adapter / render bundle 邊界阻止 diagnostics 成為正式 drawing layer；
- 專用 debug tooling 仍可直接讀 diagnostics；
- 不修改 canonical manufacturing geometry 來達成「看不到」。

## 驗收矩陣

交付前至少驗證：

- INSERT / OVERLAY / INSERT_OVERLAY，以及 registry 新增的任何 Assembly Intent；
- Head / Tail；
- 求解前碰撞顯示仍可用；
- 求解後零材料穿透；
- 2D / 單板 3D / 組合圖尺寸一致；
- Save / Reload；
- 使用者實際 `.p6fold`；
- 修改前後 operator UI inventory 沒有非預期減項；
- diagnostics 仍可從專用診斷入口查到，但正式組合圖不自動顯示。

## 禁止事項

- 因為畫面太亂就整段移除 Joint engine / registry。
- 為了隱藏 overlay 去改 material / FinalScene 幾何。
- 只看 screenshot、不比對 scene data 與 UI inventory。
- 一次同時改 operator view、Door 單板路徑、出包規則等互不相干區域。
- 測試只證明「雜訊消失」，卻沒證明原功能仍在。

## 3D 完整性聯動

只要本次組合圖修改同時動到截角、Joint、碰撞、material、Fold/placement 或 3D 幾何，必須再套用 `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`；operator/debug 分層通過不代表 3D 機械模型已通過。
