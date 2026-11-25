"""The api image carries the backup tools (specs/016 research R1, task T002)."""

import re
import shutil
import subprocess


def test_pg_dump_is_version_16() -> None:
    # pg_dump must match the PostgreSQL 16 server, so the dump restores into it without errors.
    assert shutil.which("pg_dump"), "pg_dump is missing from the api image"
    out = subprocess.run(
        ["pg_dump", "--version"], capture_output=True, text=True, check=True
    ).stdout
    assert re.search(r"\b16\.\d+", out), out


def test_pg_restore_is_version_16() -> None:
    assert shutil.which("pg_restore"), "pg_restore is missing from the api image"
    out = subprocess.run(["pg_restore", "--version"], capture_output=True, text=True, check=True)
    assert re.search(r"\b16\.\d+", out.stdout), out.stdout


def test_age_is_installed() -> None:
    for tool in ("age", "age-keygen"):
        assert shutil.which(tool), f"{tool} is missing from the api image"
