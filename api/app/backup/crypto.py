"""age encryption for backups (specs/016 research R2).

The server holds the public recipient only, so it encrypts every backup unattended and can never
decrypt one. Decryption needs the identity, which the operator unlocks from `key.age` with the
passphrase on the terminal (`age -d` asks for it); that plaintext identity lives only in tmpfs.
No function here takes a passphrase. `age` runs as a subprocess without a shell, streaming, so
memory stays bounded whatever the size.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings

CHUNK = 1024 * 1024
TEMP_SUFFIX = ".part"


class CryptoError(Exception):
    """An age failure. The message names the step, never file contents or key material."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _temp(dst: Path) -> Path:
    return dst.with_name(dst.name + TEMP_SUFFIX)


def _finish(proc: subprocess.Popen, temp: Path, dst: Path, step: str) -> None:
    assert proc.stderr is not None
    err = proc.stderr.read()
    proc.stderr.close()
    if proc.wait() != 0:
        temp.unlink(missing_ok=True)
        # age's own message is about the key or the format; it never carries plaintext.
        reason = (err or b"").decode(errors="replace").strip().splitlines()[-1:] or ["failed"]
        raise CryptoError(f"{step}: {reason[0][:200]}")
    os.chmod(temp, 0o600)
    os.replace(temp, dst)


def encrypt_stream(source: BinaryIO, dst: Path, recipient: str) -> int:
    """Encrypt everything read from `source` into `dst` (atomic). Returns the size written."""
    temp = _temp(dst)
    with temp.open("wb") as out:
        try:
            proc = subprocess.Popen(
                ["age", "--encrypt", "--recipient", recipient],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise CryptoError("encrypt: age is not available") from exc
        try:
            assert proc.stdin is not None
            shutil.copyfileobj(source, proc.stdin, CHUNK)
            proc.stdin.close()
        except BrokenPipeError:
            pass  # age stopped early (bad recipient); its exit code says why
    _finish(proc, temp, dst, "encrypt")
    return dst.stat().st_size


def encrypt_file(src: Path, dst: Path, recipient: str) -> int:
    with src.open("rb") as source:
        return encrypt_stream(source, dst, recipient)


def _check_identity(identity: Path) -> None:
    backup_dir = Path(get_settings().backup_dir).resolve()
    resolved = identity.resolve()
    if resolved == backup_dir or backup_dir in resolved.parents:
        # A plaintext identity next to the backups would undo the encryption (FR-010).
        raise CryptoError("decrypt: the identity must not be inside the backup folder")


def decrypt_file(src: Path, dst: Path, identity: Path) -> None:
    """Decrypt `src` into `dst` (atomic). Nothing is left behind on failure."""
    _check_identity(identity)
    temp = _temp(dst)
    with temp.open("wb") as out:
        proc = subprocess.Popen(
            ["age", "--decrypt", "--identity", str(identity), str(src)],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.PIPE,
        )
    _finish(proc, temp, dst, "decrypt")
