# Implementation Plan: Existing Subscriber Paths

**Branch**: `009-existing-subscriber-paths` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/009-existing-subscriber-paths/spec.md`;
- the owner's answers of 2026-11-23:
  - Q1: WhatsApp to the administration number from the settings;
  - Q2: a national ID match with a different family number goes to review as «تعارض بالأرقام»;
  - Q3: the dashboard button opens the same form;
- `docs/system.md` v1.10 §3.1, §6.1, §6.3, §10;
- the constitution.

## Summary

008 refuses a used phone or a known national ID. 009 turns those dead ends into paths.

**Matching (R1)**: the check engine reports one entry per **matched record**, saying which of the
phone, national ID and family number match it and whether it is still pending. From that:

| Match | Path |
|---|---|
| national ID + family on the same record | «طلب العودة للخدمة» |
| national ID only | «تعارض بالأرقام», sent to review |
| family only | the 008 second subscription, relabeled «إضافة اشتراك ثاني» |
| phone | «طلب العودة للخدمة» or «الاتصال بالإدارة» |

**Return choice**:
- Stored on the draft as a key, like 008's family confirmation, so it drops when the numbers change.
- It lets the OTP be sent to a phone held only by the returning person's records.
- Submission creates type `return`, pending review, reason `return` linked to those records.
- A pending request for the same person blocks a return.

**«الاتصال بالإدارة»**: opens WhatsApp to the number set in «الإعدادات ← عام», with a text that
carries only the marketer's name. The click is audited.

**Privacy**: the marketer still gets booleans only (FR-012).

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, migration `0011_existing_subscriber_paths`:
- `drafts.return_key`;
- the `request_reasons` check gains `numbers_conflict`;
- the `app_settings` key `admin_whatsapp`.

See [data-model.md](./data-model.md).

**Testing**: pytest unit and integration tests, Vitest, Playwright (research R12). Each new test is
run red before its code.

**Target Platform**: the company Linux server; phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- early checks still within 3 s of a save, using one indexed query per draft instead of three;
- submit under 5 s (SC-001 of 008).

**Constraints**:
- No matched-record data in any marketer response, audit `after` or log line.
- One winner when two returns for the same person are submitted at once (008 locks).

**Scale/Scope**:
- 1 migration, 1 new route, 3 changed routes, 1 new setting.
- 2 new web components (ReturnNotice, ContactAdminButton) and 6 changed (CardDataSection,
  PhoneSection, FamilyMatchNotice, RequestResult, Dashboard, GeneralTab).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | The server decides at submission, under the 008 locks, against every source. The return is valid only if its target still exists under the locks. The phone exception is limited to the target's own records. Every reason is stored, with links. A pending duplicate blocks a return. |
| II. Protection of Identity Documents | ✅ | The marketer gets booleans and a basis only. The WhatsApp text has no subscriber data. Matched ids live only in `request_reasons` (admin side). Audit and logs hold no card data or phone (R11). |
| III. Permanent Audit Trail | ✅ | These are audited: choose and withdraw a return, contact-admin opened, the settings change, and submissions with their new reasons. Nothing is deleted. |
| IV. Recorded Values Are Immutable | ✅ | A return request copies its values at submission, as in 008. The username rule is fixed at submission. |
| V. Mobile-First and Arabic | ✅ | Arabic labels (R10). The WhatsApp button is a real link that works on phone browsers. |
| VI. Simplicity | ✅ | One pure decision function, extended. The choice reuses the 008 "stored key" pattern. No search and no new service. The rule changes went into `docs/system.md` v1.10 first. |
| VII. Fixed Technology Stack | ✅ | No new technology. |
| VIII. Tested Business Rules | ✅ | Every row and combination has unit tests. There are integration tests for each path, concurrency and privacy, and Playwright for both return paths. |
| IX. Server-Side Authorization | ✅ | Owner-only draft routes (404 otherwise). The setting needs `settings`. |
| X. Time Handling | ✅ | `utc_now()` and no new date rules. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/009-existing-subscriber-paths/
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
├── migrations/versions/0011_existing_subscriber_paths.py  # drafts.return_key, reasons check
├── app/
│   ├── errors.py                          # no_return_match, return_pending (+ Arabic messages)
│   ├── core/matches.py                    # MatchRecord + views (R1), return target (R2)
│   ├── core/decision.py                   # v1.10 table (R4)
│   ├── models/draft.py                    # return_key
│   ├── models/request.py                  # REASONS + numbers_conflict
│   ├── schemas/drafts.py                  # DraftChecksOut fields, PATCH return_chosen
│   ├── schemas/requests.py                # result pending_approval
│   ├── services/match_service.py          # one query per draft, record flags
│   ├── services/draft_service.py          # checks, missing items, apply_return_choice, exclusivity
│   ├── services/phone_checks.py           # return-target exception (R6)
│   ├── services/submit_service.py         # return / conflict reasons, username (R7)
│   ├── services/settings_service.py       # admin_whatsapp in general settings
│   ├── api/drafts.py                      # POST /drafts/{id}/contact-admin
│   ├── api/settings.py                    # general: admin_whatsapp
│   └── api/client_config.py               # admin_whatsapp
└── tests/
    ├── unit/test_matches.py               # new
    ├── unit/test_decision.py              # extended
    ├── integration/test_return_path.py    # new
    ├── integration/test_numbers_conflict.py   # new
    ├── integration/test_admin_whatsapp.py # new
    ├── integration/test_marketer_privacy.py   # new (SC-003)
    └── integration/{test_submit,test_submit_concurrency,test_otp,test_log_safety,test_audit_completeness}.py  # extended

web/src/
├── lib/drafts.ts, lib/draftFormController.ts   # new checks fields, return_chosen
├── lib/requests.ts, lib/labels.ts              # pending_approval, reasons, type, audit labels
├── lib/contactAdmin.ts                          # new: wa.me link builder
├── pages/marketer/subscriber/ReturnNotice.tsx   # new
├── pages/marketer/subscriber/ContactAdminButton.tsx  # new
├── pages/marketer/subscriber/FamilyMatchNotice.tsx   # «إضافة اشتراك ثاني»
├── pages/marketer/subscriber/CardDataSection.tsx     # identity return / conflict notice
├── pages/marketer/subscriber/PhoneSection.tsx        # phone return + contact admin
├── pages/marketer/RequestResult.tsx             # pending_approval text
├── pages/marketer/Dashboard.tsx                 # button enabled
├── pages/admin/settings/GeneralTab.tsx          # «رقم واتساب الإدارة»
└── __tests__/{returnNotice,contactAdmin,familyMatchNotice,dashboard}.test.tsx

e2e/tests/existing-subscriber.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout and the 008 split:
- pure rules (matches views, decision) go in `core/`;
- the database-facing parts (sources, submit transaction) go in `services/`.

The source contract changes once (it now returns records). 013 and 014 implement that contract.

## Complexity Tracking

No violations.
