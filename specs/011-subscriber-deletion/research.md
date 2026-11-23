# Research: Subscriber Deletion (011)

Decisions for [plan.md](./plan.md). Sources: [spec.md](./spec.md), `docs/system.md` v1.15 §7.4,
constitution v1.3.0 Principle III, and the code left by 008–010.

## R1. Erase in place, on the same row

**Decision**: Erasure sets the personal columns of `requests` to `NULL` on the same row. The columns
become nullable. One check constraint ties them to the deletion mark:
- a row with no deletion mark keeps every column that is required today;
- a row with a deletion mark holds `NULL` in every personal column.

The erased columns:
- names: `first_name` … `mother_surname`, `full_name`, `no_surname`;
- identity: `national_id`, `national_id_input`, `submitted_national_id`, `family_number`,
  `submitted_family_number`, `family_key`;
- card: `birth_date`, `issue_date`, `expiry_date`, `birth_place`, `issuing_authority`, `card_fields`,
  `national_id_check`, `card_readings`;
- location: `location_lat`, `location_lng`, `location_source`, `location_accuracy_m`, `address`,
  `landmark`;
- contact: `phone`, `username`;
- the reviewer's note: `rejection_note`.

The existing checks that look at these columns are rewritten as `deleted_at IS NOT NULL OR (…)`:
- `requests_no_surname`;
- `requests_surname_required`;
- `requests_rejection_note`.

The format checks (`national_id`, `family_key`, `phone`) pass on `NULL` already.

**Rationale**: The row, its id and its number stay, so everything that points to it keeps working:
- reasons on other requests;
- audit lines (`entity_id` = number);
- the marketer's list;
- the counts.

`NULL` also takes the row out of every match by itself, because `NULL = value` is never true. The
database can show that nothing personal is left (SC-001).

**Alternatives considered**:
- *Move personal data to a side table and delete that row.* Cleaner on paper, but it is a large
  refactor of 008–010 code for one rare action.
- *Overwrite with placeholder text («محذوف»).* Placeholders would pass format checks badly (phone,
  national ID), and they could match each other.
- *Delete the row.* Rejected by the owner: commission and reports need the row.

## R2. The deletion mark is separate from the status

**Decision**: Three new columns:
- `deleted_at`;
- `deleted_by` (a link to `users`);
- `deletion_reason`, one of `duplicate`, `test`, `entry_error`, `other`.

A pair check keeps all three set together or all three empty. `status` keeps its value
(`pending_review` or `rejected`). A check allows a mark only on those two statuses. The partial index
`requests_pending_idx` gains `AND deleted_at IS NULL`.

**Rationale**:
- The owner kept "الحالة" on the row.
- Counts by decision time (`rejected_at`) stay right without special cases (FR-016).
- No new status means no change to the §7.2 transitions.

**Alternatives considered**:
- *A new status `deleted`.* It would lose the status at deletion, and it would add a transition to
  §7.2.
- *A free-text reason.* Rejected by the owner (Q1).

## R3. One deletion per request, and no decision after it

**Decision**: `deletion_service.delete()` reads the row with `SELECT … FOR UPDATE`, the same row lock
as `review_service._lock_pending`. It then checks, in order:
1. the caller has `review` and `delete`. Without `review`: 404 `request_not_found`, as today. With
   `review` but without `delete`: 403 `forbidden`;
2. the request is not deleted already: 409 `request_deleted`;
3. the status is `pending_review` or `rejected`: otherwise 409 `request_not_deletable`;
4. the reason is in the list: otherwise 422;
5. the typed number matches (R6): otherwise 422 `number_mismatch`.

`_lock_pending` (accept, reject, pin) gains a check: a row with `deleted_at` gets 409 `request_deleted`
before the status check, because a deleted pending request still has `status = 'pending_review'`.

**Rationale**:
- Delete and accept on the same request wait on the same lock, so the first one wins (edge case "two
  admins").
- No 008 advisory locks are needed. The erasure only removes match keys, and a submit that runs at the
  same time either sees the old row or sees no keys.

## R4. Images: rows in the transaction, files after commit

**Decision**: These run in the same transaction:
- the `request_images` rows are deleted;
- the `request_number_pins` rows are deleted.

After the commit, each file is removed with `image_store.unlink_quietly`. A missing file is logged by
image id only. If the process dies between the commit and the unlink, the file has no row any more,
so `prune-uploads` removes it (`referenced_file_names` reads `request_images`). This is the same
pattern as draft deletion (005).

`image_access_log` rows stay. They hold ids, a side and times, no personal data, and no foreign key.

**Rationale**:
- The data is either fully erased or not erased at all (edge case "erasure fails half-way").
- A retry is safe: nothing is left half-done, and an old image link gives 404 (US1 scenario 6).

## R5. OTP codes for the phone

**Decision**: In the same transaction, delete the `otp_challenges` rows with the request's phone and
`request_id IS NULL`. These are the rows whose draft was submitted or deleted. A challenge still
attached to a live draft (another marketer typing the same phone right now) is kept, so that draft's
running verification is not broken.

**Rationale**: The hourly limit counts rows by phone (`otp_service._check_limits`). Removing the
request's own rows resets the limit for that phone (US2 scenario 3).

**Alternatives considered**:
- *Delete every row for the phone.* It could cancel another draft's live code.

## R6. Reading the typed number

**Decision**: A pure function `core/request_number.parse(text) -> int | None`. It:
1. converts Arabic-Indic and Eastern Arabic digits to Western digits;
2. strips spaces and a leading `#`;
3. strips an optional `T3C-` (any case);
4. requires digits only.

The same function serves the delete confirmation (FR-006) and «فتح طلب برقمه» (FR-022). The web
mirrors it in `lib/requestNumber.ts` to enable the button. Both are tested against one fixture,
`tests/fixtures/request_number_cases.json`.

## R7. The permission `delete`

**Decision**:
- `delete` is added to `ADMIN_PERMISSIONS`, after `commissions`;
- the `users_permissions_known` check is updated in the migration;
- the label is «حذف مشترك (طلب بالانتظار أو مرفوض)».

The main admin holds it implicitly, through `has_any_permission`. The permissions screen already
shows the main admin's switches as always on. The change is audited by the existing
`user.permissions_changed` entry. No new page goes into `PAGE_ACCESS`. The page fixture stays the
same, and only the permission list fixture grows.

## R8. Open a request by its number

**Decision**: `GET /admin/requests/by-number/{text}`, with `review`. It parses with R6 and returns
`{id}` of the request with that number, in any status. A missing number and a caller without `review`
both get 404 `request_not_found`. The box sits at the top of «طلبات بالانتظار» and navigates to
`/admin/pending/:id`, the existing request file.

**Rationale**: It is the smallest way to reach a rejected request before the subscriber search (018).
It reuses the 010 file page.

## R9. The file of a deleted request

**Decision**: `review_service.to_file` returns `deleted: {at, by_name, reason}` and only the kept
fields. All personal fields are `null`, and `images`, `pins`, `linked records` and `warnings` are
empty. The live re-check (`live_check`) is skipped for a deleted request. The page shows the banner
«تم حذف بيانات هذا الطلب» and hides the decision, pin and delete panels.

## R10. Linked records pointing to a deleted request

**Decision**: The `sijil` resolver in `linked_records` returns `LinkedRecord(available=False,
deleted=True, number_label=…)` for a deleted row. `LinkedRecordCard` shows «سجل محذوف (#T3C-…)». The
reasons on other requests are not touched (FR-015).

## R11. The marketer's view

**Decision**:
- `RequestOut` and `RequestListItem` make the erased fields nullable;
- a new `result` value `deleted` is added;
- new fields `deleted_at` and `deletion_label` are added.

For a deleted request, the marketer API returns only:
- `number_label`;
- `tower_code` and `tower_name`;
- `submitted_at`;
- `deleted_at` and `deletion_label`;
- the status.

`SubmittedTab` shows the grey tag «محذوف» and the reason. `RequestResult` shows the same fields
without the copy or share buttons. The rejection label for a deleted rejected request is the
reason's name only, because the note is erased.

## R12. Audit and logs

**Decision**: One entry is written:
- action `request.deleted`, `entity_type="request"`, `entity_id=str(number)`;
- `before={"status": <status>, "image_count": n, "pin_count": m}`;
- `after={"deleted": true, "reason": <code>}`.

The audit page formatter shows «حذف مشترك» and the Arabic reason.

The audit API adds `entity_deleted: true` to entries whose request is deleted. For a
`request.numbers_pinned` line, the formatter then shows «سجل محذوف» in place of the pin link (FR-019).
Old lines are never rewritten.

The application log line is `request deleted number=… reason=…` (FR-020).

`tests/integration/test_log_safety.py` and `test_audit_completeness.py` are extended to cover the
new action.

## R13. Admin home counts

**Decision**: The `pending` count adds `deleted_at IS NULL`. `submitted`, `approved` and `rejected`
count by time, as before, and include deleted rows (SC-004).

## R14. Tests (Principle VIII)

Each new test is run red before its code (project rule).
- **Unit**:
  - `request_number.parse` against the fixture;
  - the reason list and labels.
- **Integration**:
  - delete pending, and delete rejected (fields `NULL`, files gone, pins and image rows gone, OTP rows
    gone, audit line);
  - refusals: no `delete`, no `review`, approved, linked, already deleted, wrong number, bad reason;
  - concurrency of delete with accept, and of delete with delete;
  - accept, reject and pin after delete;
  - phone, national ID and family number free after delete (match_service and the draft checks);
  - the next number is not reused;
  - linked record «سجل محذوف»;
  - the marketer view;
  - home counts;
  - by-number lookup;
  - the migration check constraints;
  - log and audit safety.
- **Vitest**:
  - the delete dialog (button disabled until a reason is chosen and the number matches);
  - the deleted banner;
  - the «محذوف» tag in the marketer list;
  - the by-number box;
  - the `delete` switch.
- **Playwright**: `e2e/tests/subscriber-deletion.spec.ts`, with a synthetic test request only (no
  real card images, per CLAUDE.md).
