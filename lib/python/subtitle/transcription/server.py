import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional


def whisper_server_enabled() -> bool:
    """Whether shared whisper server mode is enabled."""
    return os.environ.get("AMIR_WHISPER_SERVER", "1") not in ("0", "false", "False")


def get_whisper_server_socket_path(model_size: str) -> str:
    model_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (model_size or "turbo"))
    return os.environ.get("AMIR_WHISPER_SERVER_SOCKET", f"/tmp/amir_whisper_{model_key}.sock")


def is_whisper_server_ready(socket_path: str) -> bool:
    if not os.path.exists(socket_path):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(socket_path)
            return True
    except Exception:
        return False


def ensure_whisper_server(model_size: str, logger=None) -> Optional[str]:
    """Ensure whisper server is reachable; auto-start if missing."""
    if not whisper_server_enabled():
        return None

    socket_path = get_whisper_server_socket_path(model_size)
    if is_whisper_server_ready(socket_path):
        return socket_path

    try:
        if os.path.exists(socket_path):
            os.remove(socket_path)
    except Exception:
        pass

    try:
        py_exe = sys.executable or "python3"
        env = os.environ.copy()
        # subtitle/transcription/server.py -> up three levels => lib/python
        py_root = str(Path(__file__).parent.parent.parent)
        env["PYTHONPATH"] = f"{py_root}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else py_root

        cmd = [
            py_exe,
            "-m",
            "subtitle.whisper_server",
            "--socket",
            socket_path,
            "--model",
            model_size,
        ]

        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        for _ in range(80):
            if is_whisper_server_ready(socket_path):
                if logger is not None:
                    logger.info(f"🧠 Shared Whisper server ready: {socket_path}")
                return socket_path
            import time
            time.sleep(0.1)
    except Exception:
        pass

    return None
