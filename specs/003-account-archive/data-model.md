# Data Model: Account Archive (003)

Extends [002 data-model](../002-accounts-permissions/data-model.md). No rows are ever deleted.

## users: new columns

| Column | Type | Rules |
|---|---|---|
| `archived_at` | timestamptz, null | Set when archived (UTC, application clock). Null = not archived |
| `archived_by` | bigint FK → users.id, null | The main admin who archived it. Null when not archived |

Constraints added in migration `0003`:

| Constraint | Definition | Purpose |
|---|---|---|
| `users_archive_pair` | `(archived_at IS NULL) = (archived_by IS NULL)` | Both set or both empty |
| `users_archived_inactive` | `archived_at IS NULL OR is_active = false` | An archived account can never sign in |
| `users_super_admin_not_archived` | `role <> 'super_admin' OR archived_at IS NULL` | FR-002 at DB level |

`users.phone` stays unique across all rows, so an archived phone stays reserved (FR-008).

### Account states (adds to the 002 diagram)

```text
active ──┐                         ┌── «إعادة تفعيل» (002) ──▶ active
         ├─ «حذف» ─▶ archived ─ «استرجاع» ─▶ inactive ─┘
inactive ┘  (is_active=false,       (archived_at/by cleared,
             sessions revoked        is_active stays false)
             reason "archived")
```

## sessions

The CHECK `sessions_revoke_reason_valid` gains the value `archived`.

## Page map: new row (shared fixture `page_access.json`)

| Page key | Path | Access |
|---|---|---|
| `archive` | `/admin/archive` | main admin only |

## audit_log: actions added

| action | Arabic label | before | after |
|---|---|---|---|
| `user.archived` | أرشفة حساب | `{is_active, archived: false}` | `{is_active: false, archived: true}` |
| `user.restored` | استرجاع حساب من الأرشيف | `{archived: true}` | `{archived: false}` |

New field label: `archived` «مؤرشف».
