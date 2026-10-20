"""#1959 native CADCraft desktop TCP proof; isolated graphics and verified WHD geometry.

Run under a real Xvfb DISPLAY with the vendor's sha256-verified v0.8.0 binary.
Nothing here launches WHD GUI or writes manufacturing/canonical user files.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from gui_modules.editors.cadcraft_control_bridge import (
    CadcraftControlClient, CadcraftControlError,
)
from tools.issue1959_whd_cadcraft_command_draw import (
    demo_instructions, verify_dxf,
)


def pick_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def native_probe(executable: Path) -> dict:
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file():
        raise FileNotFoundError(str(executable))
    with tempfile.TemporaryDirectory(prefix="whd-1959-tcp-") as root:
        root = Path(root)
        env = os.environ.copy()
        env["CADCRAFT_CONFIG_DIR"] = str(root / "isolated-cadcraft-config")
        log_file = root / "gui.stdout.stderr.txt"
        port = pick_port()
        with log_file.open("wb") as log:
            proc = subprocess.Popen(
                [str(executable), "--control", str(port)],
                cwd=str(root), env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                client = CadcraftControlClient(port, timeout=2.0)
                deadline = time.monotonic() + 30
                catalog = None
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("CADCRAFT_GUI_EXITED_EARLY")
                    try:
                        catalog = client.probe()
                        break
                    except CadcraftControlError:
                        time.sleep(0.25)  # Only safe, read-only probes.
                if catalog is None:
                    raise RuntimeError("CADCRAFT_CONTROL_NOT_READY")
                # The vendor's 'new' command accepts metric=true, template='.'
                # and opens a NEW document; do not rely on locale drawing units.
                client.request("engine.execute", {
                    "command": "new", "params": {"metric": True, "template": "."},
                })
                original = client.inspect()
                if original.entity_count or original.dirty:
                    raise RuntimeError("NEW_METRIC_DOCUMENT_NOT_EMPTY")
                instructions = demo_instructions()
                observed = client.execute_whd_draw(instructions)
                # Inspect alone is not geometric parity. Compare independent
                # serialized DXF bytes using WHD's existing exact coordinate gate.
                payload = client.request("engine.execute", {
                    "command": "document.bytes",
                    "params": {"format": "dxf", "version": 2010},
                })
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), str):
                    raise RuntimeError("CADCRAFT_DOCUMENT_BYTES_MISSING")
                encoded = payload["data"]
                if len(encoded) > 4_100_000:
                    raise RuntimeError("CADCRAFT_DOCUMENT_BYTES_TOO_LARGE")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, base64.binascii.Error) as exc:
                    raise RuntimeError("CADCRAFT_INVALID_DOCUMENT_BASE64") from exc
                if len(raw) > 3_000_000 or payload.get("bytes") != len(raw):
                    raise RuntimeError("CADCRAFT_DOCUMENT_BYTES_SIZE_MISMATCH")
                output = root / "isolated-cadcraft-control.dxf"
                output.write_bytes(raw)
                checked = verify_dxf(output, instructions)
                if checked["entity_count"] != len(observed.entities):
                    raise RuntimeError("CONTROL_INSPECTION_DXF_COUNT_MISMATCH")
                return {
                    "status": "PASS",
                    "scope": "official CADCraft desktop TCP, isolated new metric drawing",
                    "catalog": catalog,
                    "observed_count": len(observed.entities),
                    "geometry": checked,
                    "whd_session_modified": False,
                    "manufacturing_dxf_written": False,
                    "windows_gui_uat_completed": False,
                }
            except Exception as exc:
                # Carry limited native logs in diagnostics, not as a fake PASS.
                log.flush()
                try:
                    detail = log_file.read_text(encoding="utf-8", errors="replace")[-2500:]
                except OSError:
                    detail = ""
                raise RuntimeError(f"CADCRAFT_NATIVE_TCP_PROBE_FAILED:{exc}; LOG_TAIL={detail}") from exc
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cadcraft", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = native_probe(args.cadcraft)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
