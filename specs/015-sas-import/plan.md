# Implementation Plan: Import of the SAS Subscribers

**Branch**: `015-sas-import` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-sas-import/spec.md` (clarified; `docs/system.md` 1.20 §12.2)

## Summary

A `reports` admin uploads the SAS subscribers export (`.xlsx` or `.csv`). The server reads it in memory and keeps
only the documented columns it needs: `ct_password` is never projected out of the row. It cleans the values (phone
§8.1 for the phone column and for the phone at the end of the username; tower code from the username prefix, or a
saved mapping), compares each row with the stored SAS subscribers by upper-case username, and saves a preview. No
images, so the preview is built in the upload request (no background job). The admin maps unknown prefixes to
towers, chooses «استيراد» / «تخطي» for flagged rows (or «تخطي للكل» per group), then confirms. One transaction adds
new rows, updates changed ones (each change kept in an append-only change row), marks stored rows missing from the
file «غير موجود في آخر ملف», saves the prefix mappings, and writes one audit line with counts only.

SAS subscribers join the check engine as the `sas` source (phone only, through either phone, never national ID or
family, never pending, missing rows still count), so 008–010 give case 1 with no change to their code. They join the
linked-record registry, so the review file shows «مشترك SAS» with the expiry «حسب آخر استيراد». A return to a SAS
subscriber keeps the SAS username when there is no Sijil username. Requests, links and counters are never touched.
SAS subscribers live in their own table.

## Technical Context

**Language/Version**: Python 3.12 (api), TypeScript 6 + React 18 (web)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, Pydantic, openpyxl + defusedxml (all from 014). Web: MUI.
**No new package.**

**Storage**: PostgreSQL 16 — new tables `sas_imports`, `sas_subscribers`, `sas_subscriber_changes`,
`sas_tower_mappings`, `sas_import_previews` (migration 0018). No files on disk (the upload is never written).

**Testing**: pytest (unit + integration on the test database), Vitest, Playwright (e2e stack, synthetic SAS file).

**Target Platform**: Linux server, Docker Compose; admin pages in mobile and desktop browsers.

**Project Type**: web application (`api/` + `web/`, plus `e2e/`).

**Performance Goals**: a 20 000-row file previewed in under 30 s and confirmed in under 30 s on the staging server
(4 CPU). The admin finishes a re-import of 10 000 rows in under 10 minutes (SC-004). The draft check gains two
indexed lookups.

**Constraints**: `ct_password` never kept anywhere (FR-003, SC-003); nothing saved before confirmation; all or
nothing (SC-007); no change to any request (FR-016); no usernames, phones or names in logs or audit (FR-009);
preview lives 1 h; file ≤ 15 MB and ≤ 50 000 rows.

**Scale/Scope**: thousands of SAS rows (assumed ≤ 20 000), re-imported whenever the admin wants (weekly or more);
1–3 admins.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Anti-Fraud First | SAS subscribers become a check source for the early check, the submit check and the 010 re-check, all regions and towers. Both phones count. Rows missing from a newer file still count. §8.1 normalization (R5, R8) | Pass |
| II. Identity Documents | `ct_password` is dropped at the header mapping, before any row is built. A test searches the database, preview, audit and captured logs for synthetic password values (R3). Logs and audit carry ids and counts only (R11) | Pass |
| III. Audit Trail | One `sas.imported` audit line per import. Every field change on a stored SAS subscriber is kept in an append-only `sas_subscriber_changes` row (before/after), so the change is recoverable from the audit line through one link without phones in the audit (R10). No delete route | Pass |
| IV. Immutable values | A request keeps the username and tower it was submitted with; later SAS updates never touch requests (FR-016). SAS rows change only by re-import, as §12.2 says, with the history kept | Pass |
| V. Mobile-first, Arabic | Import tab, mapping table and labels in Arabic, RTL, usable at phone width | Pass |
| VI. Simplicity | Same preview/choice/confirm model as 014. No background job (no images). No «بانتظار الربط» hint (FR-023). Notes and parent_name stored, not shown | Pass |
| VII. Fixed stack | Same stack, no new package, no external service | Pass |
| VIII. Tested rules | pytest for parsing, ct_password, username/tower rules, both phones, flags, re-import diff, missing mark, all-or-nothing, permissions, source and resolver; Playwright for import → marketer check → review file | Pass |
| IX. Server-side authorization | Import routes require `reports` (or main admin). The linked record goes to review admins only | Pass |
| X. Time | SAS dates read as Baghdad time and stored in UTC. Preview expiry and the missing mark are UTC | Pass |

Project rules (CLAUDE.md): synthetic fixtures only (made-up usernames, phones, passwords); no secrets added; the real
file is imported only on the server. **Gate: pass.**

**Post-design re-check (after Phase 1)**: the data model and contracts keep every check above. `sas_subscriber_changes`
holds phones and names; it is readable only through the database, like `number_pins` in 010. **Pass.**

## Project Structure

### Documentation (this feature)

```text
specs/015-sas-import/
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
├── app/
│   ├── models/sas.py                        # SasImport, SasSubscriber, SasSubscriberChange, SasTowerMapping, SasImportPreview
│   ├── core/sas_row.py                      # pure: headers (drop ct_password), username split, tower rule, dates, diff, flags
│   ├── services/
│   │   ├── legacy_file.py                   # read_table gains max_bytes / max_rows (shared reader)
│   │   ├── sas_import_service.py            # preview, mappings, choices, confirm, expiry sweep
│   │   ├── sas_source.py                    # registers `sas` in match_service, linked_records, tower usage
│   │   ├── submit_service.py                # _username: SAS username when no Sijil one (FR-013)
│   │   └── legacy_import_service.py         # shares the confirm advisory lock
│   ├── schemas/sas_import.py
│   ├── schemas/admin_requests.py            # LinkedRecordOut + expiry_as_of, last_online, group_name, username_phone, missing_from_file
│   ├── api/admin_imports.py                 # + /admin/imports/sas/*
│   └── main.py                              # register sas_source, startup sweep
├── migrations/versions/0018_sas_import.py
└── tests/
    ├── fixtures/sas/                        # synthetic csv/xlsx (+ second file for re-import)
    ├── unit/test_sas_row.py
    └── integration/test_sas_preview.py, test_sas_confirm.py, test_sas_reimport.py, test_sas_source.py,
        test_sas_linked_record.py, test_sas_password_never_kept.py, test_sas_isolation.py, test_migration_0018.py

web/src/
├── lib/sasImport.ts                         # API calls, flag and count labels
├── lib/labels.ts                            # SOURCE_LABELS.sas «مشترك SAS», audit action «استيراد مشتركي SAS»
├── pages/admin/import/ImportPage.tsx        # SAS tab instead of «قريباً»
├── pages/admin/import/SasImport.tsx         # upload → preview (counts, mapping table, groups) → confirm → summary
├── pages/admin/pending/LinkedRecordCard.tsx # SAS fields
└── __tests__/sasImport.test.tsx, linkedRecordCard.test.tsx

e2e/tests/sas-import.spec.ts
```

**Structure Decision**: The existing `api/` + `web/` + `e2e/` layout and the 014 split: pure rules in `core/`,
database work in `services/`, routes in `api/`. The `sas` source, resolver and tower usage check live in one module
registered at startup, like `legacy_source`.

## Complexity Tracking

No constitution violation. The one structure beyond 014 is `sas_subscriber_changes`, the minimum that keeps
Principle III («subscriber data edit» with before/after) without putting phones in the audit line (research R10).
