# API Contract: Auth & Session (001)

Base path `/api`, JSON, same origin as the web app. Errors always use:

```json
{ "code": "invalid_credentials", "message": "رقم الهاتف أو كلمة السر غير صحيحة" }
```

Messages never echo submitted values. Times are ISO-8601 UTC.

Authenticated endpoints need `Authorization: Bearer <access_token>`. The refresh cookie is
`sijil_refresh` (`HttpOnly; Secure; SameSite=Strict; Path=/api/auth; Max-Age=2592000`).

## Common auth errors

| HTTP | code | When |
|---|---|---|
| 401 | `not_authenticated` | Missing or invalid token |
| 401 | `token_expired` | Access token expired → client calls `/auth/refresh` once |
| 401 | `session_revoked` | Session signed out or revoked |
| 403 | `account_inactive` | «الحساب موقوف، راجع الإدارة» (client clears state) |
| 403 | `password_change_required` | `must_change_password` is set and the route is not allowed |
| 403 | `forbidden` | Role not allowed for the route |

## POST /api/auth/login

Request: `{ "phone": "string", "password": "string" }`

| HTTP | code | Notes |
|---|---|---|
| 200 | — | Body below; sets the refresh cookie and creates a session |
| 422 | `invalid_phone` | «رقم غير صالح». Not counted against any account |
| 401 | `invalid_credentials` | Wrong password **or** unknown phone (same message, same timing) |
| 423 | `account_locked` | Message includes the remaining minutes; `retry_after_seconds` in the body; `Retry-After` header |
| 403 | `account_inactive` | Correct password, inactive account |
| 429 | `too_many_attempts` | Per-IP limiter |

200 body:

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 1, "name": "…", "phone": "07801234567",
    "role": "super_admin", "permissions": [], "must_change_password": true
  }
}
```

## POST /api/auth/refresh

Uses the refresh cookie and has no body. Rotates the cookie and extends the session expiry.

- 200: same body shape as login.
- 401 `session_revoked`: missing, unknown, expired, or reused token (reuse also revokes the session).
- 403 `account_inactive`.

## POST /api/auth/logout

Auth optional, uses the cookie. It revokes the current session only and clears the cookie.
Always 204.

## GET /api/auth/me

Auth required. Allowed while `must_change_password = true`. 200: the `user` object.

## POST /api/auth/change-password

Auth required. Allowed while `must_change_password = true`.

Request: `{ "current_password": "string", "new_password": "string" }`. The confirmation field is
checked client-side only.

| HTTP | code | Notes |
|---|---|---|
| 200 | — | New tokens (same body as login). Clears the flag, revokes **other** sessions, rotates the current one; audit `user.password_changed` |
| 400 | `wrong_current_password` | «كلمة السر الحالية غير صحيحة» |
| 422 | `weak_password` | «كلمة السر يجب أن تكون 8 أحرف على الأقل» |
| 422 | `same_password` | «كلمة السر الجديدة يجب أن تختلف عن الحالية» |

## GET /api/marketer/dashboard

Role `marketer` only.

200: `{ "linked_this_month": 0, "month_label": "تشرين الثاني 2026" }`

The value is a fixed 0 until feature 011. The month is computed in Asia/Baghdad.

## GET /api/admin/ping

Roles `super_admin` and `admin`. 200: `{ "ok": true }`. A placeholder used by the admin shell and
by role-refusal tests. A marketer gets 403 `forbidden`.

## GET /api/health

No auth. 200: `{ "status": "ok", "db": "ok" }`. Used by the compose healthcheck. Reveals no
version or configuration.
