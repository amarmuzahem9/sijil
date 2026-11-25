"""Backup failures (specs/016 data-model.md `backup_runs.error_code`)."""


class SnapshotFailed(Exception):
    """A backup that could not be completed. `code` is one of `RUN_ERRORS`; never personal data."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class BackupBusy(SnapshotFailed):
    """Another backup or restore holds the lock (research R5)."""

    def __init__(self) -> None:
        super().__init__("busy")
