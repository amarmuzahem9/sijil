# Operator Commands Contract (016)

Run on the server from `/opt/sijil`. Messages to the operator are in Arabic; exit code 0 = success. No command prints
personal data, secrets or the passphrase.

## scripts/backup.sh

| Command | What it does | Passphrase |
|---|---|---|
| `init-key` | Once: create `key.age`, print `BACKUP_AGE_RECIPIENT` and tell the owner to write the passphrase down. Refuses if `key.age` exists. | sets it |
| `init-external` | Once per drive: checks the mount point, writes the marker `.sijil-external`. | no |
| `now [--kind manual\|pre_deploy]` | One backup now (R4). Exit 3 `busy`, 4 `disk_low`, 1 other failure. | no |
| `list [--external]` | Snapshots: id, Baghdad time, kind, status, size, counts. | no |
| `weekly` | External copy (R10) then drill on it; ends with «يمكن فصل الهارد الآن». Exit 5 drive not mounted / no marker / full. | yes (drill) |
| `drill [id] [--external]` | Restore drill in the isolated stack (R9). Exit 6 failed. | yes |
| `status` | Last backup, last external copy, last drill, warnings. Exit 1 when there is a warning. | no |

## scripts/restore.sh `[id] [--from-external]`

Interactive (R7). Shows the snapshot and what is lost, asks to type its date, takes `pre_restore`, asks the
passphrase, verifies, stages, swaps, restarts, checks health. Exit 7 refused (revision newer than the code, damaged,
not confirmed); the live system is unchanged on any failure before the swap.

## scripts/deploy.sh

As research R11. Exit 1 pre-flight refusal (nothing changed), 2 public URL unreachable (as today), 8 health failed
after update (prints the pre-deploy snapshot and rollback steps). `scripts/deploy-staging.sh` calls it.

## python -m app.cli go-live

Deactivates the demo accounts, audited `system.go_live`; idempotent.

## .env additions (.env.example)

| Variable | Meaning |
|---|---|
| `BACKUP_DIR` | host folder for backups (server), e.g. `/var/backups/sijil` |
| `BACKUP_AGE_RECIPIENT` | public `age1…` key printed by `init-key` (not a secret) |
| `BACKUP_EXTERNAL_DIR` | mount point of the external drive, e.g. `/media/sijil-external` |
| `BACKUP_NIGHTLY_AT` | `03:00` (Baghdad) |
| `BACKUP_MIN_FREE_GB` | `2` |
