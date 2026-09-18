"""Multipart-specific input presentation boundary.

Accepted T3 navigation keeps stable physical child identity and top-level logical
selection semantics.
"""


def collect_multipart_input(payload):
    """Copy existing multipart presentation/input values without deriving state."""
    return dict(payload or {})
