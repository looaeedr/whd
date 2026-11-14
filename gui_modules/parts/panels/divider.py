"""Divider input-panel presentation boundary; physical input belongs to Engine."""

from ae_engine import manufacturing_api


def collect_divider_input(part_key, payload, *, default_depth, default_thickness):
    """Forward the operator's Divider source to the public Engine contract."""
    return manufacturing_api.project_operator_fold_designer_divider_input(
        part_key, payload,
        default_depth=default_depth, default_thickness=default_thickness,
    )
