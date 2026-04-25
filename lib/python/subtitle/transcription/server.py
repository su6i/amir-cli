import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def whisper_server_enabled() -> bool:
    """Whether shared whisper server mode is enabled."""
    return os.environ.get("AMIR_WHISPER_SERVER", "1") not in ("0", "false", "False")


def get_whisper_server_socket_path(model_size: str) -> str:
    model_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (model_size or "turbo"))
    return os.environ.get("AMIR_WHISPER_SERVER_SOCKET", f"/tmp/amir_whisper_{model_key}.sock")


def _get_server_log_path(model_size: str) -> str:
    """Where the server writes its stderr for post-mortem diagnostics."""
    model_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (model_size or "turbo"))
    return f"/tmp/amir_whisper_{model_key}.log"


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


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def ensure_whisper_server(model_size: str, logger=None) -> Optional[str]:
    """Ensure whisper server is reachable; auto-start if missing.

    Improvements over the original:
    - Waits up to 120 seconds (model loading can be slow on first run).
    - Logs server stderr to a file for crash diagnostics.
    - Checks process liveness during wait to fail fast on crashes.
    - Retries once if the server process dies during startup.
    """
    if not whisper_server_enabled():
        return None

    socket_path = get_whisper_server_socket_path(model_size)
    if is_whisper_server_ready(socket_path):
        return socket_path

    # Clean stale socket
    try:
        if os.path.exists(socket_path):
            os.remove(socket_path)
    except Exception:
        pass

    max_attempts = 2  # try starting the server up to 2 times
    for attempt in range(1, max_attempts + 1):
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

            # Redirect stderr to a log file for crash diagnostics
            log_path = _get_server_log_path(model_size)
            log_file = open(log_path, "a", encoding="utf-8")

            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=log_file,
                start_new_session=True,
            )
            # Child keeps its own FD; close parent-side handle.
            log_file.close()

            if logger is not None:
                logger.info(f"🧠 Starting Whisper server (PID {proc.pid}, attempt {attempt}/{max_attempts})...")

            # Wait up to 120 seconds with progressive backoff.
            # Model loading on Apple Silicon w/ turbo can take 30-60s.
            total_waited = 0.0
            poll_interval = 0.3  # start fast, slow down
            while total_waited < 120.0:
                if is_whisper_server_ready(socket_path):
                    if logger is not None:
                        logger.info(f"🧠 Shared Whisper server ready: {socket_path} ({total_waited:.1f}s)")
                    return socket_path

                # Check if the server process is still alive
                if not _is_pid_alive(proc.pid):
                    if logger is not None:
                        logger.warning(f"⚠️ Whisper server process died (PID {proc.pid}). See {log_path} for details.")
                    break  # exit inner loop to retry

                time.sleep(poll_interval)
                total_waited += poll_interval
                # Progressive backoff: increase interval up to 2s
                poll_interval = min(2.0, poll_interval * 1.3)

            if is_whisper_server_ready(socket_path):
                return socket_path

            if logger is not None:
                logger.warning(f"⚠️ Whisper server startup attempt {attempt}/{max_attempts} timed out after {total_waited:.0f}s")

        except Exception as e:
            if logger is not None:
                logger.warning(f"⚠️ ensure_whisper_server attempt {attempt}: {e}")

    return None

