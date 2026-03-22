import hashlib
import json
import os
import tempfile
import time
from typing import Optional


def is_pid_alive(pid: int) -> bool:
    """Return True if a process with pid exists."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def acquire_workflow_lock(lock_key: str, source_path: str) -> str:
    """Acquire an exclusive lock for a subtitle workflow."""
    lock_dir = os.path.join(tempfile.gettempdir(), "amir_subtitle_locks")
    os.makedirs(lock_dir, exist_ok=True)

    lock_name = hashlib.sha1(lock_key.encode("utf-8")).hexdigest() + ".lock"
    lock_path = os.path.join(lock_dir, lock_name)

    payload = {
        "pid": os.getpid(),
        "created_at": int(time.time()),
        "source": source_path,
        "key": lock_key,
    }

    for _ in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            return lock_path
        except FileExistsError:
            stale = False
            holder = {}
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    holder = json.load(f)
                holder_pid = int(holder.get("pid", 0))
                holder_ts = int(holder.get("created_at", 0))
                holder_alive = is_pid_alive(holder_pid)
                too_old = (time.time() - holder_ts) > 24 * 3600
                stale = (not holder_alive) or too_old
            except Exception:
                stale = True

            if stale:
                try:
                    os.remove(lock_path)
                except Exception:
                    pass
                continue

            holder_src = holder.get("source", "unknown")
            holder_pid = holder.get("pid", "?")
            raise RuntimeError(
                f"Another subtitle workflow is already running for this source "
                f"(pid={holder_pid}, source={holder_src}). "
                f"Wait for it to finish or stop that process first."
            )

    raise RuntimeError("Failed to acquire workflow lock")


def release_workflow_lock(lock_path: Optional[str]) -> None:
    """Release workflow lock if currently held by this process."""
    if not lock_path:
        return
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if int(payload.get("pid", -1)) == os.getpid() and os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


def acquire_global_workflow_slot(source_path: str, cap: int, logger=None) -> Optional[str]:
    """Acquire a global slot to throttle concurrent subtitle workflows."""
    if cap <= 0:
        return None

    slot_dir = os.path.join(tempfile.gettempdir(), "amir_subtitle_global_slots")
    os.makedirs(slot_dir, exist_ok=True)

    payload = {
        "pid": os.getpid(),
        "created_at": int(time.time()),
        "source": source_path,
    }

    wait_seconds = 0
    while True:
        stale_removed = False
        for i in range(cap):
            slot_path = os.path.join(slot_dir, f"slot_{i}.lock")
            try:
                fd = os.open(slot_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                if logger is not None:
                    if wait_seconds > 0:
                        logger.info(f"🟢 Global slot acquired after waiting {wait_seconds}s (slot {i+1}/{cap}).")
                    else:
                        logger.info(f"🟢 Global slot acquired ({i+1}/{cap}).")
                return slot_path
            except FileExistsError:
                try:
                    with open(slot_path, "r", encoding="utf-8") as f:
                        holder = json.load(f)
                    holder_pid = int(holder.get("pid", 0))
                    holder_ts = int(holder.get("created_at", 0))
                    holder_alive = is_pid_alive(holder_pid)
                    too_old = (time.time() - holder_ts) > 24 * 3600
                    if (not holder_alive) or too_old:
                        os.remove(slot_path)
                        stale_removed = True
                except Exception:
                    try:
                        os.remove(slot_path)
                        stale_removed = True
                    except Exception:
                        pass

        if stale_removed:
            continue

        if wait_seconds == 0 and logger is not None:
            logger.warning(
                f"⏳ Concurrent subtitle limit reached (cap={cap}). "
                "Waiting for a free slot..."
            )
        time.sleep(5)
        wait_seconds += 5


def release_global_workflow_slot(slot_path: Optional[str]) -> None:
    """Release global workflow slot held by this process."""
    if not slot_path:
        return
    try:
        with open(slot_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if int(payload.get("pid", -1)) == os.getpid() and os.path.exists(slot_path):
            os.remove(slot_path)
    except Exception:
        pass
