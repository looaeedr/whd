# DM6 / T1 Preflight Evidence

Task: DM6 / T1 Annotation Semantic Identity Contract + RED guards
Owning Issue: #65
Work branch: `work/dm6-t1-annotation-semantic-contract`
Dispatch base: `f465dffabc7c381eef106d7d3dc24a22ba2c72c9`

READ_SKILL: `.agents/skills/engineering/派工/SKILL.md`
READ_SKILL: `.agents/skills/engineering/拆解任務工單/SKILL.md`
READ_SKILL: `.agents/skills/engineering/掃描深模組/SKILL.md`
READ_SKILL: `monitoring-remote-qa`
READ_SKILL: `superpowers/test-driven-development`
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md

Requirement authority:
1. Current approved DM6 spec: display text/label is presentation only, never engineering identity.
2. Current production evidence: `drawing_annotation_layout.py` reconstructs callout/dimension ownership from text/label and distance.
3. AI Library historical guidance remains subordinate to current approved requirement.

Validation boundary: tests/expected values judge production only; they are never production semantic or geometry inputs.
