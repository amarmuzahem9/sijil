# Research: Link Message, Request Statuses and Notifications

**Feature**: 012 | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

No new dependency and no new service. Every decision below reuses what 005–011 built.

## R1. The link message is composed on the server, never stored

- **Decision**: a pure function `api/app/core/link_message.py` `compose(request) -> str | None` builds the
  §8.4 text from the request's stored columns. `RequestOut` gains one field `link_message: str | None`, set
  only when the request is not deleted and its status is `approved` or `linked`.
- **Rationale**: FR-005 wants the server to decide what goes in, so no hidden field can leak. The function
  takes only the allowed columns (number, full name, phone, username, tower name and code, plan, prices,
  address, landmark, lat/lng, marketer name), so the national ID, family number, images and OTP are out of
  reach by construction. Not storing it means a deletion (011) leaves nothing behind and names stay the
  ones stored at submission (FR-003).
- **Alternatives**: building it in the web from `RequestOut` (the way «نسخ التفاصيل» is built) — rejected:
  it needs the coordinates sent to the page and moves the "what may appear" rule to the client. Storing the
  text — rejected: one more copy of personal data for the erasure to remember.

## R2. Exact text

```
طلب ربط جديد | رقم الطلب: #T3C-1001
الاسم: {full_name}
الهاتف: {phone}
اليوزر: {username}
البرج: {tower_name} ({tower_code})
الفئة: {plan_name} | التجريبي {trial:,} د.ع | الثاني {second:,} د.ع
العنوان: {address}، {landmark}
الموقع: https://maps.google.com/?q={lat},{lng}
المسوّق: {marketer_name}
```

- Prices: Latin digits with `,` thousands separators, the same as `web/src/lib/money.ts` `formatMoney`.
- Address line: the non-empty parts of (address, landmark) joined by «، »; both empty → «العنوان: —».
- Coordinates: up to 6 decimals (≈ 0.1 m), trailing zeros removed, `.` decimal point (FR-004).
- `marketer_name` is the marketer's current name, like «نسخ التفاصيل» (spec edge case).
- Lines joined by `\n`, no trailing newline.
- Tests: a golden case per request type, the empty-address/landmark cases, and a property test that the
  output never contains the request's national ID or family number (SC-002).

## R3. Copy and WhatsApp share in the web

- **Copy**: `navigator.clipboard.writeText`; on failure the text block stays selectable (it is already shown)
  and the snackbar says «تعذّر النسخ، انسخ النص يدوياً». Same pattern as «نسخ التفاصيل» today.
- **Share**: a link to `https://wa.me/?text=<encodeURIComponent(text)>` opened in a new tab. With no number
  WhatsApp asks for the chat (FR-007). On a phone it opens the app, on desktop WhatsApp Web.
- **Alternative**: `navigator.share` — rejected: it offers every app, and the button promises WhatsApp.

## R4. Status transitions in one place

- **Decision**: `api/app/core/request_status.py` holds `TRANSITIONS = {None: {approved, pending_review},
  pending_review: {approved, rejected}, approved: {linked}, linked: {approved}}` and `check(old, new)` that
  raises `AppError("invalid_transition", 409)`. `submit`, `accept` and `reject` call it; 013 will call it for
  linking and its undo. A deleted request is refused before (011's `request_deleted`).
- **Rationale**: FR-011 and Principle VIII want every allowed and refused pair tested; a table-driven unit
  test covers all 4×5 pairs, including the two linked ones 013 uses.
- The database check `requests_status` stays as is; no migration needed for statuses.

## R5. Notifications: one table, written in the decision's transaction

- **Decision**: a table `notifications` (see [data-model.md](./data-model.md)). The row is added by
  `notification_service.add(db, request, kind, reason)` inside the same transaction as accept, reject or
  delete, before the commit. A refused second decision raises before reaching it, so it never writes
  (FR-017). A partial unique index on `(request_id, kind)` for `approved`, `rejected`, `deleted` makes a
  duplicate impossible even by mistake.
- **No personal data in the row** (FR-019): only marketer, request, kind, a reason **code**, created and read
  times. The list endpoint joins the request at read time: a live request gives its `full_name`, a deleted
  one gives `null` and `deleted: true`.
- **Reason**: rejection → the rejection reason code, shown by its fixed label (for «سبب آخر» the label only,
  never the admin's note); deletion → the deletion reason code; undo of link → filled by 013 (column is a
  free code, 013 decides its list).
- **Auto-acceptance** writes nothing (FR-016).
- **Alternatives**: deriving notifications from the audit log — rejected: the audit log is main-admin only and
  carries the rejection note. An event bus or job queue — rejected (Principle VI).

## R6. Unread counter refresh

- **Decision**: React Query `useQuery(['notifications','unread'], …, { refetchInterval: 15_000,
  refetchIntervalInBackground: false, refetchOnWindowFocus: true })` in `MarketerLayout`, so the badge works
  on every marketer page (FR-020, SC-003). The endpoint is a single indexed `count(*)`.
- **Rationale**: the project already polls drafts every 15 s (005) and rejected SSE/WebSocket (specs/002 research.md); 15 s
  meets SC-003 and costs one cheap query per open app.
- Opening the notifications page, marking read, and «تعليم الكل كمقروء» invalidate the count query.

## R7. Reading and paging

- `GET /api/notifications?before=<id>&limit=30`, newest first by `id` (ids increase with time). The page
  loads more on scroll with React Query `useInfiniteQuery` (FR-022).
- `POST /api/notifications/{id}/read` and `POST /api/notifications/read-all`. Both only touch the caller's
  rows; another marketer's id answers 404 (FR-023, Principle IX).
- Tapping a notification: mark read, then navigate to `/requests/{request_id}`. The request page already
  shows the deleted view for a deleted request (011).

## R8. Marketer search

- **Decision**: `GET /api/requests?q=…` (with or without `status`). A pure function
  `api/app/core/request_search.py` `classify(q)` picks one kind:
  1. `request_number.parse(q)` gives a number → match `number` (deleted rows included);
  2. else `normalize_phone(q)` is valid → match `phone` exactly;
  3. else the text cleaned like names (diacritics and tatweel removed, spaces collapsed) with at least 2
     letters → `full_name ILIKE '%…%'` with `%`, `_` and `\` escaped.
  Otherwise no search (the web does not call with < 2 characters).
- Always filtered by `marketer_id = caller` (FR-014). Deleted rows have `phone` and `full_name` null, so
  only the number finds them, with no extra rule.
- **Mirror**: `web/src/lib/requestSearch.ts` only decides "too short"; the server classifies.
- Results go across all statuses; the page shows them in place of the tab list while a query is typed.
- **Scale**: one marketer's requests (hundreds), no new index needed beyond `(marketer_id, submitted_at)`.
- **Logs** (found in batch 5, T053): uvicorn's access line carries the full URL, so the log filter
  hides the value of `q` (`q=[REDACTED]`, `app/logging_config.py`); the search text is a phone or a
  name and never reaches the logs (constitution Principle II, system.md §13).

## R9. The «تم الربط» tab and labels

- The tab calls `listRequests(['linked'])` like the others; it is empty until 013. The order is
  `submitted_at desc` now; 013 adds `linked_at` and orders by it (FR-012 fully testable there).
- `STATUS_LABELS.approved` becomes «مقبول (بانتظار الربط)» in `web/src/lib/requestStatus.ts`; every screen
  already reads labels and colours from that one file (FR-010). The tab title «مقبولة» stays.

## R10. Tests (Principle VIII)

| Level | What |
|---|---|
| pytest unit | `link_message.compose` golden cases and the no-sensitive-data property; `request_status` all pairs; `request_search.classify` from a fixture file |
| pytest integration | accept/reject/delete add exactly one notification; second decision adds none; auto-accept adds none; list shows name live and `null` after deletion; counts, read, read-all; 404 for another marketer; search by name/phone/number, never across marketers, deleted by number only; `link_message` present only for approved |
| Vitest | link message block (copy, share URL, hidden for pending/rejected/deleted); notification badge and list; search box |
| Playwright | `link-message-notifications.spec.ts`: marketer submits → admin accepts → badge 1 → open → link message copied; admin rejects then deletes another → notification shows «محذوف» without name |

Each new test is run red first (project rule).
