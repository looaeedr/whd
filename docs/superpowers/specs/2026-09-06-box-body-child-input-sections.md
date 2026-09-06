# T14 Box Body Child Input Sections

## Contract

Box Body child input sections are a UI projection of the already-authoritative physical Box Body pieces.

- Two-piece W split renders exactly:
  - `box_body:left`
  - `box_body:right`
- Three-piece W split renders exactly:
  - `box_body:left`
  - `box_body:middle`
  - `box_body:right`
- Receiving side/back split renders exactly:
  - `box_body:left_side`
  - `box_body:back`
  - `box_body:right_side`
- Every section stores the matching physical stable id as `_phase6_part_key`.
- Switching structure type rebuilds the settings page from current resolved pieces, destroying stale sections.
- Save/Reload rebuilds the same sections from persisted `box_body_structure_state`.
- There is no child-piece persistence model and no fake geometry. Inputs write the pre-existing canonical structure state.
- Shared seam / relief controls remain shared structure settings instead of being duplicated into one child piece.

## Acceptance evidence

Remote current-head QA run `34024564540`, head `094bb3b2c6a9be7791d5ef5b848785fb7e98a2be`:
- T14 structure + multipart guards: 14 PASS
- T15/T16/T17 guards: 16 PASS
- family + 2D/3D roundtrip guards: 20 PASS
- total: 50 PASS / 0 FAIL
- visual piece IDs == input section IDs
- `config.ini` before/after SHA256:
  `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
