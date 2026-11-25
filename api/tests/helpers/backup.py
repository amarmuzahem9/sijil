"""Backup test helpers (specs/016): a throwaway age key per test, synthetic files only."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgeKey:
    identity: Path  # plaintext identity: only ever in tmp_path (tests) or tmpfs (operator)
    recipient: str


def make_age_key(directory: Path, name: str = "identity.txt") -> AgeKey:
    """A fresh X25519 key, written under `directory` (a pytest tmp_path). Never committed."""
    identity = directory / name
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(
        ["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True
    ).stdout.strip()
    return AgeKey(identity=identity, recipient=recipient)


def image_name(n: int) -> str:
    """A stored-image file name in the image_store format (`<32 hex>.jpg`)."""
    return f"{n:032x}.jpg"
