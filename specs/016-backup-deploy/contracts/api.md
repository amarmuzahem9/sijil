# API Contract: Backups (016)

All routes require the **main admin** (`role = main_admin`); anyone else → `403 forbidden` (Principle IX). Times are
UTC ISO; the web shows them in Baghdad time. No response carries personal data.

## GET /api/admin/backup

```json
{
  "status": {
    "service_ok": true, "heartbeat_at": "…", "nightly_at": "03:00",
    "free_bytes": 0, "total_bytes": 0, "min_free_bytes": 0, "backup_dir_bytes": 0,
    "external_dir": "/media/sijil-external"
  },
  "running": {"id": "…", "kind": "manual", "started_at": "…"} ,
  "runs": [{"id": "…", "snapshot_id": "…", "kind": "nightly", "status": "succeeded", "error_code": null,
            "started_at": "…", "finished_at": "…", "total_size": 0, "image_count": 0,
            "counts": {"requests": 0, "legacy_subscribers": 0, "sas_subscribers": 0, "users": 0}}],
  "last_external": {"at": "…", "result": "succeeded", "snapshot_id": "…"},
  "last_drill": {"at": "…", "result": "passed", "snapshot_id": "…", "reason": null},
  "deploys": [{"at": "…", "result": "succeeded", "mode": "production", "commit": "af9155f"}],
  "warnings": ["external_overdue"]
}
```
`running` is `null` when idle. `runs`: last 40, newest first, `removed` excluded. `deploys`: last 10.

## POST /api/admin/backup/run

Starts a manual backup. → `202 {"id": "req-…"}`. Audited `backup.manual_requested`.
- `409 backup_busy` «يوجد نسخ جارٍ الآن» when a run is `requested` or `running`.
- `503 backup_service_down` «خدمة النسخ متوقفة» when the heartbeat is older than 10 minutes.

## GET /api/admin/home (changed)

Adds `"backup_warnings": [code]` — present for the main admin, always `[]` for other admins.

## Warning codes and texts

| code | text |
|---|---|
| `last_failed` | فشل آخر نسخ احتياطي |
| `no_recent_backup` | لا توجد نسخة ناجحة منذ أكثر من 36 ساعة |
| `external_overdue` | النسخة الأسبوعية على الهارد الخارجي متأخرة |
| `drill_failed_or_overdue` | تجربة الاسترجاع فشلت أو متأخرة |
| `disk_low` | مساحة السيرفر قليلة |
| `service_down` | خدمة النسخ متوقفة |
