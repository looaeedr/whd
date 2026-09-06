# T17 Receiving Inner Door / Frame Default 80 mm Datum

## Contract
Receiving inner-door panel and its frame are placed relative to the owning outer Door plane.

- Default inward offset: 80 mm.
- The direction is the T16 family coordinate contract `inward_vector`; consumers must not hard-code `Z-80`.
- Each enabled `inner_doors[]` item owns its own `inward_offset_mm`.
- Missing legacy value migrates to the Receiving family default.
- A user edit changes only that Door item's value.
- Project Save/Reload preserves the field because it is authoritative project state.
- Multi-door placement always resolves from the owning Door stable id and its own outer-door plane.

## Reference
For fresh Receiving W=800 H=1600 D=350 T=2:
- outer Door plane: Z=175
- default 80 mm inward: Z=95
