---

description: "Task list for feature 013: «تم الربط» and the Monthly Counter"
---

# Tasks: «تم الربط» and the Monthly Counter

**Input**: Design documents from `specs/013-linking-counter/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run
red before its code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: the fake card reader, made-up numbers, names and phones. No real card images or
  subscribers (CLAUDE.md).
- Requests come from `api/tests/helpers/requests.py::request_factory` (with `mark_deleted` for a deleted one);
  admins from `api/tests/helpers/review.py::admin_with`; time from the clock fixture of `api/tests/conftest.py`.
- Vitest runs from PowerShell (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T011 |
| 2 | 3 (US1 linking) | T012–T024 |
| 3 | 4 (US2 counter and marketer views) | T025–T034 |
| 4 | 5–6 (US3 undo, US4 admin home) | T035–T046 |
| 5 | 7 (Polish, e2e, manual test) | T047–T053 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, then `docker compose exec api pytest` and
  `cd web && npm test` are green on the branch before any change; note the counts in the batch report.
- [x] T002 [P] Add error codes `already_linked` (409, «تم ربط هذا الطلب مسبقاً») and `already_unlinked` (409,
  «تم التراجع عن هذا الربط مسبقاً») with their Arabic messages in `api/app/errors.py` (research R2).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the link columns, the history table, the undo reasons and the search that every story uses.

### Tests (write first, run red)

- [x] T003 [P] Migration test in `api/tests/integration/test_migration_0016.py`: after upgrade the columns
  data-model.md `requests.linked_at`, `requests.linked_by` exist; check `requests_linked_has_time` refuses
  `linked` without `linked_at`/`linked_by` and `approved` with them; `requests_linked_approved` refuses `linked`
  without `approved_at`; table `request_links` exists with data-model.md `request_links.kind` (only
  `linked`/`unlinked`) and `request_links.reason` (null for `linked`, one of the four codes for `unlinked`),
  `request_links.request_id` and `request_links.actor_id` required; the replaced `notifications_reason_kind`
  refuses an `unlinked` notification without a reason (data-model.md › Changed table `notifications`);
  downgrade to 0015 removes all of it.
- [x] T004 [P] Unit test `api/tests/unit/test_unlink_reasons.py`: the four codes and their exact Arabic labels
  (research R4), `validate` refuses an unknown or empty code with `validation_error`.
- [x] T005 [P] Unit test `api/tests/unit/test_link_search.py` driven by a new fixture
  `api/tests/fixtures/link_search_cases.json`: «1004», «T3C-1004», «#t3c-١٠٠٤» → number; `0780 123 4567`,
  `+964 780 123 4567`, Arabic digits → phone `07801234567`; `alm03-07801234567` → username
  `ALM03-07801234567`; a name, `%`, `_`, Latin text → no term (research R7).

### Implementation

- [x] T006 Write migration `api/migrations/versions/0016_request_links.py` (revises `0015`): data-model.md
  `requests.linked_at`, `requests.linked_by`, checks `requests_linked_has_time`, `requests_linked_approved`,
  indexes `requests_awaiting_link`, `requests_linked_at`, `requests_linked_recent`; table `request_links` with
  data-model.md `request_links.id`, `request_links.request_id`, `request_links.kind`, `request_links.actor_id`,
  `request_links.at`, `request_links.reason` and index `request_links_request`; the replaced
  `notifications_reason_kind`; T003 green.
- [x] T007 [P] Mirror the migration in the models: `linked_at`, `linked_by` and the checks in
  `api/app/models/request.py`; new `api/app/models/request_link.py` (`RequestLink`) registered in
  `api/app/models/__init__.py`; the check in `api/app/models/notification.py`.
- [x] T008 [P] Create `api/app/core/unlink_reasons.py` (`LABELS`, `validate`) like `deletion_reasons.py`;
  T004 green. Add `"unlinked": unlink_reasons.LABELS` to `_REASON_LABELS` in
  `api/app/services/notification_service.py`.
- [x] T009 [P] Create `api/app/core/link_search.py` (`LinkSearchTerm`, `classify`) reusing
  `request_number.parse` and `normalize_phone`; T005 green.
- [x] T010 Update `request_factory` in `api/tests/helpers/requests.py` so `status="linked"` sets `linked_at`
  (default now, overridable), `linked_by` (overridable, default a dedicated synthetic admin made by the
  factory) and writes the matching `request_links` row `linked` (so the current `link_id` exists), and add
  helper `link_request(db, request, admin, at=None)` that links an approved request the same way; the whole
  existing suite stays green with the new checks.
- [x] T011 [P] Mirror the undo reasons in `web/src/lib/labels.ts` (`UNLINK_REASON_LABELS`, same codes and
  labels) and add audit labels `'request.linked': 'تم الربط'`, `'request.unlinked': 'تراجع عن الربط'`
  (research R10).

**Checkpoint**: batch 1 commit.

---

## Phase 3: User Story 1 — The admin confirms «تم الربط» (Priority: P1) 🎯 MVP

**Goal**: «بانتظار الربط» lists accepted requests and «تم الربط» links one, with audit and notification.

**Independent Test**: spec US1 — link a synthetic accepted request as a `link`-only admin; it leaves the
list, the marketer gets «تم ربط المشترك».

### Tests (write first, run red)

- [ ] T012 [P] [US1] Integration test `api/tests/integration/test_link.py`: success sets status, data-model.md
  `requests.linked_at` from `utc_now()` and `requests.linked_by`, adds one `request_links` row `linked`, one
  audit `request.linked` (before/after status, entity = number), one `linked` notification; refusals write
  nothing: pending (`invalid_transition`), rejected (`invalid_transition`), deleted (`request_deleted`), already
  linked (`already_linked`), unknown id (404), admin without `link` and marketer (403); `approved_at`,
  `approved_by`, `counts_commission` unchanged.
- [ ] T013 [P] [US1] Concurrency test `api/tests/integration/test_link_concurrency.py`: two sessions link the
  same request; one 200, one `already_linked`; one history row, one audit, one notification (pattern of
  `test_admin_decide_concurrency`).
- [ ] T014 [P] [US1] Integration test `api/tests/integration/test_link_lists.py` for `GET
  /api/admin/links/awaiting`: only approved, not deleted, oldest `approved_at` first; row keys exactly the
  `LinkRow` fields of contracts/api.md (assert no `national_id`, `family_number`, card or image key and that
  the JSON text holds neither number); search by number, phone, username; `q` of 1 character → 422; offset and
  limit; `total`; 403 without `link`.
- [ ] T015 [P] [US1] Vitest `web/src/__tests__/awaitingLink.test.tsx`: the waiting tab lists rows with number,
  name, username, phone, «اسم البرج (رمز البرج)», plan, marketer, date; search sends `q`; «تم الربط» opens the
  confirmation and posts; on `already_linked` shows the server message and refreshes.

### Implementation

- [ ] T016 [US1] Create `api/app/schemas/admin_links.py`: `LinkRow`, `LinkList` (items, total), `UnlinkIn`
  (reason, link_id; strict) per contracts/api.md.
- [ ] T017 [US1] Create `api/app/services/link_service.py`: `_lock(db, request_id)` (`FOR UPDATE OF
  requests`, `populate_existing`, order of refusals per research R2), `awaiting(db, q, offset, limit)`,
  `link(db, user, request_id)` per research R3, `to_row`; T012, T013 green.
- [ ] T018 [US1] Create router `api/app/api/admin_links.py` (`require_permission("link")`): `GET
  /admin/links/awaiting`, `POST /admin/requests/{id}/link`; include it in `api/app/main.py`; T014 green for
  the awaiting part.
- [ ] T019 [P] [US1] Create `web/src/lib/links.ts`: types `LinkRow`, `LinkList`; `listAwaiting(q, offset)`,
  `linkRequest(id)` (and `listRecent`, `unlinkRequest` signatures for US3).
- [ ] T020 [P] [US1] Create `web/src/pages/admin/links/LinkConfirmDialog.tsx`: «تأكيد الربط؟» with the number,
  name and username; «تم الربط» / «إلغاء».
- [ ] T021 [US1] Create `web/src/pages/admin/links/AwaitingLink.tsx`: tabs «بانتظار الربط» / «المربوطة مؤخراً»
  (second tab filled in US3), search box (≥ 2 characters), cards per row, «تحميل المزيد», mutation that
  invalidates both lists; T015 green.
- [ ] T022 [US1] Replace `AdminAwaitingLink` placeholder: remove it from `web/src/pages/admin/placeholders.tsx`
  and route `/admin/awaiting-link` to `AwaitingLink` in `web/src/router.tsx`.
- [ ] T023 [P] [US1] Extend `api/tests/integration/test_deletion.py`: deleting a linked request answers
  `request_not_deletable` and changes nothing (FR-020).
- [ ] T024 [US1] Run the api and web suites; all green.

**Checkpoint**: batch 2 commit.

---

## Phase 4: User Story 2 — The marketer sees the counter and the linked subscribers (Priority: P1)

**Goal**: the real counter with «و M بلا عمولة», the latest 10 links, the «تم الربط» tab by link time and the
link date on the request.

**Independent Test**: spec US2.

### Tests (write first, run red)

- [ ] T025 [P] [US2] Integration test `api/tests/integration/test_linked_counter.py` for `GET
  /api/marketer/dashboard` (data-model.md › Counting rule): commission links count in `linked_this_month`, a
  return with `counts_commission=false` counts in `linked_without_commission`; Baghdad boundaries with the
  clock fixture (a link at 23:59 Baghdad on the last day counts in that month, 00:00 in the next); last month's
  links do not count; another marketer's links do not count; an archived marketer's links still count
  (spec Edge Cases); a deleted row never counts (FR-020); `recent_links` up to 10, newest first, this month
  only, caller's only.
- [ ] T026 [P] [US2] Integration test `api/tests/integration/test_linked_tab.py`: `GET
  /api/requests?status=linked` ordered by `linked_at` desc; `linked_at` present on list items and `GET
  /api/requests/{id}`, null when not linked; no `linked_by` key in either.
- [ ] T027 [P] [US2] Extend `web/src/__tests__/dashboard.test.tsx`: «تم الربط هذا الشهر: N»; «و M بلا عمولة»
  only when M > 0; the latest links list with green chips linking to the request; empty state.
- [ ] T028 [P] [US2] Vitest `web/src/__tests__/linkedTab.test.tsx`: the «تم الربط» tab shows each row's link
  date; the request page shows «تاريخ الربط» for a linked request and the link message stays.

### Implementation

- [ ] T029 [US2] Add `marketer_counts(db, user)` to `api/app/services/link_service.py` and return
  `linked_this_month`, `linked_without_commission`, `month_label`, `recent_links` from `dashboard` in
  `api/app/api/marketer.py` (contracts/api.md › dashboard); T025 green.
- [ ] T030 [US2] Add `linked_at` to `RequestOut` and `RequestListItem` in `api/app/schemas/requests.py`, fill
  it in `to_out` and `list_own` (null on a deleted row), and order by `linked_at DESC, id DESC` when statuses
  are exactly `['linked']` in `api/app/services/submit_service.py`; T026 green.
- [ ] T031 [P] [US2] Add `linked_at` to the request types in `web/src/lib/requests.ts`.
- [ ] T032 [US2] Update `web/src/pages/marketer/Dashboard.tsx`: the counter, «و M بلا عمولة», the latest links
  list; T027 green.
- [ ] T033 [US2] Show the link date in `web/src/pages/marketer/SubmittedTab.tsx` (linked rows) and «تاريخ
  الربط» in `web/src/pages/marketer/RequestResult.tsx`; T028 green.
- [ ] T034 [US2] Extend `api/tests/integration/test_marketer_privacy.py`: a marketer's dashboard and lists never
  include another marketer's links. Run both suites; all green.

**Checkpoint**: batch 3 commit.

---

## Phase 5: User Story 3 — The admin undoes «تم الربط» with a reason (Priority: P2)

**Goal**: the recent links list and «التراجع عن الربط» with a fixed reason.

**Independent Test**: spec US3.

### Tests (write first, run red)

- [ ] T035 [P] [US3] Integration test `api/tests/integration/test_unlink.py`: success restores `approved`,
  clears data-model.md `requests.linked_at`, `requests.linked_by`, adds a `request_links` row `unlinked` with
  the reason (data-model.md `request_links.reason`), one audit `request.unlinked` with the reason, one
  `unlinked` notification whose `reason_label` is the fixed label; `approved_at`, `approved_by`,
  `counts_commission` unchanged; refusals write nothing: missing/unknown reason or `link_id` (422), stale
  `link_id` and second undo (`already_unlinked`), pending/rejected (`invalid_transition`), deleted
  (`request_deleted`), 403 without `link`.
- [ ] T036 [P] [US3] Concurrency test in `api/tests/integration/test_link_concurrency.py`: two undos of the same
  link; one succeeds, one `already_unlinked`; one history row, audit and notification.
- [ ] T037 [P] [US3] Extend `api/tests/integration/test_linked_counter.py`: undo removes a link from its month
  (also a previous month's); link → undo → link in a new month counts once, in the new month; full history
  kept (three `request_links` rows).
- [ ] T038 [P] [US3] Extend `api/tests/integration/test_link_lists.py` for `GET /api/admin/links/recent`:
  linked only, not deleted, newest link first across months, `linked_at`, `linked_by_name`, `link_id` = the
  current link; same search and no identity fields.
- [ ] T039 [P] [US3] Extend `api/tests/integration/test_deletion.py`: an undone (approved again) request is
  not deletable.
- [ ] T040 [P] [US3] Vitest `web/src/__tests__/unlinkDialog.test.tsx`: the reason is required, the four labels
  shown, no text field; posts `reason` and `link_id`; on `already_unlinked` shows the message and refreshes.

### Implementation

- [ ] T041 [US3] Add `recent(db, q, offset, limit)` and `unlink(db, user, request_id, body)` to
  `api/app/services/link_service.py` (research R2, R3); `GET /admin/links/recent` and `POST
  /admin/requests/{id}/unlink` in `api/app/api/admin_links.py`; T035–T039 green.
- [ ] T042 [US3] Create `web/src/pages/admin/links/UnlinkDialog.tsx` and fill the «المربوطة مؤخراً» tab of
  `web/src/pages/admin/links/AwaitingLink.tsx` (rows with link date and who linked, «التراجع عن الربط»);
  T040 green.
- [ ] T043 [P] [US3] Show the undo reason label from `after.reason` in `web/src/lib/auditFormat.ts`, with a
  case in `web/src/__tests__/audit-format.test.ts` (red first).

---

## Phase 6: User Story 4 — The admin home counts links (Priority: P3)

**Goal**: real «تم الربط» numbers on the admin home.

**Independent Test**: spec US4.

- [ ] T044 [US4] Extend `api/tests/integration/test_admin_home.py` (red first): linked today and month by
  `linked_at` in Baghdad bounds; an undone link not counted; counts only.
- [ ] T045 [US4] Replace the fixed `linked=0` in `api/app/services/admin_home.py` with the count of research
  R6; T044 green.
- [ ] T046 Run the api and web suites; all green.

**Checkpoint**: batch 4 commit.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T047 [P] Extend `api/tests/integration/test_notifications.py`: the marketer's list shows `linked` and
  `unlinked` rows with their titles and the undo reason label, after a real link and undo.
- [ ] T048 [P] Log safety: assert that link and unlink log lines carry only the action and the request number
  (no name, phone or username), in `api/tests/integration/test_link.py`.
- [ ] T049 [P] Playwright `e2e/tests/linking-counter.spec.ts`: accept → admin links → marketer badge and counter
  1 → admin undoes with «ضُغط بالخطأ» → counter 0 and notification with the reason → relink → counter 1.
- [ ] T050 Remove the "until 013" comments in `api/app/api/marketer.py`, `api/app/services/admin_home.py`,
  `api/app/core/request_status.py`, `api/app/services/notification_service.py`, `web/src/lib/requestStatus.ts`,
  `web/src/pages/marketer/Requests.tsx`.
- [ ] T051 Write `specs/013-linking-counter/manual-test-ar.md` (Arabic manual test steps from quickstart.md).
- [ ] T052 Run the full suites (api, web, e2e) and `docker compose up`; walk quickstart.md scenarios 1–14.
- [ ] T053 Final commit; report red/green per test task.

**Checkpoint**: batch 5 commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → stories. Phase 2 blocks every story (columns, history table, factory, reasons, search).
- US1 (Phase 3) before US2: the counter tests can use the factory alone, but the e2e path and the marketer views
  need real links. US3 needs US1's service, router and page. US4 needs only Phase 2 (can run after Phase 2 in
  parallel with US1–US3, kept in batch 4 for simple commits).
- Within a phase: tests first (red), then implementation (green).

## Parallel Examples

- Phase 2 tests: T003, T004, T005 together; then T007, T008, T009, T011 together after T006.
- US1: T012, T013, T014, T015 together; T019, T020 alongside T016–T018.
- US2: T025–T028 together; T031 alongside T029–T030.
- US3: T035–T040 together.

## Implementation Strategy

- **MVP**: Phases 1–3 (US1): admins can link, marketers are notified; the counter still shows 0 until US2.
- Then US2 (the counter the marketer sees), US3 (undo), US4 (admin home), Polish.
- Each batch ends with green suites and a commit.
