---
name: to-spec
description: "Turn the current conversation into a spec only after grounding it in the current codebase, AI library, existing specs, and tests."
disable-model-invocation: true
---

This skill produces a specification from verified project evidence plus the current conversation.

Do NOT write a WHD specification from conversation memory alone.

## Mandatory pre-spec gate

Before writing any product or engineering specification, inspect the affected domain in the current repository.

At minimum, read and cross-check:

1. Current production code that owns the behavior.
2. Relevant AI library / SOP rules.
3. Existing specs / design notes for the same semantic area.
4. Existing tests that encode the behavior.
5. Relevant fixture / baseline / certified data when one exists.

For WHD geometry, CAD, 2D, 3D, DXF, Fold, assembly, placement, collision, relief, and dimensions, this gate is mandatory.

## Evidence classification

Classify every important fact before promoting it into the spec:

- **CONFIRMED PRODUCT RULE** — user-confirmed or authoritative project rule.
- **CURRENT IMPLEMENTATION** — what code currently does; may be wrong.
- **CURRENT TEST ORACLE** — what tests currently assert; may be wrong.
- **PROBE / DIAGNOSTIC VALUE** — runtime result used for diagnosis only.
- **HYPOTHESIS** — proposed explanation not yet proven.
- **OPEN / UNRESOLVED** — not yet sufficiently defined.

Only **CONFIRMED PRODUCT RULE** may be written directly as normative product behavior.

Never promote CURRENT IMPLEMENTATION, CURRENT TEST ORACLE, PROBE values, or HYPOTHESES into a product requirement merely because they are reproducible or currently passing.

## WHD mechanical rule

Before defining placement, relief, or dimensions, identify the real physical relationship:

- which formed faces mate / flush / enter / wrap,
- which numbers are operator outside / formed / material dimensions,
- which part owns the datum,
- which code path currently approximates that relationship.

Do not infer the product rule from variable names, origin coordinates, bbox values, renderer offsets, or existing placement constants.

If the physical relationship is unresolved, mark it OPEN / UNRESOLVED and continue investigation. Do not invent a datum.

## Source priority when evidence conflicts

1. User-confirmed mechanical / product rule.
2. Authoritative AI library / SOP / certified geometry source.
3. Current production code.
4. Current tests.
5. Probe outputs / diagnostics.
6. Historical notes / stale fixtures.

Passing tests do not override a confirmed mechanical rule.

## Process

1. Run the mandatory pre-spec gate.
2. Internally map each rule/question to:
   - authoritative source,
   - current implementation,
   - current test coverage,
   - conflict or gap.
3. Prefer the highest existing user-path / integration seam for validation.
4. Write normative requirements only from confirmed product rules.
5. Put current coordinates, collision values, probe outputs, and stale test expectations under **Current State / RED Evidence**.
6. Every numeric normative requirement must state why the value is authoritative.
7. Preserve AI-library traceability in the spec/work order/acceptance evidence.
8. Re-check that no hypothesis or diagnostic result was accidentally written as a fixed oracle.

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

The spec-writing task is not complete if:

- owning code was not read first;
- relevant AI/SOP rules were not consulted;
- a passing test was treated as mechanical truth without checking its source;
- a probe value was turned into a fixed product requirement;
- a physical face/datum was inferred from Z=0, D/2, bbox center, or renderer origin;
- an unresolved physical relationship was replaced with an invented datum.
