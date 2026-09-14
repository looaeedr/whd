# #204 T0 Preflight Evidence

[當前角色：T0 實作者]

Production baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
Work branch: `refactor/gui-modularization-20260914`

## Process / Skill evidence

- READ_SKILL: UI設計與去AI味
- READ_SKILL: monitoring-remote-qa
- READ_SKILL: long-log-context-safe-execution
- READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / dispatch / remote-QA / long-log gates

## Required reference evidence

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md

Relevant constraints carried into T0/T1:
- module split must reduce interface knowledge, not merely move methods or reduce `gui.py` line count;
- current authoritative state/geometry owners must not be duplicated by a second state store, renderer, bridge, or presentation-derived authority;
- upstream semantic identity must not be flattened to display strings across module seams;
- validation/test/golden/screenshot evidence judges correctness only and never becomes production calculation authority;
- branch-first, explicit ownership, Save→Reload, 2D/3D parity, physical-part identity, and invariant boundaries remain protected;
- remote QA is active-poll-to-terminal, with long logs handled by bounded slices/artifacts.

This file records read evidence only. It does not redefine manufacturing or UI authority.
