# Legacy 2D 入口退役踩坑（2026-09-10）

Marker: ISSUE100_LEGACY_2D_ENTRY_RETIREMENT_RULE

## 根因 / 風險
舊主 GUI 的 2D Notebook 不只是入口；部分新「截角資料」能力仍重用既有 renderer、annotation、hole editor、Door drag callbacks 與其初始化 state。若用「舊 2D」名稱直接整段刪除，會造成新入口看似存在但互動能力變成空殼。

## 正確做法
1. 先移除 user-reachable Notebook/tab navigation、return-to-legacy callback、Notebook-derived active-part/presence identity。
2. 仍被新 View 共用的 renderer/helper 必須保留。
3. 若 callback 尚需舊 Tk 初始化 state，可暫留 hidden compatibility host，但它不得 pack、不得成為 navigation surface、不得成為 geometry authority。
4. 主 `draw_preview()` 改成只刷新 visible authoritative corner-data View。
5. 驗收不只 source grep，還要在 Xvfb 真正開 GUI、進 Fold Designer「截角資料」，確認舊入口不可達且新入口可操作。

## #100 證據
- RED run 34484921499：7 failed / 1 passed；唯一先綠的是共用 T5 helpers preservation。
- Worker run 34485178700：40 passed；T7_LEGACY_ENTRY_UNREACHABLE=PASS、T7_LEGACY_NAV_DEPENDENCY=PASS。
- Final Acceptance run 34485950792：71 passed / 59 skipped / 1 warning；T7_LEGACY_ENTRY_UNREACHABLE=PASS、T7_DEAD_NAVIGATION_GATE=PASS、T7_T5_CAPABILITY_PRESERVED=PASS、T7_RUNTIME_NAVIGATION=PASS；config.ini 前後 sha256 皆為 980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67。
