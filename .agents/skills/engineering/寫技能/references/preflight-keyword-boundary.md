---
whd_doc_role: REFERENCE
whd_contract: skill-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Preflight Registry Keyword Boundary Rule

這份 **REFERENCE／非執行權威** 屬於 `寫技能` 的 Registry keyword routing 防錯方法。當工作涉及 `.agents/skills/skill_registry.json`、`tools/phase6_skill_preflight.py`、trigger accuracy、route over-trigger / under-trigger 時讀取；現行來源只認 GitHub `localX` exact HEAD 的 `AGENTS.md`、CURRENT Skill／Registry。`phase6_skill_preflight.py` 是相容診斷器，不得把其 missing evidence／exit code 當成 Git／施工／PR／CI／DC 的授權或阻擋前置。

## Contract

- Registry route 的 keyword matching 必須避免「短英文縮寫在較長單字內被 substring 誤命中」。
- 短 ASCII acronym-like keyword（例如 `UI`、`UX`、`3D`、`MCP`、`DNS`）使用 token boundary；不得因 `guidance` 內含 `ui` 就觸發 UI Skill。
- 真正獨立 token 必須保持可觸發，例如 `UI design`、`UX review`、`3D geometry`。
- 中文 keyword、多字 phrase、一般 lowercase keyword 保持既有 routing semantics。對特定易誤觸的 lowercase keyword（如測試 `mock` 對 UI `mockup`），只有在 Registry 該 route 明列 `boundary_keywords` 時才採 token boundary；不可全域改變其他 keyword 語意。
- `required_skills_for()` 與 `required_references_for()` 共用同一 matcher；禁止兩套匹配邏輯漂移。
- 修 matcher 必須建立近似 negative cases + positive cases，並跑 `tests/test_issue183_preflight_keyword_boundaries.py`、`tests/test_phase6_skill_preflight_gate.py` 及受影響路由契約；無可用執行器就標 `TARGETED_NOT_RUN`、交由 exact-head GitHub CI，不虛構本地結果。
- 不得靠刪除合法 Registry keyword 或要求使用者避開正常字彙來掩蓋 matcher bug。

Canonical pitfall：

`個人AI檔案庫/踩坑庫/preflight_keyword_boundary_pitfall.md`

Permanent regression：

`tests/test_issue183_preflight_keyword_boundaries.py`
