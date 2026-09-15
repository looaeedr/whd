# FIX11 Fold Designer Part Bundle Design

## Scope
- Keep the user's original `fold_designer_original.py` input behavior and Renderer unchanged.
- Phase6 only adapts data into/out of the designer.
- Carry all currently existing Phase6 parts into the designer, including their hole/feature data.
- Initial designer selection follows the part that was active before opening when possible.
- Unknown model uses the same rules.
- If no part exists, create one default `box_body` entry.
- Missing known parts can be added from the designer.
- `D-W-D` identities are fixed only inside the box-body profile; their values remain editable.
- The duplicate designer hole-editing tab is hidden; hole data is still loaded into the original state so the unchanged Renderer can display supported circle/rect holes.
- CornerType stays in Phase6 and is not moved into the designer.

## Existing-part rule
Primary Phase6 parts are `box_body`, `head`, `tail`, `door`, `base_plate`. Optional `indicator_box` and `indicator_door` are carried when their current Phase6 state/data exists. If a stored designer bundle already exists, its explicit part order/presence is preserved and refreshed from current Phase6 values.

## Data safety
- Raw Phase6 feature objects are preserved losslessly in the bundle.
- The original renderer preview gets a read-only projection of circle/rect features into its `state.holes`; unsupported profile features stay in the bundle and are not discarded.
- Opening and closing the designer without edits must not change Phase6 manufacturing values or feature lists.
