# Quickstart / Validation: Deployment and Backups (016)

Synthetic data and a throwaway key only. Never run these steps against real card images outside the isolated drill.

## Prerequisites

- Local stack: `docker compose up -d --build` (the `backup` service starts with it; `BACKUP_DIR` defaults to a named
  volume, `BACKUP_AGE_RECIPIENT` from a test key created by `scripts/backup.sh init-key` with any passphrase).
- Synthetic data: `docker compose exec api python -m app.cli seed-demo` plus a few submitted requests with generated
  images (as in the 005/014 tests) and a fake legacy import.

## Automated

```bash
docker compose exec -T api pytest tests -k backup        # unit + integration (R13)
bash scripts/backup-e2e.sh                               # full cycle on a throwaway project
scripts/test-all.sh                                      # everything, incl. vitest and Playwright
```

`backup-e2e.sh` must show: backup OK → change → restore → identical counts and image hashes; drill passed; drill on a
corrupted object failed; weekly refused without the marker, succeeded with it; deploy pre-flight refused a `fake` mode
in production and an active demo account in production.

## Manual checks

1. **Nightly** — set `BACKUP_NIGHTLY_AT` to two minutes from now, restart `backup`; a `nightly` run appears on
   «النسخ الاحتياطي» with size and counts. Set it again: no second nightly the same Baghdad day.
2. **Manual button** — main admin presses «نسخة يدوية الآن»: in progress, then «ناجحة»; pressing during a run shows
   «يوجد نسخ جارٍ الآن». An added admin with all permissions gets 403 on the page and on the API.
3. **No secrets** — `grep -r` every value of `.env` over `BACKUP_DIR` (after decrypting a test snapshot): no hit.
   Opening `db.dump.age` or an image object without the passphrase fails.
4. **Restore** — note counts, add a request, erase another (011), run `scripts/restore.sh <id>`: the warning lists
   what is lost; after it the counts match the snapshot, every image opens, the erased request is back, the page lists
   the restore and the `pre_restore` snapshot.
5. **Weekly** — mount a USB stick (or a loop file system) at `BACKUP_EXTERNAL_DIR`, `init-external`, `weekly`: copy
   verified, drill passed, «يمكن فصل الهارد الآن». Unmount and run `weekly` again: refused, nothing written to the
   server disk. Fake the clock (or the last event) past 8 days: «النسخة الأسبوعية متأخرة» on the home page.
6. **Retention** — rename synthetic snapshots to dates older than 30 days; after the next success they are gone, the
   newest success is kept, unreferenced image objects are removed.
7. **Deploy** — `scripts/deploy.sh` in staging: `pre_deploy` snapshot, health OK, deploy line on the page. Break
   `.env` (`change-me`): refused, nothing changed.
