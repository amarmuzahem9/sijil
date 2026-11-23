# Implementation Plan: Subscriber Deletion

**Branch**: `011-subscriber-deletion` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/011-subscriber-deletion/spec.md`;
- the owner's answers of 2026-11-24:
  - «سبب آخر» takes no text;
  - the marketer still sees the request, marked «محذوف»;
  - a box «فتح طلب برقمه» is added;
  - the rejection note is erased from the request, and the copy in its audit line stays;
  - deleting needs `review` and `delete`;
  - the feature plan is renumbered;
- `docs/system.md` v1.15 §7.4 (written in this step);
- the constitution v1.3.0, Principle III amended in this step.

## Summary

The owner needs a way to correct a mistake, such as a duplicate or test request, without keeping a
real person's data and without breaking counts or commission. 011 erases a request in place.

| Part | What |
|---|---|
| Erasure | the personal columns are set to `NULL` on the same row. Card images, pins and the request's OTP rows are removed. A check ties the erased columns to the deletion mark (R1, R4, R5) |
| Mark | `deleted_at`, `deleted_by`, `deletion_reason`. The status is kept. Only pending and rejected requests can be deleted. Deletion is final (R2) |
| Safety | the row lock is shared with accept, reject and pin. A deleted request refuses every later action (R3) |
| Confirmation | a fixed reason and the typed number, parsed the same way on the server and the page (R6) |
| Permission | the new `delete`. The main admin always holds it (R7) |
| Reach | «فتح طلب برقمه» opens any request file by its number (R8) |
| Views | the deleted file banner (R9), «سجل محذوف» on linked records (R10), the marketer's «محذوف» tag (R11), the pending count without deleted rows (R13) |
| Audit | one `request.deleted` line with no personal data. Old lines are never altered (R12) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, migration `0014_subscriber_deletion`:
- the deletion mark;
- the personal columns made nullable, with the erasure checks;
- the pending index;
- the permission check.

The image files are in the existing uploads volume. See [data-model.md](./data-model.md).

**Testing**: pytest unit and integration tests, Vitest, Playwright ([R14](./research.md#r14-tests-principle-viii)).
Each new test is run red before its code.

**Target Platform**: the company Linux server. The admin pages are used on desktop and phone.

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- a deletion finishes in under 2 s (SC-007: the whole action takes under 30 s);
- the lookup by number takes under 1 s.

**Constraints**:
- No personal data in the audit or log lines.
- A request is never left half-erased.
- Accepted and linked requests are never erased.
- Old audit lines are never altered.

**Scale/Scope**:
- 1 migration;
- 2 new pure modules (`core/request_number.py`, `core/deletion_reasons.py`);
- 1 new service (`deletion_service`);
- 2 new routes (delete, by-number);
- changed: `review_service` (lock, file, live check), `linked_records`, `admin_home`,
  `match_service`, the marketer request schemas, the audit API, and `access`;
- web: 1 new dialog (DeleteRequestDialog), 1 new box (OpenByNumber), and changes to RequestReview,
  LinkedRecordCard, SubmittedTab, RequestResult, Admins (the permission switch) and auditFormat.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Only pending and rejected requests are deleted, so no accepted decision is undone. The server enforces the status, the permission and the number. A deleted row has no keys, so it leaves every check. The match query also filters `deleted_at IS NULL`. Other requests keep their reasons. Status transitions in §7.2 are unchanged. |
| II. Protection of Identity Documents | ✅ | The deletion erases the identity data and the image files. The deleted file and the marketer view return no personal field. The audit line and the log hold the number, the actor, the reason and the counts only. Backups expire on their own schedule, and the owner accepts this (§15). |
| III. Permanent Audit Trail | ✅ (v1.3.0) | The 1.3.0 exception allows erasure of pending and rejected requests only. The row stays with the mark. The deletion is audited without personal data. Old audit lines are not touched. Pin lines show «سجل محذوف» through `entity_deleted`. |
| IV. Recorded Values Are Immutable | ✅ | Prices, the decision (who, when, reason code), the dates and the number stay. The note is erased by the owner's decision, which v1.3.0 lists. Nothing that is kept changes value. |
| V. Mobile-First and Arabic | ✅ | The dialog, the banner and the tags are in Arabic and RTL. The number field takes Arabic-Indic digits. |
| VI. Simplicity | ✅ | Erasure happens in place on the existing row, with no side table. There is one parse function shared by the confirmation and the lookup. The reasons are a fixed list. The rules went into `docs/system.md` v1.15 first. |
| VII. Fixed Technology Stack | ✅ | No new technology. |
| VIII. Tested Business Rules | ✅ | Unit tests for the parsing and the reasons. Integration tests cover every refusal, concurrency, the freed keys, privacy, the audit and logs, the counts and the migration. Playwright covers the main flow, with synthetic data only. |
| IX. Server-Side Authorization | ✅ | The delete route checks `review` and `delete` on the server. The by-number route checks `review`. Accept, reject and pin refuse a deleted request. |
| X. Time Handling | ✅ | `deleted_at` comes from `utc_now()`. The counts keep the Baghdad bounds. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/011-subscriber-deletion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── migrations/versions/0014_subscriber_deletion.py  # mark, nullable personal cols, checks, index, permission
├── app/
│   ├── errors.py                     # request_deleted, request_not_deletable, number_mismatch (+ Arabic)
│   ├── core/access.py                # "delete" in ADMIN_PERMISSIONS
│   ├── core/request_number.py        # new: parse typed number (R6)
│   ├── core/deletion_reasons.py      # new: codes and Arabic labels
│   ├── models/request.py, models/user.py   # new columns, nullable columns, checks
│   ├── schemas/admin_requests.py     # DeleteIn, deleted block, can_delete, by-number out, LinkedRecord.deleted
│   ├── schemas/requests.py           # nullable fields, result "deleted", deletion fields
│   ├── services/deletion_service.py  # new: delete (R1–R5, R12)
│   ├── services/review_service.py    # lock refuses deleted; file and live check for deleted; by-number
│   ├── services/linked_records.py    # deleted resolver output (R10)
│   ├── services/match_service.py     # deleted_at IS NULL
│   ├── services/admin_home.py        # pending excludes deleted
│   ├── services/submit_service.py    # marketer to_out for deleted (R11)
│   ├── services/audit_service.py, api/audit.py   # entity_deleted
│   └── api/admin_requests.py         # POST …/delete, GET …/by-number/{text}
└── tests/
    ├── fixtures/request_number_cases.json
    ├── unit/{test_request_number,test_deletion_reasons}.py
    └── integration/{test_deletion,test_deletion_concurrency,test_deletion_frees_keys,test_by_number,
                     test_migration_0014}.py
        + extended: test_marketer_privacy, test_log_safety, test_audit_completeness, test_admin_home,
                    test_permissions (page/permission fixtures)

web/src/
├── auth/access.ts, lib/labels.ts            # "delete" permission and label
├── lib/requestNumber.ts                     # new: mirror of R6
├── lib/adminRequests.ts, lib/requests.ts    # delete, by-number, deleted fields
├── lib/auditFormat.ts                       # «حذف مشترك», «سجل محذوف» for pin lines
├── pages/admin/pending/PendingList.tsx      # OpenByNumber box on top
├── pages/admin/pending/OpenByNumber.tsx     # new
├── pages/admin/pending/DeleteRequestDialog.tsx  # new
├── pages/admin/pending/RequestReview.tsx    # «حذف» button, deleted banner, panels hidden
├── pages/admin/pending/LinkedRecordCard.tsx # «سجل محذوف (#…)»
├── pages/admin/Admins.tsx                   # the delete switch
├── pages/marketer/SubmittedTab.tsx, RequestResult.tsx   # «محذوف» tag and view
└── __tests__/{deleteRequestDialog,openByNumber,deletedRequest,marketerDeleted,requestNumber}.test.tsx

e2e/tests/subscriber-deletion.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout and the 008/010 split:
- the pure rules (number parsing, reason list) go in `core/`;
- the locked, database-facing erasure goes in `services/deletion_service.py`;
- the existing review page carries the delete dialog, and no new admin page is added.

## Complexity Tracking

No violations.
