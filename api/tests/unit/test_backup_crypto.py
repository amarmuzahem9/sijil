"""age encryption for backups (specs/016 research R2, task T006). Throwaway keys only."""

import inspect
import os
import tracemalloc
from pathlib import Path

import pytest

from app.backup import crypto
from tests.helpers.backup import make_age_key

AGE_HEADER = b"age-encryption.org/v1\n"


@pytest.fixture
def key(tmp_path):
    return make_age_key(tmp_path)


def test_encrypt_then_decrypt_gives_the_bytes_back(tmp_path, key) -> None:
    plain = tmp_path / "plain.bin"
    plain.write_bytes(b"synthetic card bytes \x00\xff" * 100)
    enc = tmp_path / "out" / "plain.bin.age"
    enc.parent.mkdir()
    crypto.encrypt_file(plain, enc, key.recipient)
    data = enc.read_bytes()
    assert data.startswith(AGE_HEADER)
    assert b"synthetic card bytes" not in data
    back = tmp_path / "back.bin"
    crypto.decrypt_file(enc, back, key.identity)
    assert back.read_bytes() == plain.read_bytes()


def test_encrypt_is_atomic_and_leaves_no_temp_file(tmp_path, key) -> None:
    plain = tmp_path / "p"
    plain.write_bytes(b"x")
    enc = tmp_path / "p.age"
    crypto.encrypt_file(plain, enc, key.recipient)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["identity.txt", "p", "p.age"]


def test_encrypt_stream(tmp_path, key) -> None:
    enc = tmp_path / "dump.age"
    src = tmp_path / "src"
    src.write_bytes(b"dump-bytes" * 1000)
    with src.open("rb") as stream:
        size = crypto.encrypt_stream(stream, enc, key.recipient)
    assert size == enc.stat().st_size
    back = tmp_path / "back"
    crypto.decrypt_file(enc, back, key.identity)
    assert back.read_bytes() == src.read_bytes()


def test_wrong_identity_fails_cleanly(tmp_path, key) -> None:
    other = make_age_key(tmp_path, "other.txt")
    plain = tmp_path / "p"
    plain.write_bytes(b"secret-ish synthetic")
    enc = tmp_path / "p.age"
    crypto.encrypt_file(plain, enc, key.recipient)
    out = tmp_path / "out"
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_file(enc, out, other.identity)
    assert not out.exists()


def test_bad_recipient_fails_without_writing(tmp_path) -> None:
    plain = tmp_path / "p"
    plain.write_bytes(b"x")
    enc = tmp_path / "p.age"
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt_file(plain, enc, "age1notakey")
    assert not enc.exists()
    assert not list(tmp_path.glob("*.part"))


def test_damaged_file_fails_to_decrypt(tmp_path, key) -> None:
    plain = tmp_path / "p"
    plain.write_bytes(b"y" * 5000)
    enc = tmp_path / "p.age"
    crypto.encrypt_file(plain, enc, key.recipient)
    data = bytearray(enc.read_bytes())
    data[-10] ^= 0xFF
    enc.write_bytes(bytes(data))
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_file(enc, tmp_path / "out", key.identity)


def test_streaming_keeps_memory_bounded(tmp_path, key) -> None:
    big = tmp_path / "big"
    with big.open("wb") as f:
        for _ in range(20):
            f.write(os.urandom(1024 * 1024))
    tracemalloc.start()
    crypto.encrypt_file(big, tmp_path / "big.age", key.recipient)
    digest = crypto.sha256_file(tmp_path / "big.age")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 4 * 1024 * 1024, peak
    assert len(digest) == 64


def test_sha256_file(tmp_path) -> None:
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    assert crypto.sha256_file(p) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_no_function_takes_a_passphrase() -> None:
    # The passphrase never passes through Python: `age -p` asks for it on the terminal (R2).
    for name, fn in inspect.getmembers(crypto, inspect.isfunction):
        params = set(inspect.signature(fn).parameters)
        assert not params & {"passphrase", "password", "secret"}, name


def test_decrypt_refuses_an_identity_inside_the_backup_folder(tmp_path, key, monkeypatch) -> None:
    # A plaintext identity next to the backups would make the encryption useless (FR-010).
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    inside = backup_dir / "identity.txt"
    inside.write_bytes(Path(key.identity).read_bytes())
    plain = tmp_path / "p"
    plain.write_bytes(b"x")
    enc = tmp_path / "p.age"
    crypto.encrypt_file(plain, enc, key.recipient)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(crypto.CryptoError, match="identity"):
            crypto.decrypt_file(enc, tmp_path / "out", inside)
    finally:
        get_settings.cache_clear()
