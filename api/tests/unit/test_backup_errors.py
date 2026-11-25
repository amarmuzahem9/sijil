"""Backup error codes and their Arabic messages (specs/016 contracts/api.md, task T004)."""

from app.errors import MESSAGES


def test_backup_error_messages() -> None:
    assert MESSAGES["backup_busy"] == "يوجد نسخ جارٍ الآن"
    assert MESSAGES["backup_service_down"] == "خدمة النسخ متوقفة"
