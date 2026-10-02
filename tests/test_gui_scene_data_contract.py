from pathlib import Path


def test_gui_scene_data_consumers_use_params_attribute():
    source = (Path(__file__).resolve().parents[1] / 'gui.py').read_text(encoding='utf-8')
    forbidden = [
        "geom['params']",
        "geom_z['params']",
        "geom_door['params']",
    ]
    found = [token for token in forbidden if token in source]
    assert not found, f"GUI still uses removed SceneData dict contract: {found}"
