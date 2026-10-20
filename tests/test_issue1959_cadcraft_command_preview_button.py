"""#1959 WHD Hole Editor opt-in CADCraft CLI command drawing entry."""
import ast
from pathlib import Path

import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
    Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_command_preview_bridge import (
    find_cadcraft_cli, prepare_whd_cadcraft_commands,
    draw_whd_commands_with_cadcraft,
)
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError


def _sample():
    surface=feature_surface_from_rect(
        "1959",Vec2(-100,-100),Vec2(200,200))
    features=[
        CircleFeature(10,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(25,30)),
        RectFeature(20,12,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(70,45),
                    rotation_deg=90),
        ProfileFeature(
            (Vec2(-20,5),Vec2(-7,4),Vec2(-5,16),Vec2(-24,20)),
            FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(0,0)),
    ]
    return surface,features


def test_opt_in_adapter_resolves_only_original_whd_finished_face_holes():
    surface, features=_sample()
    frozen=tuple(features)
    instructions=prepare_whd_cadcraft_commands(
        surface=surface,features=features,width=300,height=300)
    assert [i.kind for i in instructions]==["circle","rectangle","profile"]
    assert instructions[0].points == ((25.0,30.0),)
    assert instructions[1].points==(
        (76,35),(76,55),(64,55),(64,35)
    )
    assert instructions[2].points[0]==(-20,5)
    assert tuple(features)==frozen


def test_unknown_process_and_invalid_surface_are_rejected_before_cli():
    surface,features=_sample()
    features[0]=CircleFeature(10,FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                               Vec2(25,30),layer="BLIND_HOLE")
    with pytest.raises(CadcraftCommandProofError,match="CUTTING_HOLES_ONLY"):
        prepare_whd_cadcraft_commands(surface=surface,features=features,
                                       width=300,height=300)
    features[0]=CircleFeature(10,FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                               Vec2(500,500))
    with pytest.raises(CadcraftCommandProofError,match="WHD_FEATURE_SURFACE_REJECTED"):
        prepare_whd_cadcraft_commands(surface=surface,features=features,
                                       width=300,height=300)


def test_installed_cli_explicit_path_and_no_automatic_download(tmp_path,monkeypatch):
    path=tmp_path/"cadcraft-cli.exe"
    path.write_bytes(b"test executable location, not real binary")
    assert find_cadcraft_cli(configured=path)==str(path)
    with pytest.raises(CadcraftCommandProofError,match="CADCRAFT_CLI_NOT_FOUND"):
        find_cadcraft_cli(configured=tmp_path/"not-installed.exe")


def test_new_drawing_runner_receives_whd_instructions_without_input_dxf(tmp_path):
    surface,features=_sample()
    instructions=prepare_whd_cadcraft_commands(
        surface=surface,features=features,width=300,height=300)
    called=[]
    def fake_runner(binary,items,output,preview):
        called.append((binary,items,output,preview))
        output.write_bytes(b"native-output-placeholder")
        preview.write_bytes(b"native-image-placeholder")
        return {"status":"PASS","geometry":[{"check":"PASS"}]}
    result=draw_whd_commands_with_cadcraft(
        instructions=instructions,executable="test-cadcraft-cli",
        output_dir=tmp_path,runner=fake_runner)
    assert len(called)==1
    assert called[0][0]=="test-cadcraft-cli"
    assert called[0][1] is instructions
    assert result.output_dxf.name=="whd-command-drawing.dxf"
    assert result.preview_png.name=="whd-command-drawing.png"
    assert not any(p.name.endswith(".p6fold") for p in tmp_path.iterdir())
    assert tuple(features)==tuple(_sample()[1])


def test_no_overwrite_and_no_fake_green(tmp_path):
    instructions=prepare_whd_cadcraft_commands(
        surface=_sample()[0],features=_sample()[1],width=300,height=300)
    output=tmp_path/"whd-command-drawing.dxf"
    output.write_bytes(b"old source must not be overwritten")
    with pytest.raises(CadcraftCommandProofError,match="REFUSE_TO_OVERWRITE"):
        draw_whd_commands_with_cadcraft(
            instructions=instructions,executable="dummy",output_dir=tmp_path)
    assert output.read_bytes()==b"old source must not be overwritten"
    output.unlink()
    with pytest.raises(CadcraftCommandProofError,match="CADCRAFT_GEOMETRY_PROOF_NOT_GREEN"):
        draw_whd_commands_with_cadcraft(
            instructions=instructions,executable="dummy",output_dir=tmp_path,
            runner=lambda *args: {"status":"FAIL"})


def test_gui_button_keeps_original_preview_and_runs_cli_off_tk_event_thread():
    view=ast.parse(Path("gui_modules/editors/hole_editor_view.py").read_text("utf-8"))
    composition=ast.parse(Path("gui_modules/editors/hole_editor_composition.py").read_text("utf-8"))
    def tokens(tree):
        return {n.value for n in ast.walk(tree)
                if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    vt=tokens(view)
    assert "CADCraft 試看" in vt
    assert "CADCraft 開孔編輯" in vt
    bodies=[n for n in ast.walk(composition)
            if isinstance(n,ast.FunctionDef) and n.name=="draw_new_cadcraft_picture"]
    assert len(bodies)==1
    calls=[n for n in ast.walk(bodies[0]) if isinstance(n,ast.Call)]
    assert any(isinstance(n.func,ast.Name) and n.func.id=="Thread" for n in calls)
    assert any(isinstance(n.func,ast.Name) and n.func.id=="prepare_whd_cadcraft_commands"
               for n in calls)
    assert any(isinstance(n.func,ast.Name) and n.func.id=="draw_whd_commands_with_cadcraft"
               for n in calls)



def test_actual_gui_launcher_opens_only_existing_isolated_dxf_via_argv(tmp_path):
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        open_cadcraft_hole_editor,
    )
    gui = tmp_path / "cadcraft.exe"
    gui.write_bytes(b"portable executable")
    exchange = tmp_path / "isolated-exchange.dxf"
    exchange.write_text("exchange placeholder", encoding="utf-8")
    captured = []
    process = object()

    def launch(argv):
        captured.append(argv)
        return process

    assert open_cadcraft_hole_editor(
        exchange, executable=gui, launcher=launch,
    ) is process
    assert captured == [[str(gui), str(exchange.resolve())]]
    with pytest.raises((OSError, ValueError)):
        open_cadcraft_hole_editor(
            tmp_path / "missing.dxf", executable=gui, launcher=launch,
        )
    with pytest.raises(CadcraftCommandProofError, match="EXCHANGE_INVALID"):
        wrong = tmp_path / "original-manufacturing.txt"
        wrong.write_text("not a valid exchange")
        open_cadcraft_hole_editor(wrong, executable=gui, launcher=launch)
    assert len(captured) == 1


def test_gui_launcher_failure_fails_closed_and_does_not_shell_fallback(tmp_path):
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        open_cadcraft_hole_editor,
    )
    exchange = tmp_path / "isolated.dxf"
    exchange.write_bytes(b"not opened")
    gui = tmp_path / "cadcraft.exe"
    gui.write_bytes(b"stub")
    def refuse(argv):
        assert argv == [str(gui), str(exchange.resolve())]
        raise OSError("Windows GUI process denied")
    with pytest.raises(CadcraftCommandProofError, match="CADCRAFT_GUI_LAUNCH_FAILED"):
        open_cadcraft_hole_editor(exchange, executable=gui, launcher=refuse)



def test_controlled_gui_launch_adds_local_tcp_arg_without_shell(tmp_path):
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        open_cadcraft_hole_editor,
    )
    gui = tmp_path / "cadcraft.exe"
    gui.write_bytes(b"test-only")
    exchange = tmp_path / "WHD-issued.dxf"
    exchange.write_bytes(b"test-only")
    argv = []
    def launch(command):
        argv.append(command)
        return object()

    open_cadcraft_hole_editor(
        exchange, executable=gui, launcher=launch, control_port=41991,
    )
    assert argv == [[str(gui), "--control", "41991", str(exchange.resolve())]]
    with pytest.raises(CadcraftCommandProofError, match="INVALID_CONTROL_PORT"):
        open_cadcraft_hole_editor(
            exchange, executable=gui, launcher=launch, control_port=0,
        )
    assert len(argv) == 1
