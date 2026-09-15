# Phase6 Preflight Keyword Boundary 踩坑

## 問題

`tools/phase6_skill_preflight.py` 曾直接使用：

```python
keyword.lower() in task_text
```

比對 Registry keyword。當 route 含短英文 keyword `UI` 時，普通單字 `guidance` 也會因內含 `ui` 而誤命中 `UI設計與去AI味`，造成不相關 Skill 被要求、Preflight 假紅燈。

## 根因

短英文縮寫被當成任意 substring，而不是獨立 token。這類風險不只 `UI`，也包括 `UX`、`3D`、`MCP`、`DNS` 等短 ASCII acronym-like keyword。

## 永久規則

1. 短 ASCII acronym-like keyword（目前 matcher 定義為長度 `<= 3`、ASCII alnum，且原 Registry keyword 含大寫字母或數字）必須使用 ASCII token boundary matching。
2. `guidance` / `build` / `suite` 之類較長單字內部的字母片段不得觸發 `UI`。
3. 真正獨立 token 仍必須命中，例如 `UI design`、`UX review`、`3D geometry`。
4. 中文 keyword、多字英文 phrase、一般 lowercase keyword 不因這次修正全面改成 word-boundary；避免一次 bugfix 改寫整個既有 routing semantics。
5. `required_skills_for()` 與 `required_references_for()` 必須共用同一 keyword matcher，禁止兩條路徑各自實作造成 drift。
6. 每次修改 Preflight matcher 必須同時保留 should-not-trigger 與 should-trigger regression，並跑既有 `tests/test_phase6_skill_preflight_gate.py`。

## 回歸證據

Issue #183：`tests/test_issue183_preflight_keyword_boundaries.py`

- `DM7 navigation durable guidance` 不得要求 `UI設計與去AI味`。
- `UI design review` / `UX review` 仍要求 `UI設計與去AI味`。
- `3D geometry review` 仍要求 `phase6-corner-3d-model-integrity`。

## 禁止的修法

- 不要刪掉 Registry 的 `UI` keyword 來躲過 bug；那會破壞真正 UI 任務的 routing。
- 不要要求任務描述避用 `guidance`、`build`、`suite` 等正常英文單字。
- 不要對所有 keyword 一刀切成同一 regex 規則，除非另有規格與完整 migration regression。
