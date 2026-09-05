---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use /tdd where possible, at pre-agreed seams.

## Phase6 執行硬閘門
若任務位於 Phase6 / CAD 專案，執行時必須同時遵守 `.agents/skills/engineering/派工/SKILL.md` 的 durable checkpoint、process-group、Xvfb ownership、timeout classification、journal/resume 與 checkpoint provenance 規則。不得從聊天文字或 mtime 重建進度。

- 每張已驗收工單要有實體 checkpoint；長回歸前若已有未封裝修改，先封 checkpoint。
- fresh extract、restore、工具回合重建或手動複製檔案後，先驗 execution-tree fingerprint；若與最近已驗收 checkpoint 不符，視為混合狀態，完整還原 checkpoint 後再續工。
- GUI targeted gate 若 pytest 已有完整 PASS summary 但 Tk/Xvfb/interpreter 不退出，分類為 `complete_teardown_timeout`；只有點號或局部百分比則為 `incomplete_timeout`。timeout 本身不得直接判 production failure。
- incomplete batch 必須縮到未完成 nodeid；已完成節點禁止為方便而重跑。
- 任務尚未完成時，每 30 秒至少回報一次目前工單、正在做的事項、最新測試/進度數字與阻塞狀態；回報不得成為停工點，且不得中斷正在執行的任務。若單一不可中斷工具呼叫超過 30 秒，返回控制權後立即補報，不得為了回報頻率中止正常程序。

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

若目前來源不是 Git repository，Git/commit 步驟直接跳過，不得為了滿足形式硬造 repository；checkpoint + SHA/provenance 仍必須完成。若是 Git repository，才 commit 到目前工作分支。
