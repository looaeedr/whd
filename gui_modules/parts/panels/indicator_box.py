"""Indicator-box/indicator-door input configuration boundary; drawing remains T6."""


def collect_indicator_box_input(payload):
    """Copy existing indicator input values without deriving drawing or geometry."""
    return dict(payload or {})
