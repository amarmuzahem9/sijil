# API Contract: Account Archive (003)

The conventions are those of [002 api.md](../../002-accounts-permissions/contracts/api.md). Every
route below requires the **main admin** (`require_roles("super_admin")`); anyone else gets 403
`forbidden`.

| Method & path | Body | Success | Errors | Audit |
|---|---|---|---|---|
| `GET /api/admin/archive` | — | 200 `{items: ArchivedAccountOut[]}`, newest `archived_at` first | — | — |
| `POST /api/admin/archive/{user_id}` | — | 200 `AccountOut` (`is_active: false`); revokes all sessions (`archived`) | 404 `not_found`: unknown id, main admin, or already archived | `user.archived` |
| `POST /api/admin/archive/{user_id}/restore` | — | 200 `AccountOut` (`is_active: false`) | 404 `not_found`: unknown id or not archived | `user.restored` |

```json
// ArchivedAccountOut
{
  "id": 12, "name": "…", "phone": "07700000301", "role": "marketer",
  "permissions": [], "archived_at": "2026-11-22T10:00:00Z",
  "archived_by": {"id": 1, "name": "…", "role": "super_admin"}
}
```

## Changes to 002 routes

- `GET /api/admin/admins` and `GET /api/admin/marketers` omit archived accounts.
- Every `/{id}` route under `/api/admin/admins` and `/api/admin/marketers` returns 404 for an
  archived id.
- Sign-in and any request by an archived account return 403 `account_inactive`.
