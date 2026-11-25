"""key.age: the backup identity wrapped with the owner's passphrase (specs/016 research R2).

`create` makes a new X25519 identity, wraps it with `age -p` into key.age and returns the public
recipient for `.env`. `unlocked` unwraps it into a private scratch folder (tmpfs when there is
one) for the length of a restore or drill, then wipes it.

The operator types the passphrase on the terminal (`age` reads /dev/tty). With
`passphrase=...` (local development and the automated end-to-end checks) the same prompts are
answered through a pseudo-terminal. The passphrase is never written to a file, an argument, an
environment variable or a log.
"""

import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIN_PASSPHRASE = 12
_PROMPT = re.compile(rb"(Enter|Confirm) passphrase")


class KeyfileError(Exception):
    """key.age could not be created or unlocked. Never carries the passphrase."""


def _scratch_dir() -> Path:
    base = "/dev/shm" if os.access("/dev/shm", os.W_OK) else None
    return Path(tempfile.mkdtemp(prefix="sijil-key-", dir=base))


def _wipe(folder: Path) -> None:
    for path in folder.glob("*"):
        try:
            size = path.stat().st_size
            with path.open("r+b") as f:
                f.write(b"\0" * size)
        except OSError:
            pass
    shutil.rmtree(folder, ignore_errors=True)


def _run_age(argv: list[str], passphrase: str | None, timeout: float = 120) -> None:
    if passphrase is None:
        # Interactive: age asks on the operator's terminal.
        if subprocess.run(argv).returncode != 0:
            raise KeyfileError("age failed (wrong passphrase?)")
        return
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.execvp(argv[0], argv)
        finally:
            os._exit(127)
    seen, answered = b"", 0
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    break
                continue
            try:
                chunk = os.read(fd, 1024)
            except OSError:
                break  # the child closed the terminal
            if not chunk:
                break
            seen += chunk
            prompts = len(_PROMPT.findall(seen))
            while answered < prompts:
                os.write(fd, passphrase.encode() + b"\n")
                answered += 1
        else:
            os.kill(pid, 9)
    finally:
        os.close(fd)
    _, status = os.waitpid(pid, 0)
    if os.waitstatus_to_exitcode(status) != 0:
        raise KeyfileError("age failed (wrong passphrase?)")


def create(key_path: Path, passphrase: str | None = None) -> str:
    """Create key.age; returns the public recipient. Refuses to overwrite an existing key."""
    if key_path.exists():
        raise KeyfileError("key.age already exists; it is never overwritten")
    if passphrase is not None and len(passphrase) < MIN_PASSPHRASE:
        raise KeyfileError(f"the passphrase must have at least {MIN_PASSPHRASE} characters")
    scratch = _scratch_dir()
    try:
        identity = scratch / "identity"
        subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
        recipient = subprocess.run(
            ["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True
        ).stdout.strip()
        temp = key_path.with_name(key_path.name + ".part")
        _run_age(["age", "--passphrase", "--armor", "-o", str(temp), str(identity)], passphrase)
        os.chmod(temp, 0o600)
        os.replace(temp, key_path)
        return recipient
    except subprocess.CalledProcessError as exc:
        raise KeyfileError("age-keygen failed") from exc
    finally:
        key_path.with_name(key_path.name + ".part").unlink(missing_ok=True)
        _wipe(scratch)


@contextmanager
def unlocked(key_path: Path, passphrase: str | None = None) -> Iterator[Path]:
    """The plaintext identity in a private scratch folder, wiped on exit."""
    scratch = _scratch_dir()
    try:
        if not key_path.is_file():
            raise KeyfileError("key.age not found")
        identity = scratch / "identity"
        _run_age(["age", "--decrypt", "-o", str(identity), str(key_path)], passphrase)
        os.chmod(identity, 0o600)
        yield identity
    finally:
        _wipe(scratch)
