"""#1959 official CADCraft GUI: unsaved live hole returns to genuine WHD Session.

A native Linux/Xvfb experiment using a publisher-verified desktop executable.
This never opens a user's project or changes WHD manufacturing/DXF authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import ezdxf

from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_control_bridge import (
    CadcraftControlClient, CadcraftControlError,
)
from gui_modules.editors.cadcraft_live_return_bridge import (
    capture_unsaved_cadcraft_return,
)
from gui_modules.editors.cadcraft_manual_hole_return_bridge import (
    create_manual_return_ticket, stage_manual_cadcraft_return,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_cadcraft_tcp_native_probe import pick_port


def proof(executable: Path) -> dict:
    gui = Path(executable).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="whd-1959-live-native-") as dirname:
        root = Path(dirname)
        # The *only* file handed to CADCraft is a WHD-authored, disposable mm DXF.
        origin = root / "WHD-issued-open-holes.dxf"
        doc = ezdxf.new("R2010", units=ezdxf.units.MM)
        doc.modelspace().add_circle((40, 40), 5)
        doc.saveas(origin)
        original_file = origin.read_bytes()
        features = [CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40))]
        original_feature = tuple(features)
        session = Phase6HoleEditorSession("1959-native-live", features)
        surface = feature_surface_from_rect("1959-native-live", Vec2(0, 0), Vec2(200, 200))
        ticket = create_manual_return_ticket(
            output=origin, features=features, session=session,
            surface=surface, width=200, height=200,
        )
        port = pick_port()
        env = os.environ.copy()
        env["CADCRAFT_CONFIG_DIR"] = str(root / "vendor-profile")
        logs = root / "cadcraft-console.log"
        with logs.open("wb") as log:
            proc = subprocess.Popen(
                [str(gui), "--control", str(port), str(origin)],
                cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                client = CadcraftControlClient(port, timeout=3)
                deadline = time.monotonic() + 40
                opened = None
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("NATIVE_GUI_EXITED_BEFORE_OPEN")
                    try:
                        client.probe()
                        observed = client.inspect()
                        if observed.path and (
                            os.path.normcase(str(Path(observed.path).resolve()))
                            == os.path.normcase(str(origin.resolve()))
                        ):
                            opened = observed
                            break
                    except CadcraftControlError:
                        pass
                    time.sleep(0.3)
                if opened is None:
                    raise RuntimeError("NATIVE_GUI_DID_NOT_OPEN_ISSUED_DXF")
                if len(opened.entities) != 1 or opened.dirty:
                    raise RuntimeError("NATIVE_GUI_ISSUED_SOURCE_NOT_PRISTINE")
                # This occurs solely inside CADCraft's unsaved in-memory drawing.
                client.request("engine.execute", {
                    "command": "circle",
                    "params": {"center": [90, 95], "radius": 6},
                })
                observed = client.inspect()
                if len(observed.entities) != 2:
                    raise RuntimeError("NATIVE_GUI_UNSAVED_CIRCLE_NOT_DRAWN")
                if origin.read_bytes() != original_file:
                    raise RuntimeError("NATIVE_GUI_MODIFIED_ISSUED_DXF_ON_DISK")
                captured = capture_unsaved_cadcraft_return(
                    ticket, port=port, client=client, process=proc,
                )
                if origin.read_bytes() != original_file:
                    raise RuntimeError("LIVE_CAPTURE_OVERWROTE_ISSUED_DXF")
                pending = stage_manual_cadcraft_return(captured)
                if pending.moves or len(pending.additions) != 1:
                    raise RuntimeError("LIVE_CAPTURE_WRONG_SESSION_DIFFERENCE")
                pending.confirm()
                if not (
                    len(features) == 2
                    and features[1].offset == Vec2(90, 95)
                    and not session.has_active_edit
                ):
                    raise RuntimeError("LIVE_CAPTURE_SESSION_CONFIRM_FAILED")
                session.execute(HoleEditorAction.undo())
                if tuple(features) != original_feature:
                    raise RuntimeError("LIVE_CAPTURE_SESSION_UNDO_FAILED")
                return {
                    "status": "PASS",
                    "scope": "real official CADCraft GUI unsaved TCP document to WHD original Session",
                    "loaded_whd_issued_document": True,
                    "manual_cadcraft_save": False,
                    "disk_original_unchanged": True,
                    "live_native_entity_count": 2,
                    "new_holes_in_whd_session": 1,
                    "session_confirm": True,
                    "session_undo": True,
                    "manufacturing_dxf_written": False,
                    "windows_user_gui_uat": False,
                }
            except Exception as exc:
                log.flush()
                try:
                    tail = logs.read_text(encoding="utf-8", errors="replace")[-2200:]
                except OSError:
                    tail = ""
                raise RuntimeError(f"NATIVE_LIVE_RETURN_FAILED:{exc}; LOG_TAIL={tail}") from exc
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cadcraft", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = proof(args.cadcraft)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
