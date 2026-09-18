---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue #329 — UI UX Pro Max → WHD canonical UI skill

- owning issue: https://github.com/looaeedr/whd/issues/329
- target: `cleanup/2d-3d-sync`
- frozen base/head before write: `7de32d6c53864ae48b276d4817f4a00e3baaa846`
- work branch: `skill/issue329-ui-ux-pro-max-20260918`
- worker: `chatgpt-gpt5.6-sol`
- upstream inspected: `nextlevelbuilder/ui-ux-pro-max-skill@15de38fb70bc80ae9276fa7703b48ae861a672e6`
- upstream canonical skill: `.claude/skills/ui-ux-pro-max/SKILL.md`

## Knowledge preflight

REQUIRED_SKILL: UI設計與去AI味
REQUIRED_SKILL: 寫技能
REQUIRED_SKILL: phase6-release-packaging
REQUIRED_SKILL: monitoring-remote-qa
REQUIRED_SKILL: long-log-context-safe-execution
REQUIRED_SKILL: executable-continuity-controller

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md

## RED

Baseline lacks both the UI UX Pro Max registry aliases and the pinned canonical upstream marker, so the new contract is intentionally RED on the frozen base.

## Design decision

Do not create a competing `ui-ux-pro-max` CURRENT skill. Integrate it as capability-checked external design intelligence under WHD's existing canonical `UI設計與去AI味` authority, then filter through WHD's Tkinter/ttk, functionality-first, domain-preservation and real-GUI acceptance rules.

## Intended changed files

- `.agents/skills/engineering/UI設計與去AI味/SKILL.md`
- `.agents/skills/skill_registry.json`
- `tests/test_ui_design_de_ai_skill_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- this evidence file

## Verification

- QA workflow: `.github/workflows/qa-issue329-uiux-skill.yml` (one-shot; removed in closing cleanup)
- fresh RUN: `35293770834`
- exact tested HEAD: `5db23727a0c55d45853fdbb9788b9a83db051eab`
- job: `105441960672 / focused-contract`
- terminal result: **SUCCESS**
- focused UI + Skill governance contracts: **45 passed in 0.47s**
- changed-file Phase6 Knowledge Preflight: **GREEN**
  - required Skills: `寫技能`, `UI設計與去AI味`, `phase6-release-packaging`, `monitoring-remote-qa`, `long-log-context-safe-execution`, `executable-continuity-controller` all ✓
  - required References: global pitfall ledger, AI08, release manifest, long-log pitfall, continuity-controller pitfall all ✓
- exact-head identity step: SUCCESS
- one-shot workflow cleanup: performed in the same closing commit that updates this evidence
- cleanup commit: `b0713c3a33485292980217d90f0885f89a6a4936`
- tested-head → cleanup-head drift audit: **PASS** — only `.github/workflows/qa-issue329-uiux-skill.yml` removal + this verification evidence changed; canonical Skill / Registry / contract test / AI08 are byte-identical to tested HEAD.
- base → cleanup-head diff: exactly five durable files remain; the one-shot workflow is absent.

