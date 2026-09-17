"""Door layout/input panel presentation and routing boundary.

Door-layout committed structures remain owned by the existing authoritative
host/controller seam during T4.
"""


def collect_door_input(payload):
    """Copy door presentation/input values without deriving topology or geometry."""
    data = dict(payload or {})
    result = {}
    for key in (
        "door_layout_columns",
        "door_layout_scope",
        "door_handle_edges",
        "model",
    ):
        if key in data:
            result[key] = data[key]
    return result
