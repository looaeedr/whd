---
name: 寫成規格書
description: 將目前對話整理成工程／產品規格，但必須先以 current codebase、AI Library、既有規格、測試與 certified data 做 grounding；共享尺寸與機械語意需跨 Family 查證，不能把現況、測試或 probe 當成產品真值。
disable-model-invocation: true
---

# 寫成規格書

把已確認的需求與專案證據整理成可施工規格。**不得只靠聊天記憶寫 WHD 規格。**

## Mandatory pre-spec gate

寫任何產品／工程規格前，先檢查受影響領域的 current repository。至少交叉讀：

1. 真正擁有該行為的 production code。
2. 相關 AI Library / SOP。
3. 同語意區域的既有 spec / design note。
4. 現有 tests。
5. 有則讀 fixture / baseline / certified data。

WHD geometry、CAD、2D、3D、DXF、Fold、assembly、placement、collision、relief、dimensions 一律不可跳過。

## 共享語意 scope gate

在定義 `FW`、`W/H/D`、`T`、CornerType、assembly intent、formed/material dimensions 等共享語意前，先判定 scope，不可因目前 bug 在單一 Family 就把共享詞定義成 Family-local。

至少沿整條 ownership chain 查：global glossary → Family adapter/conversion → Box Body → Door → Head/Tail/EndCap → Divider/child part → Fold Profile/material conversion → 2D/3D/DXF/FinalScene → Save/Reload schema → 跨 Family tests/fixtures。

Family-specific value/conversion 不是共享詞的定義；UI 位置也不是新 semantic layer。比如值位於「3D 輸入區」，只能說那是 input surface，不代表產生新的「3D 語意」。

## Evidence classification

每個重要事實先分類：

- **CONFIRMED PRODUCT RULE** — 使用者確認或 authoritative project rule。
- **CURRENT IMPLEMENTATION** — current code 行為，可能錯。
- **CURRENT TEST ORACLE** — current test assertion，可能錯。
- **PROBE / DIAGNOSTIC VALUE** — 診斷值。
- **HYPOTHESIS** — 尚未證明的解釋。
- **OPEN / UNRESOLVED** — 尚未定義清楚。

只有 **CONFIRMED PRODUCT RULE** 可直接升格為 normative product behavior。不能因 implementation/test/probe 可重現或 PASS，就把它寫成產品規格。

## WHD mechanical rule

定義 placement、relief 或 dimensions 前，先確認真實物理關係：

- 哪些 formed faces mate / flush / enter / wrap；
- 哪些數字是 operator outside / formed / material dimensions；
- datum 由哪個 part 擁有；
- current code 如何近似該關係。

不得從 variable name、origin、bbox、renderer offset 或現有 placement constant 反推產品真值。若實體關係未解，標 `OPEN / UNRESOLVED` 並繼續查，不可自行發明 datum。

## Source priority

1. 使用者已確認的 mechanical / product rule。
2. authoritative AI Library / SOP / certified geometry source。
3. current production code。
4. current tests。
5. probe / diagnostics。
6. historical notes / stale fixtures。

Passing tests 不得覆蓋已確認 mechanical rule。

## Process

1. 完成 mandatory pre-spec gate。
2. 對每條需求建立 source / implementation / test / conflict map。
3. 優先選最高 existing user-path / integration seam 做現況驗證。
4. 只從 confirmed product rules 寫 normative requirement。
5. current coordinates、collision values、probe outputs、stale expectations 放在 **Current State / RED Evidence**。
6. 每個 normative numeric value 都要交代 authority。
7. 規格保留 AI Library traceability。
8. 最後再檢查一次，確保 hypothesis/diagnostic 沒被寫成固定 oracle。

## Required spec structure

### Problem Statement
### Confirmed Product Rules
### Current State / RED Evidence
### Solution
### User Stories
### Implementation Decisions
### Testing Decisions
### Out of Scope / Open Items
### Evidence / Traceability

## Failure conditions

下列任一成立，規格尚未完成：

- 沒先讀 owning production code；
- 沒讀相關 AI/SOP；
- 把 passing test 當 mechanical truth；
- 把 probe value 寫成 fixed requirement；
- 從 Z=0、D/2、bbox center、renderer origin 猜 datum；
- 未解實體關係被自行補成答案；
- shared term 只查單一 Family；
- Family representation 被當 global definition；
- cross-Family evidence 未查；
- 驗證資料被反向拿去決定 production 計算。
