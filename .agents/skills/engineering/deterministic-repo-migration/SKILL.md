---
name: deterministic-repo-migration
description: Use when a repository-wide role, path, metadata, workflow, or governed artifact migration must be derived from an authoritative matrix/registry and applied completely, repeatably, and fail-closed without turning validation output into production authority.
whd_doc_role: CURRENT
whd_contract: deterministic-repo-migration
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Deterministic Repo Migration

## Purpose

Use this Skill for a **deterministic migration** whose source of truth is an **authoritative matrix/registry**. The migration must first discover the complete governed **scope inventory**, derive one deterministic target state from the authority, apply only that state, then prove **strict validation**, **idempotence**, and **drift audit** evidence.

This Skill is a repository/process migration contract. It does not own or redefine production geometry, DXF, or manufacturing truth.

## Authority boundary

The authoritative matrix/registry is the only source allowed to decide the desired migration mapping. A validator **must not** become the authority, must not infer missing production truth, and must not reverse-engineer a target state from observed validation results.

Validation answers only whether the generated repository state conforms to the authority. Validation evidence may reject a result; it may not feed new values back into the migration computation.

Out of scope:

- production geometry computation or correction;
- DXF dimensions, hole positions, folds, corner geometry, or manufacturing truth;
- replacing domain authorities with test fixtures, snapshots, or validator expectations;
- opportunistic cleanup outside the governed migration scope.

## Mandatory execution contract

### 1. Pin authority

Read the authoritative matrix/registry before changing files. Record its exact path/ref and **authority SHA**. If more than one candidate authority exists and precedence is not explicit, **fail closed**.

### 2. Build the scope inventory

Enumerate every governed artifact before mutation. Record the **governed inventory count** and the exact inventory. The scope inventory must be complete enough to detect both missing and unexpected artifacts.

Do not start rewriting while discovery is still incomplete.

### 3. Derive a total mapping

For every governed source identity, derive exactly one destination identity/role from the authority. Before applying changes, reject all of the following:

- **duplicate mapping**: one governed source or target has conflicting assignments;
- **missing mapping**: an in-scope governed artifact has no authority entry;
- **unknown role**: the authority names a role the migration implementation does not support;
- **nonexistent target**: the authority resolves to a target that cannot exist or is not present when existence is required.

Any one of these conditions must **fail closed** before mutation.

### 4. Apply deterministic changes only

Given the same repository input and the same authority SHA, the migration must compute the same ordered operations and same final bytes. Avoid timestamp-derived content, unordered iteration, heuristic role guessing, or validator-driven rewrites.

When content is copied or preserved by contract, verify required **byte-for-byte** identity rather than approximate semantic similarity.

Record the exact **changed-file set**. Any changed path outside the derived plan is a failure.

### 5. Strict validation

Run strict validation against the authority after migration. The validator may report invalid state but must not rewrite the authority or choose replacement values. Record the **validator result** and all rejected identities/roles.

A passing validator is necessary evidence, not a new source of truth.

### 6. Idempotence proof

Run the same migration a second time against the same repository state and **same authority input**. The required **idempotence result** is **zero diff**: no file content, path, metadata, or ordering change may remain.

For copied/preserved governed artifacts, compare required data byte-for-byte where the contract requires exact identity.

A second execution that modifies anything is a failure even if validation still passes.

### 7. Drift audit

Compare the tested state against the allowed changed-file set and the pinned authority. The **drift audit** must prove that no unrelated repository artifact moved and that authority/validator separation remained intact.

If a temporary QA workflow or harness was introduced, include its lifecycle in the drift audit and do not silently ship it as production behavior unless the owning issue explicitly requires that.

## T6 strict-metadata accepted handoff

For the #225/#233 knowledge-consolidation migration, the accepted T6 lineage uses the frozen T1 classification authority plus the explicit #255 deterministic resolution overlay. That pair is the migration input; **do not re-run classification heuristics** and do not reconstruct desired metadata from strict-validator failures.

Accepted T6-B evidence at migrated HEAD `2ef002cc6cc9476fc36eccbbe6b8b64acda6a777`:

- governed inventory: `398`, mapped: `398`, rejected/unmapped: `0`;
- second migration pass: `CHANGED_COUNT=0`;
- strict/focused validation: `29 PASS / 0 FAIL`;
- full `tests/knowledge`: `102 PASS / 0 FAIL`;
- remote QA: run `34905919429`, job `104182413876`;
- scope-external drift: `0`.

T7 and later governance work must consume this accepted strict-mode state. It may add permanent guards, but it must not silently reopen T1 classification or treat tests/validator output as a replacement authority.

## Evidence schema

A completion record for this Skill must include, at minimum:

- authority path/ref;
- **authority SHA**;
- **governed inventory count** plus inventory source;
- derived mapping count and rejected mapping count;
- exact **changed-file set**;
- first execution result;
- second execution / **idempotence result** proving **zero diff**;
- **validator result**;
- **drift audit** result;
- focused/remote QA run identity when remote QA is required;
- issue/branch/tested commit identities needed for readback.

Missing required evidence is fail-closed; do not report the migration complete.

## Applicability

### Positive applicability

Use this Skill when the desired repository state already exists as an explicit governed mapping, matrix, registry, catalog, manifest, or equivalent authority and the task is to migrate many files/roles/paths to that state deterministically.

Examples: role renames controlled by a registry, governed path relocation, metadata normalization from a manifest, or repository-wide mapping migrations with a defined target table.

### Negative applicability

Do not use this Skill to invent geometry, repair DXF/manufacturing truth, choose UI semantics, discover an unknown domain model, or infer desired values from failing tests. Those tasks require their own domain authority and validation Skills.

Do not use this Skill when the mapping itself is still a design question; resolve the authority first.

## Failure rules

- No authority SHA: fail closed.
- Incomplete scope inventory: fail closed.
- Duplicate mapping, missing mapping, unknown role, or nonexistent target: fail closed.
- Validator disagrees with authority: stop and diagnose; do not let validator become authority.
- Second execution is not zero diff: fail closed.
- Drift audit finds an unrelated change: fail closed.
- Production geometry, DXF, or manufacturing truth would need alteration: stop and route to the proper domain owner instead of extending this Skill.
