---
name: receiving-base-no-manual-shrink
description: Receiving BasePlate operator controls must not expose manual shrink values
---

# Receiving BasePlate — source only physical geometry

- Hide all four receiving-only manual shrink inputs in the live settings panel.
- The source-based physical `shrink_*` dimensions are structural, not operator-editable preferences. Never zero or discard these on save/load: EAR slots, PAD, source blank, 2D/3D and DXF rely on them.
- Do not change the common BasePlate settings for non-receiving cabinet families.
- Keep legacy project roundtrips and manufacturing validations intact; do not broaden NC authorization.
- Test actual Tk widget tree and source semantics before merging to localX. Production X only via explicit /推推.
