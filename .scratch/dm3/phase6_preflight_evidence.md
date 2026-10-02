# DM3 Phase6 Knowledge Preflight Evidence

Task: Issue #53 DM3 — Divider canonical relief、final material 與 placement datum 單源化
Branch: `work/dm3-divider-canonical-relief`
Base: `63810a32a371fde6e153089ca1c4f642ce535a54`

## Required skill verification

- VERIFIED_SKILL: phase6-corner-3d-model-integrity
- Read: `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
- Applied constraints: state/Assembly Intent → canonical relief → Final Material → true-thickness folded solid → 2D/single-3D/assembly-3D/DXF/NC/Save-Reload is one chain; legal contact is not penetration; pre-solve and post-solve evidence are both required; final retained material must verify zero illegal penetration; multi-piece BoxBody keeps piece-level physical ownership; renderer must not hide placement errors; config.ini must not drift.

## Required references

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- Key guards: Base Polygon - Relief Polygon = final material; geometry is single truth; do not use 2D bbox as formed geometry; FW remains independent Source of Truth; world-space collision lines alone are not manufacturing dimensions; restore/reference material cannot be promoted wholesale to production material; `174 / 121 / 47 / 26` are not product constants without physical datum proof.

READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
- Key guards: Registry HIT is canonical manufacturing relief; 3D discovery is only for MISS/candidate flow; dimension space must stay explicit; STANDARD and semantic delta remain authoritative. DM3 must not create a second relief formula authority.

READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
- Key guards: active certified rules retain their revision, topology/preconditions, target semantics, dimension space and geometry inputs. DM3 does not rewrite certified EndCap/WRAP formulas; it only canonicalizes Divider placement/relief/final-material ownership.

READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
- Key guards: certified results cannot be overwritten by 3D discovery; semantic TOP vs physical corner must be preserved; 3D backprojection candidates require flat UV and cut→refold verification; solved production material must start from authoritative original material and only apply actually solved relief deltas; final material is supplied through Manufacturing API to 2D/3D/DXF, not recalculated by renderer/exporter.

## DM3 hard constraints

- FW physical face / real formed geometry establishes legal placement first.
- Relief is solved only after placement evidence is valid.
- `verified=True` requires placement and collision evidence plus zero illegal penetration after solve.
- Real multi-piece BoxBody physical pieces remain collision authority.
- No fixed world Z, bbox center, `174`, `47/26`, 1mm probe oracle.
- `中隔.dxf` remains fixed holes/features source only, never final contour oracle.
- No renderer-only cut, exporter-only cut, GUI geometry patch, or duplicate relief state.
- D/FW/T changes must re-enter the same canonical solve.
- #48 T48-2 behavior remains regression authority.
- Formal AI Library / Skill authority writeback remains #55 scope.
