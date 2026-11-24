---

description: "Task list for feature 012: Link Message, Request Statuses and Notifications"
---

# Tasks: Link Message, Request Statuses and Notifications

**Input**: Design documents from `specs/012-link-message-notifications/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run
red before its code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: the fake card reader, made-up numbers (national ID `199000000001`, family number
  `1234A5678901234567`), made-up names and phones. No real card images or subscribers (CLAUDE.md).
- Requests come from `api/tests/helpers/requests.py::request_factory` (with `mark_deleted` for a deleted
  one), or from `api/tests/helpers/submit.py` when the real submission is needed; admins from
  `api/tests/helpers/review.py::admin_with`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T012 |
| 2 | 3 (US1 link message) | T013–T022 |
| 3 | 4–5 (US2 notifications on decisions, US4 deleted requests) | T023–T040 |
| 4 | 6–7 (US3 search and tabs, US5 linked events ready) | T041–T051 |
| 5 | 8 (Polish, e2e, manual test) | T052–T058 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, then `docker compose exec api pytest` and
  `cd web && npm test` are green on the branch before any change; note the counts in the batch report.
- [x] T002 [P] Add error codes `invalid_transition` (409, «لا يمكن تغيير حالة الطلب بهذا الشكل») and
  `notification_not_found` (404, «الإشعار غير موجود») with their Arabic messages in `api/app/errors.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the transition table and the notifications table that US1–US5 rely on.

### Tests (write first, run red)

- [x] T003 [P] Unit test every (from, to) pair of §7.2 — allowed: submission→approved,
  submission→pending_review, pending_review→approved, pending_review→rejected, approved→linked,
  linked→approved; every other pair raises `invalid_transition` — in `api/tests/unit/test_request_status.py`
  (research R4, data-model.md › Status transitions).
- [x] T004 [P] Migration test in `api/tests/integration/test_migration_0015.py`: the table exists after
  upgrade and is gone after downgrade to 0014; the checks refuse a bad `kind`
  (data-model.md `notifications.kind`), a `reason` on `approved`/`linked` and a missing `reason` on
  `rejected`/`deleted` (data-model.md `notifications.reason`, `notifications_reason_kind`); the unique index
  refuses a second `approved`/`rejected`/`deleted` row for one request but allows two `linked` rows
  (data-model.md `notifications_once`); `marketer_id` and `request_id` are required
  (data-model.md `notifications.marketer_id`, `notifications.request_id`).
- [x] T005 [P] Integration test of `notification_service` in `api/tests/integration/test_notification_service.py`:
  `add` stores only marketer, request, kind, reason code and `created_at` from `utc_now()`
  (data-model.md `notifications.created_at`); `unread_count`, `mark_read` (idempotent, keeps first
  `read_at`, data-model.md `notifications.read_at`), `mark_all`, and `page(before, limit)` newest first by id
  with `next_before` (research R7).

### Implementation

- [x] T006 Create `api/app/core/request_status.py` with `TRANSITIONS` and `check(old, new)` raising
  `AppError("invalid_transition", 409)` (research R4); T003 green.
- [x] T007 Call `request_status.check` in `submit_service.submit` (None→approved/pending_review) in
  `api/app/services/submit_service.py`, and in `review_service.accept`/`reject` after `_lock_pending` in
  `api/app/services/review_service.py`; existing suites stay green.
- [x] T008 Write migration `api/migrations/versions/0015_notifications.py` (revises `0014`) creating
  `notifications` with data-model.md `notifications.id`, `notifications.marketer_id`,
  `notifications.request_id`, `notifications.kind`, `notifications.reason`, `notifications.created_at`,
  `notifications.read_at`, the check `notifications_reason_kind` and the indexes `notifications_once`,
  `notifications_marketer_id`, `notifications_unread`; T004 green.
- [x] T009 [P] Create the model `api/app/models/notification.py` (data-model.md › Model `Notification`),
  registered in `api/app/models/__init__.py`.
- [x] T010 [P] Create `api/app/schemas/notifications.py`: `NotificationOut` (id, kind, request_id,
  number_label, full_name, deleted, reason_label, created_at, read_at), `NotificationPage` (items,
  next_before), `UnreadCount` (count) per contracts/api.md.
- [x] T011 Create `api/app/services/notification_service.py` with `add(db, request, kind, reason=None)` (no
  commit; joins the caller's transaction), `page`, `unread_count`, `mark_read`, `mark_all`; `page` joins
  `requests` to return `full_name` live, `null` + `deleted: true` for a deleted request, and `reason_label`
  from `rejection_reasons.LABELS` / `deletion_reasons.LABELS` (never the note) (research R5); T005 green.
- [x] T012 Run the full api suite green and commit batch 1.

**Checkpoint**: batch 1 ends. The suites are green. Commit.

Batch 1 report: baseline api 1128 / web 391 green. Red first: T003 (no module `request_status`),
T004 (2 failed: no table), T005 (no module `notification`). Green after T006–T011: 30 new tests;
full api suite 1158 passed; web unchanged (391).

---

## Phase 3: User Story 1 - Copy or share the link message (Priority: P1) 🎯 MVP

**Goal**: an accepted request shows the §8.4 link message with copy and WhatsApp share.

**Independent Test**: spec.md US1.

### Tests for User Story 1 (write first, run red)

- [ ] T013 [P] [US1] Unit tests in `api/tests/unit/test_link_message.py`: golden text for new, additional and
  return (historical username); «البرج: اسم البرج (رمز البرج)»; prices with `,`; address-only,
  landmark-only and both-empty lines; coordinates to 6 decimals without trailing zeros; `None` for
  pending, rejected and deleted; the output never contains the request's national ID or family number
  (research R2, SC-002).
- [ ] T014 [P] [US1] Integration test in `api/tests/integration/test_link_message_api.py`:
  `GET /api/requests/{id}` and the submit response carry `link_message` only for approved (auto and by
  admin); `null` for pending, rejected and deleted; another marketer gets 404 (contracts/api.md, FR-009).
- [ ] T015 [P] [US1] Vitest `web/src/__tests__/linkMessage.test.tsx`: the card renders the text for an
  approved request; «نسخ رسالة الربط» calls the clipboard and shows «تم النسخ»; clipboard failure shows
  «تعذّر النسخ، انسخ النص يدوياً»; «مشاركة بالواتساب» links to `https://wa.me/?text=` + encoded text; no card
  for pending, rejected or deleted; «نسخ التفاصيل» still present.

### Implementation for User Story 1

- [ ] T016 [US1] Create `api/app/core/link_message.py` `compose(request) -> str | None` reading only the
  allow-listed columns (research R1–R2); T013 green.
- [ ] T017 [US1] Add `link_message: str | None = None` to `RequestOut` in `api/app/schemas/requests.py`
  (data-model.md › Changed: `RequestOut`) and set it in `submit_service.to_out` (`_deleted_out` keeps it
  null) in `api/app/services/submit_service.py`; T014 green.
- [ ] T018 [P] [US1] Add `link_message: string | null` to `SubmittedRequest` in `web/src/lib/requests.ts`.
- [ ] T019 [P] [US1] Create `web/src/lib/linkMessage.ts` (`whatsappUrl(text)`, `copyText(text)` returning
  success).
- [ ] T020 [US1] Create `web/src/components/LinkMessageCard.tsx` (title «رسالة الربط», the text in a
  selectable pre-wrap block, the two buttons, the snackbar) using T019.
- [ ] T021 [US1] Show `LinkMessageCard` in `web/src/pages/marketer/RequestResult.tsx` when `link_message` is
  set, below the details and above «نسخ التفاصيل»; remove the "comes with feature 012" comment; T015 green.
- [ ] T022 [US1] Run api and web suites green, `npm run lint`, and commit batch 2.

**Checkpoint**: batch 2 ends. US1 works on its own. Commit.

---

## Phase 4: User Story 2 - The marketer is notified when an admin decides (Priority: P1)

**Goal**: accept and reject create one notification; the badge, list, read and read-all work.

**Independent Test**: spec.md US2.

### Tests for User Story 2 (write first, run red)

- [ ] T023 [P] [US2] Extend `api/tests/integration/test_admin_decide.py`: accept adds one `approved` row for
  the request's marketer; reject adds one `rejected` row with the reason code («other» → label «سبب آخر»,
  no note); a refused accept/reject (`already_decided`, `warnings_unconfirmed`, 422) adds none.
- [ ] T024 [P] [US2] Extend `api/tests/integration/test_admin_decide_concurrency.py`: two admins deciding
  the same request → exactly one notification (FR-017).
- [ ] T025 [P] [US2] In `api/tests/integration/test_notifications.py`: auto-accepted submission adds no
  notification (FR-016); `GET /api/notifications` newest first with paging; `unread-count`; `read` and
  `read-all`; another marketer's id → 404 `notification_not_found`; admins get 403; the list never shows
  another marketer's rows (FR-023).
- [ ] T026 [P] [US2] Extend `api/tests/integration/test_marketer_privacy.py`: notification responses carry no
  phone, national ID, family number, address, note or other subscriber's data.
- [ ] T027 [P] [US2] Vitest `web/src/__tests__/notifications.test.tsx`: titles per kind (contracts/api.md),
  number, name, reason, Baghdad time; unread rows styled; tapping marks read and navigates to
  `/requests/{id}`; «تعليم الكل كمقروء»; empty state «لا توجد إشعارات».
- [ ] T028 [P] [US2] Vitest `web/src/__tests__/marketerBadge.test.tsx`: the bottom-bar and side-bar icon show
  the unread count, nothing at 0, and refetch on the 15 s interval (fake timers).

### Implementation for User Story 2

- [ ] T029 [US2] Call `notification_service.add(..., "approved")` in `accept` and `add(..., "rejected",
  body.reason)` in `reject` before the commit, in `api/app/services/review_service.py`; T023, T024 green.
- [ ] T030 [US2] Create `api/app/api/notifications.py` (marketer-only routes per contracts/api.md) and include
  it in `api/app/main.py`; T025, T026 green.
- [ ] T031 [P] [US2] Create `web/src/lib/notifications.ts` (types, `KIND_TITLES`, `listNotifications(before)`,
  `unreadCount()`, `markRead(id)`, `markAllRead()`, query keys).
- [ ] T032 [US2] Add the unread badge to the «الإشعارات» item in `web/src/layouts/MarketerLayout.tsx` with
  React Query `refetchInterval: 15_000`, `refetchIntervalInBackground: false` (research R6); T028 green.
- [ ] T033 [US2] Create `web/src/pages/marketer/Notifications.tsx` (infinite list, tap = read + navigate,
  «تعليم الكل كمقروء», invalidates the count); route it in `web/src/router.tsx` and remove
  `MarketerNotifications` from `web/src/pages/marketer/placeholders.tsx`; T027 green.

---

## Phase 5: User Story 4 - Deleted requests and notifications (Priority: P2)

**Goal**: deletion notifies with number and reason only; older notifications of a deleted request show
«محذوف» and no name.

**Independent Test**: spec.md US4.

### Tests for User Story 4 (write first, run red)

- [ ] T034 [P] [US4] Extend `api/tests/integration/test_deletion.py`: a deletion adds one `deleted` row with
  the deletion reason code; a refused deletion (`request_not_deletable`, `number_mismatch`,
  already deleted) adds none.
- [ ] T035 [P] [US4] In `api/tests/integration/test_notifications.py`: a `rejected` notification of a request
  later deleted returns `full_name: null`, `deleted: true`; the `deleted` notification has
  `reason_label` = the deletion reason's label (SC-005).
- [ ] T036 [P] [US4] Vitest case in `web/src/__tests__/notifications.test.tsx`: a deleted row shows the
  number and «محذوف», no name; tapping opens `/requests/{id}` (the 011 deleted view).

### Implementation for User Story 4

- [ ] T037 [US4] Call `notification_service.add(db, request, "deleted", body.reason)` before the commit in
  `api/app/services/deletion_service.py`; T034, T035 green.
- [ ] T038 [US4] Render the deleted row (grey «محذوف» tag from `DELETED_TAG`) in
  `web/src/pages/marketer/Notifications.tsx`; T036 green.
- [ ] T039 [US4] Point the 011 note "notifications come in a later feature" to 012:
  add a one-line pointer to 012 in `specs/011-subscriber-deletion/spec.md` Assumptions.
- [ ] T040 [US4] Run api and web suites green, lint, and commit batch 3.

**Checkpoint**: batch 3 ends. Commit.

---

## Phase 6: User Story 3 - Requests list with search, tabs and colours (Priority: P2)

**Goal**: search own requests by name, phone, number; «تم الربط» tab real; labels per §7.2.

**Independent Test**: spec.md US3.

### Tests for User Story 3 (write first, run red)

- [ ] T041 [P] [US3] Fixture `api/tests/fixtures/request_search_cases.json` and unit test
  `api/tests/unit/test_request_search.py` for `classify(q)`: number forms («1004», «T3C-1004», «#t3c-١٠٠٤»),
  phone forms («0780 123 4567», «+964 780…», Arabic digits), names with diacritics/tatweel/extra spaces,
  `%`/`_` escaped, < 2 letters → none (research R8).
- [ ] T042 [P] [US3] Integration test `api/tests/integration/test_request_search_api.py`: own matches across
  statuses; never another marketer's; deleted found by number only; `q` of 1 character → 422
  (contracts/api.md).
- [ ] T043 [P] [US3] Vitest `web/src/__tests__/requestSearch.test.tsx`: typing ≥ 2 characters shows results
  with status chips in place of the tab list; clearing returns to the tab; the «تم الربط» tab requests
  `status=linked`; the label «مقبول (بانتظار الربط)».

### Implementation for User Story 3

- [ ] T044 [US3] Create `api/app/core/request_search.py` `classify(q)`; T041 green.
- [ ] T045 [US3] Add `q` to `GET /api/requests` in `api/app/api/requests.py` and to `submit_service.list_own`
  in `api/app/services/submit_service.py`; T042 green.
- [ ] T046 [P] [US3] Set `STATUS_LABELS.approved` to «مقبول (بانتظار الربط)» in
  `web/src/lib/requestStatus.ts` and fix any test that asserted «مقبول».
- [ ] T047 [US3] Add `q` to `listRequests` in `web/src/lib/requests.ts`, create
  `web/src/lib/requestSearch.ts` (minimum length), add the search box and the linked tab (via
  `SubmittedTab` with `['linked']`) in `web/src/pages/marketer/Requests.tsx`; T043 green.

---

## Phase 7: User Story 5 - Linked notifications ready for 013 (Priority: P3)

**Goal**: `linked` and `unlinked` notifications render with the right text.

**Independent Test**: spec.md US5.

- [ ] T048 [P] [US5] In `api/tests/integration/test_notification_service.py`: `add(..., "linked")` and
  `add(..., "unlinked", "<code>")` can repeat for one request and list correctly (data-model.md
  `notifications_once`); run red, then green (no code change expected beyond T011 — report if it was
  already green).
- [ ] T049 [P] [US5] Vitest case in `web/src/__tests__/notifications.test.tsx`: «تم ربط المشترك» and «تم
  التراجع عن الربط» with its reason.
- [ ] T050 [US5] Add a comment in `api/app/core/request_status.py` and `notification_service.py` that 013
  calls `check` and `add` for linking and its undo, and defines the undo reason codes.
- [ ] T051 [US5] Run api and web suites green, lint, and commit batch 4.

**Checkpoint**: batch 4 ends. Commit.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Playwright `e2e/tests/link-message-notifications.spec.ts`: marketer submits a pending request →
  admin accepts → badge 1 → open → link message copied; admin rejects then deletes another → notification
  shows «محذوف» without the name; search by number.
- [ ] T053 [P] Extend `api/tests/integration/test_log_safety.py` :
  notification writes and link message reads log no name, phone or numbers.
- [ ] T054 Run `quickstart.md` automated block; fix anything red.
- [ ] T055 `docker compose up` from clean, check the app starts and the migration applies.
- [ ] T056 Write the owner's manual test in Arabic in `specs/012-link-message-notifications/manual-test-ar.md`
  from quickstart.md › Manual scenarios.
- [ ] T057 Fix stale numbering comments that say "linked … 012" meaning «تم الربط» (now 013) in
  `specs/010-admin-request-review/manual-test-ar.md` and `research.md` only where they mislead.
- [ ] T058 Commit batch 5.

**Checkpoint**: batch 5 ends. The feature is ready for review.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → all stories.
- US1 needs only Phase 2's transition check (T007) — it is independent of notifications.
- US2 needs T008–T011. US4 needs US2's notification page (T033) for its web part; its api part needs only
  T011.
- US3 is independent of US2/US4 (only T046 touches shared labels).
- US5 needs T011 and T033.
- Polish needs all.

## Parallel Example: Foundational

```text
T003 test_request_status.py   T004 test_migration_0015.py   T005 test_notification_service.py
then T009 model + T010 schemas in parallel, T006 → T007, T008 → T011
```

## Parallel Example: User Story 2

```text
T023, T024, T025, T026, T027, T028 (all tests, different files)
then T029 → T030 (api) alongside T031 → T032, T033 (web)
```

## Implementation Strategy

- **Batches 1–2** deliver the MVP: the marketer can copy and share the link message of any accepted request.
- **Batch 3** adds notifications on accept, reject and delete, including the deleted-request rules.
- **Batch 4** adds search, the «تم الربط» tab, the §7.2 label, and readies 013's two events.
- **Batch 5** adds e2e, log safety, the clean start and the owner's manual test.

## Notes

- Report red → green for every test task, per the owner's rule.
- Python edit scripts write CRLF on this host: use `newline="\n"` or strip `\r` before Prettier.
- Commit at the end of each batch only.
