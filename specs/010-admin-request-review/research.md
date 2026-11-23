# Research: Admin Review of Pending Requests (010)

Inputs:
- [spec.md](./spec.md);
- `docs/system.md` v1.13 §6.4, §7.2, §10;
- the 008/009 code: `core/matches.py`, `core/decision.py`, `services/match_service.py`,
  `services/submit_service.py`, `services/numbers_edited.py`, and `ImageAccessLog`.

The Technical Context had no open items. Each item below is a design choice.

## R1. Where the decision is stored

**Decision**: new columns on `requests`:
- `rejected_at`, `rejected_by`, `rejection_reason` (code), `rejection_note`;
- `counts_commission` (boolean, not null, default true);
- `approval_warnings` (jsonb, null).

`approved_at` and `approved_by` already exist (008). A human approval sets `approved_by`. An automatic
approval keeps it null.

Check constraints:
- `rejected` ⇔ `rejected_at`, `rejected_by` and `rejection_reason` are set;
- `rejection_reason = 'other'` ⇒ `rejection_note` is not blank;
- `rejection_reason` is one of the five codes (R6).

**Rationale**: Principle IV wants the decision on the request itself. Columns with constraints keep a
request from being half-decided.

**Alternatives**:
- A separate `request_decisions` table. Rejected: there is at most one decision per request (no undo,
  §7.2), so a table adds a join for nothing.

## R2. One decision per request (FR-009)

**Decision**: accept and reject run in one transaction:
1. `SELECT … FOR UPDATE` on the request row;
2. check `status = 'pending_review'`, else 409 `already_decided` with the current status;
3. write the decision and commit.

A second admin waits on the row lock, then sees the new status.

**Rationale**: the row lock is the simplest guarantee. The status check runs under the lock, so
SC-003 holds.

**Alternatives**:
- An optimistic version column. Rejected: it needs a version round-trip from the page, and the
  outcome is the same.

## R3. Reason state

**Decision**: new columns on `request_reasons`:
- `state` text, CHECK `IN ('open','resolved','not_applicable')`, default `'open'`;
- `state_changed_at`, `state_changed_by` (null until a pin changes the state);
- `added_by` (null for submission rows, the admin for rows added by a re-check).

What a pin does to the reasons:
- `numbers_edited` becomes `resolved` («تم التثبيت») once every field in `details.fields` is pinned.
- A match-based row (`family_exists`, `numbers_conflict`) whose record no longer matches becomes
  `not_applicable` («لم يعد ينطبق»).
- A row that matches again goes back to `open`.
- A new match adds a row with `added_by` set. The existing UNIQUE constraint keeps one row per
  reason and record.
- `return` rows are never changed by a pin. A lost target only raises a warning (R5).
- Rows are never deleted.

**Rationale**: FR-014 says reasons are kept and only marked. Principle I wants every applicable reason
recorded.

## R4. Pinning numbers

**Decision**:
- Migration 0013 adds `submitted_national_id` and `submitted_family_number` to `requests`. They are
  filled from the current values and never written again, so the marketer's values stay visible after
  any pin.
- The original card reading is already on the request: `card_fields[field].original` for both
  fields, and `national_id_check.mrz` for the national ID. These go to the review page.
  `card_readings` (raw) is still never sent anywhere (Principle II).
- A new table `request_number_pins` keeps one row per pin: field, the pinned value, source
  (`reading`, `mrz`, `marketer`, `typed`), who and when. The current value lives in the request
  columns `national_id`, `family_number` and `family_key`.
- `POST …/pin` takes `{field, source, value?}`:
  - for `reading`, `mrz` and `marketer` the server takes the value itself, so the page cannot send a
    different one;
  - only `typed` takes `value`.
- Validation:
  - national ID: `normalize_national_id` must give 12 digits, else 422 `invalid_national_id`;
  - family number: kept as written, and its `family_key` must not be empty, else 422
    `invalid_family_number`.
- Pinning is allowed only while the request is `pending_review`. It runs under the request row lock,
  then the 008 advisory locks on the national ID and family keys (both old and new values, in the
  same order as submit), so a pin and a submission with the same numbers cannot both pass unseen.

**Rationale**: the original reading and the marketer's value stay as they were (Principle IV).
Values the server picks itself cannot be swapped on the way.

**Alternatives**:
- Keep the marketer's value only in the first pin row. Rejected: the page would need to find the
  earliest pin before it knows the marketer's value, and a request that was never pinned has no row
  at all.

## R5. Re-check and warnings

**Decision**: a pure function `core/review_check.py::review(type, return_refs, matches, edited)`
returns:
- the reason rows that should be open now: `family_exists` and `numbers_conflict` per record;
- the type change: `new` becomes `additional` if a family-only match exists (FR-015). Nothing else
  changes the type;
- `warnings`, a list of kinds:
  - `same_person`: the type is `new` or `additional` and a record has the same national ID and
    family number;
  - `id_conflict`: a national-ID-only match that was not on the request before the pin;
  - `return_target_lost`: a `return` with basis `identity` whose stored target records no longer
    match on both numbers.

`matches` comes from `match_service.find_matches` with the request's phone and current numbers, with
the request itself removed (source `sijil`, its own id). Rejected requests never count, as in 008.

When the re-check runs:
- after each pin, inside the pin transaction, to update the reasons (R3) and the type;
- on every read of the request file, to show the warnings (no write). The warnings stay current even
  without a pin, for example when 013/014 bring in new records;
- at accept, under the row lock, to compute the final warnings.

**Rationale**: one rule set for all three moments, tested as a pure function like `decide`
(Principle VIII).

## R6. Rejection reasons (FR-019)

**Decision**: fixed codes and their Arabic labels, kept in the backend and mirrored in the web
labels:

| Code | Arabic |
|---|---|
| `card_unclear` | صورة البطاقة غير واضحة |
| `numbers_mismatch` | الأرقام غير مطابقة للبطاقة |
| `under_15_days` | المتبقي من الاشتراك الأول أقل من 15 يوماً |
| `active_subscription` | المشترك لديه اشتراك فعّال |
| `other` | سبب آخر |

Rules:
- `other` needs a note of 3 to 300 characters after trimming;
- with any other code a note is not accepted (422), so the marketer sees exactly the label.

The marketer sees the label, or for `other` the note.

**Rationale**: system.md v1.13 makes the list fixed (no settings page). Short notes limit what can
leak.

## R7. Accept with the commission answer and with warnings

**Decision**: `POST …/accept` takes `{counts_commission?: bool, confirm_warnings?: list[str]}`.

`counts_commission`:
- for `return` it is required (422 `commission_answer_required` without it);
- for other types it must be absent and is stored as true.

`confirm_warnings`:
- the server recomputes the warnings under the lock (R5);
- if they are not empty and not exactly the set the page confirmed, it answers 409
  `warnings_unconfirmed` with the current kinds, and the page shows the second confirmation
  «القبول رغم التحذير؟»;
- on success the kinds are stored in `approval_warnings`;
- the audit entry is `request.approved` with `despite_warnings: [...]`.

**Rationale**: a warning that shows up between page load and the press still needs its own
confirmation.

## R8. Linked records

**Decision**: a resolver registry, `services/linked_records.py`, works like the match sources:
- `register_resolver(source, fn(db, refs) -> list[LinkedRecordOut])`;
- in 010 only `sijil` is registered. It reads the request rows and returns name, username, phone,
  tower code and name, registration date (submitted_at), current status, image ids and expiry (null);
- 013 and 014 register `legacy` and `sas`, and SAS fills `expiry` («حسب آخر استيراد»).

The file groups linked records by reason row and shows the basis label. A record whose resolver is
missing shows «سجل غير متوفر» with its source.

**Rationale**: the same extension point 008 used for sources. 010 does not need to know the future
import shapes.

## R9. Image access for review (FR-005)

**Decision**: new route `GET /api/admin/request-images/{image_id}`, for the main admin and admins with
`review`; anyone else gets 404, as for draft images.

Each open writes `image_access_log` with `purpose='view'`. Migration 0013:
- makes `image_access_log.draft_id` nullable;
- adds `request_id` (plain bigint, no FK, like `draft_id`).

A request image row writes `request_id`, and also `draft_id = request.draft_id` so the history stays
in one place. A missing file gives 404 `image_not_found`, logged without the path, and the page shows
«الصورة غير متوفرة».

Images of linked sijil records use the same route, under the same permission.

## R10. Admin home counts (FR-021)

**Decision**: `GET /api/admin/home`, open to any admin, returns `{today: Counts, month: Counts}`,
where Counts is `{submitted, approved, pending, linked, rejected}`.

The bounds are Baghdad days and months, from `timeutil`. A new `baghdad_today_bounds()` helper is
added next to `baghdad_month_bounds`.

| Count | Rule |
|---|---|
| `submitted` | `submitted_at` in range |
| `approved` | `approved_at` in range (the automatic approval counts at submission) |
| `rejected` | `rejected_at` in range |
| `pending` | current `status='pending_review'`, the same number in both rows |
| `linked` | always 0 in 010. 012 adds `linked_at` and fills it |

The response holds counts only.

**Rationale**: system.md v1.13 §10 item 1 says by what time each count goes.

## R11. Marketer view (FR-011)

**Decision**: `RequestOut` gains `rejection_reason` (code), `rejection_label` (Arabic, or the note for
`other`) and `rejected_at`.

It still carries no linked record, no reason details, no deciding admin and no warnings. `result` is
already `rejected` for a rejected status.

Web pages:
- `RequestResult` and `SubmittedTab` show «تم رفض الطلب» with the label;
- an approved request shows «تمت الموافقة» with the username and «نسخ التفاصيل» (008).

`tests/integration/test_marketer_privacy.py` is extended after accept, reject and pin.

## R12. Audit and logs (FR-017)

| Action | entity | before | after |
|---|---|---|---|
| `request.approved` | request / number | `{status: "pending_review"}` | `{status: "approved", type, counts_commission, despite_warnings}` |
| `request.rejected` | request / number | `{status: "pending_review"}` | `{status: "rejected", reason, note}` |
| `request.numbers_pinned` | request / number | `{type, field_changed: bool}` | `{field, source, type, reasons_added, reasons_not_applicable, numbers_edited_resolved}` |

The rules:
- No national ID, family number, phone, names or image file names.
- The rejection note is the admin's own text, shown to the marketer and audited as written.
- Log lines carry the number and action only.
- `test_log_safety` and `test_audit_completeness` are extended.
- The audit viewer labels (`web/src/lib/auditFormat.ts`) get the three actions.

## R13. Pending list (FR-002)

**Decision**: `GET /api/admin/requests/pending?reason=…`:
- oldest `submitted_at` first;
- returns items and `total`, with no paging in 010 (expected tens of items);
- `reason` filters on rows whose state is not `not_applicable`;
- each item lists its active reason codes.

Indexes:
- `request_reasons (request_id, reason)` already exists through the unique constraint;
- a partial index `requests_pending_idx (submitted_at) WHERE status='pending_review'` is added.

## R14. Tests (Principle VIII)

Each new test runs red before its code.

- **Unit**:
  - `test_review_check.py`: every type × match kind, and warning kinds;
  - `test_rejection_reasons.py`: note rules;
  - `test_timeutil` for the day bounds.
- **Integration**:
  - `test_admin_pending_list.py`: list, filter, permissions;
  - `test_admin_decide.py`: accept, reject, commission, already decided;
  - `test_admin_decide_concurrency.py`;
  - `test_admin_pin.py`: pin sources, validation, re-check, type change, warnings;
  - `test_admin_request_images.py`: access and log;
  - `test_admin_home.py`: counts, Baghdad edge at 23:30;
  - `test_migration_0013.py`;
  - extended `test_marketer_privacy`, `test_log_safety`, `test_audit_completeness`,
    `test_match_sources` (a rejected request no longer matches).
- **Vitest**: decision panel (commission dialog, reject reasons, warning confirmation), pin panel,
  pending list filter, admin home.
- **Playwright** `e2e/tests/admin-review.spec.ts`: a marketer submits a family request, an admin
  accepts it, and the marketer sees «تمت الموافقة». The admin rejects a second one with «سبب آخر»,
  and the marketer sees the note. The admin pins a number that raises a warning and accepts after the
  second confirmation.
