from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import shutil
import tempfile
import time
import uuid


class Error(RuntimeError):
    """An actionable operation failure; details never imply rollback of external effects."""
    code = "operation_failed"


class Conflict(Error):
    code = "conflict"


class LockBusy(Conflict):
    code = "lock_busy"


class RetryableRead(Error):
    """Only the failed read is safe to repeat, not its caller's business operation."""
    code = "retryable_read"


class Uncertain(Error):
    code = "outcome_unknown"


class Unavailable(Error):
    code = "unavailable"


def now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def uid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex


def slug(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value):
        raise Error("Use 1-64 letters, digits, underscores or hyphens for IDs and aliases.")
    return value


def relpath(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or "\0" in value:
        raise Error(f"Not a safe relative path: {value!r}")
    if any(part.lower() in (".git", ".aw-local") for part in path.parts):
        raise Error("Git internals and local runtime state are not publishable assets.")
    return str(path)


def inside(root: Path, value: str) -> Path:
    path = root / relpath(value)
    if not path.resolve().is_relative_to(root.resolve()):
        raise Error("Asset path escapes the instance directory.")
    return path


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".aw-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, value) -> None:
    write_bytes(path, encode(value))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextlib.contextmanager
def locked(path: Path, *, wait: float = 30):
    """OS lock, released on process death; never infer liveness from an old PID file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        # Windows permits byte-range locks beyond EOF. Writing an initial byte
        # before locking races another handle which has already locked that byte.
        deadline = time.monotonic() + wait
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise LockBusy(f"Resource is in use: {path.name}") from exc
                time.sleep(0.04)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def command_detail(output: bytes | str | None) -> str:
    detail = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or ""
    # Credentials can appear in remote URLs. Redact before truncating a diagnostic.
    detail = re.sub(r"(https?://)[^/@\s]+@", r"\1[redacted]@", detail)
    return detail.strip()[-1500:]


def run(args: list[str], *, cwd: Path | None = None, data: bytes | None = None,
        env: dict | None = None, check: bool = True, timeout: float = 60):
    result = subprocess.run(args, cwd=cwd, input=data, capture_output=True, env=env,
                            timeout=timeout, check=False)
    if check and result.returncode:
        raise Error(command_detail(result.stderr) or f"{Path(args[0]).name} exited {result.returncode}")
    return result


def child_command(command: list[str]) -> list[str]:
    """Resolve npm's Windows .cmd launchers; prompt/body data still travels on stdin."""
    if not command or not all(isinstance(part, str) for part in command):
        raise Error("Process command must be a non-empty argument array.")
    if os.name != "nt":
        return command
    executable = shutil.which(command[0]) or command[0]
    if Path(executable).suffix.lower() in (".cmd", ".bat"):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c",
                subprocess.list2cmdline([executable, *command[1:]])]
    return [executable, *command[1:]]
