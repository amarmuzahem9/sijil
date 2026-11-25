"""key.age: the identity wrapped with the owner's passphrase (specs/016 research R2, T028).

The operator types the passphrase on the terminal. For local development and the automated
end-to-end checks the same `age -p` flow is fed through a pseudo-terminal; the passphrase is
never written to a file, an argument or a log.
"""

import subprocess

import pytest

from app.backup import __main__ as cli
from app.backup import crypto, keyfile

PASS = "synthetic-test-passphrase-not-real"


def test_create_then_unlock_round_trip(tmp_path) -> None:
    key_path = tmp_path / "backups" / "key.age"
    key_path.parent.mkdir()
    recipient = keyfile.create(key_path, passphrase=PASS)
    assert recipient.startswith("age1")
    data = key_path.read_bytes()
    assert b"AGE-SECRET-KEY" not in data  # wrapped, never plaintext
    assert (key_path.stat().st_mode & 0o777) == 0o600

    # The unlocked identity decrypts what the recipient encrypted.
    plain = tmp_path / "p"
    plain.write_bytes(b"synthetic")
    crypto.encrypt_file(plain, tmp_path / "p.age", recipient)
    with keyfile.unlocked(key_path, passphrase=PASS) as identity:
        assert "AGE-SECRET-KEY-1" in identity.read_text()
        crypto.decrypt_file(tmp_path / "p.age", tmp_path / "back", identity)
        left = identity
    assert not left.exists()  # the plaintext identity is gone afterwards
    assert (tmp_path / "back").read_bytes() == b"synthetic"


def test_wrong_passphrase_fails(tmp_path) -> None:
    key_path = tmp_path / "key.age"
    keyfile.create(key_path, passphrase=PASS)
    with pytest.raises(keyfile.KeyfileError):
        with keyfile.unlocked(key_path, passphrase="wrong"):
            pass


def test_create_refuses_an_existing_key(tmp_path) -> None:
    key_path = tmp_path / "key.age"
    keyfile.create(key_path, passphrase=PASS)
    with pytest.raises(keyfile.KeyfileError):
        keyfile.create(key_path, passphrase=PASS)


def test_short_passphrase_refused(tmp_path) -> None:
    with pytest.raises(keyfile.KeyfileError):
        keyfile.create(tmp_path / "key.age", passphrase="short")


def test_identity_is_never_left_behind_on_failure(tmp_path, monkeypatch) -> None:
    created = []
    real = keyfile._scratch_dir

    def spy():
        path = real()
        created.append(path)
        return path

    monkeypatch.setattr(keyfile, "_scratch_dir", spy)
    with pytest.raises(keyfile.KeyfileError):
        with keyfile.unlocked(tmp_path / "missing.age", passphrase=PASS):
            pass
    assert created and not any(p.exists() for p in created)


def test_recipient_of_a_wrapped_key(tmp_path) -> None:
    key_path = tmp_path / "key.age"
    recipient = keyfile.create(key_path, passphrase=PASS)
    with keyfile.unlocked(key_path, passphrase=PASS) as identity:
        derived = subprocess.run(
            ["age-keygen", "-y", str(identity)], capture_output=True, text=True, check=True
        ).stdout.strip()
    assert derived == recipient


def test_cli_init_key_from_stdin(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "b"))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(PASS + "\n"))
        assert cli.main(["init-key", "--passphrase-stdin"]) == 0
        out = capsys.readouterr().out
        assert "BACKUP_AGE_RECIPIENT=age1" in out
        assert PASS not in out
        assert (tmp_path / "b" / "key.age").exists()
        assert cli.main(["init-key", "--passphrase-stdin"]) == 1  # never overwritten
    finally:
        get_settings.cache_clear()
