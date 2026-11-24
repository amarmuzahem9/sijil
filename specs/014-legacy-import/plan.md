# Implementation Plan: Import of the Legacy Subscribers (Google Form file)

**Branch**: `014-legacy-import` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/014-legacy-import/spec.md` (clarified; `docs/system.md` 1.19 §12.1)

## Summary

A `reports` admin uploads the old Google Form export (`.xlsx` or `.csv`). The server parses it in memory, cleans the
values with the existing normalizers (phone §8.1, family key §6.2), fetches every Google Drive card image in a
background job into staged files, and shows a preview of flagged rows. The admin picks «استيراد» / «تخطي» (or
corrects an odd family number) for each, then confirms; one transaction writes `legacy_imports`,
`legacy_subscribers` and `legacy_images`, plus one audit line without personal data. A re-upload adds only new legacy
numbers. Rows with «الحالة» «ملغي» or «مرفوض» are imported but never count in the check.

The legacy subscribers join the check engine as the `legacy` source (phone and family key only, never national ID,
never pending), so 008–010 give case 1 / case 3 with no change to their code, and join the linked-record registry
so the review file shows them as «مشترك قديم» with their images through a logged route. They stay out of every
request list, counter and commission because they are a separate table.

## Technical Context

**Language/Version**: Python 3.12 (api), TypeScript 6 + React 18 (web)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, Pydantic, Pillow, httpx (existing); **new**: `openpyxl`
(read `.xlsx`) and `defusedxml` (safe XML for openpyxl) — research R4. Web: MUI (existing), no new package.

**Storage**: PostgreSQL 16 — new tables `legacy_imports`, `legacy_subscribers`, `legacy_images`,
`legacy_import_previews`; new column `image_access_log.legacy_subscriber_id` (migration 0017). Images in the
existing private `uploads` volume through `image_store`.

**Testing**: pytest (unit + integration on the test database), Vitest, Playwright (e2e stack with fake card reader,
fake OTP, fake Drive fetcher).

**Target Platform**: Linux server, Docker Compose; admin pages in mobile and desktop browsers.

**Project Type**: web application (`api/` + `web/`, plus `e2e/`).

**Performance Goals**: 109-row file previewed (with ~218 images fetched, 4 in parallel) in a few minutes; whole
import under 15 minutes including review (SC-003). Adding the `legacy` source keeps the draft check on two indexed
lookups.

**Constraints**: nothing saved before confirmation; all or nothing (SC-006); no OCR on legacy images; no personal
data in logs or audit; preview lives 1 h; file ≤ 5 MB / 2 000 rows; image ≤ 15 MB downloaded, stored ≤ 1 600 px.

**Scale/Scope**: ~109 legacy rows once (plus later re-uploads that add new numbers); 1–3 admins.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Anti-Fraud First | Legacy subscribers become a check source for the early and the authoritative check, all regions and towers, with the canonical phone and family key normalizations (R2, R5). The decision table is unchanged | Pass |
| II. Identity Documents | Images in the private volume, served only to review admins through a permission-checked route, every open logged (R13). Uploaded file never written to disk. Audit, logs and summary carry no family numbers or phones (R11). Re-encoding strips image metadata | Pass |
| III. Audit Trail | One `legacy_import` audit line per import; corrected family numbers recoverable by reference via the never-changed legacy rows (R11). Legacy subscribers never deleted; no delete route | Pass |
| IV. Immutable values | Legacy rows are insert-only; a re-upload never updates them (FR-020); file values kept next to corrections | Pass |
| V. Mobile-first, Arabic | Import page and labels in Arabic, RTL, works on phone width; code in English | Pass |
| VI. Simplicity | Only what §12.1 v1.19 asks; no edit, no subscriber list (018); e-mails stored but not shown | Pass |
| VII. Fixed stack | Same stack; two small Python packages for `.xlsx`. Google Drive behind a swappable `drive_fetcher` adapter with a fake, `fake` refused in staging/production (R7) | Pass |
| VIII. Tested rules | pytest for parsing, cleaning, flags, status rule, source matching, re-upload, all-or-nothing, permissions; Playwright for import → marketer check → review file | Pass |
| IX. Server-side authorization | Import routes require `reports` (or main admin); legacy image route requires review; checked on the server | Pass |
| X. Time | Form timestamp read as Baghdad time, stored UTC; preview expiry in UTC | Pass |

Project rules (CLAUDE.md): synthetic fixtures only; OCR never touches legacy images; no secrets added (the fetcher
needs none). **Gate: pass.**

## Project Structure

### Documentation (this feature)

```text
specs/014-legacy-import/
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
│   ├── models/legacy.py                     # LegacyImport, LegacySubscriber, LegacyImage, LegacyImportPreview
│   ├── core/legacy_row.py                   # pure: headers, cleaning, legacy number, flags (no DB)
│   ├── services/
│   │   ├── legacy_file.py                   # xlsx/csv → raw rows (openpyxl, csv)
│   │   ├── drive_fetcher.py                 # adapter: google (httpx) | fake
│   │   ├── legacy_import_service.py         # preview, fetch job, choices, confirm, expiry sweep
│   │   ├── legacy_source.py                 # registers `legacy` in match_service and linked_records
│   │   ├── image_store.py                   # + save_bytes (re-encode ≤1600 px JPEG)
│   │   ├── draft_service.py                 # referenced_file_names + legacy and staged files
│   │   └── review_service.py                # + open_legacy_image
│   ├── schemas/legacy_import.py
│   ├── schemas/admin_requests.py            # LinkedRecordOut + legacy_number, incomplete, extra
│   ├── api/admin_imports.py                 # /admin/imports/legacy/*
│   ├── api/admin_requests.py                # + /admin/legacy-images/{id}
│   ├── config.py                            # DRIVE_MODE
│   └── main.py                              # router, source registration, startup sweep
├── migrations/versions/0017_legacy_import.py
└── tests/
    ├── fixtures/legacy/                     # synthetic csv/xlsx + expected flags
    ├── unit/test_legacy_row.py, test_legacy_file.py, test_drive_fetcher.py
    └── integration/test_legacy_preview.py, test_legacy_confirm.py, test_legacy_source.py,
        test_legacy_linked_record.py, test_legacy_images.py, test_migration_0017.py

web/src/
├── lib/legacyImport.ts                      # API calls, flag labels
├── lib/labels.ts                            # SOURCE_LABELS.legacy «مشترك قديم», audit action label
├── pages/admin/import/ImportPage.tsx        # tabs: القدامى | SAS (قريباً)
├── pages/admin/import/LegacyImport.tsx      # upload → progress → preview → confirm → summary
├── pages/admin/pending/LinkedRecordCard.tsx # legacy fields, images route by source
├── pages/admin/pending/RequestImage.tsx     # image URL by kind
└── __tests__/legacyImport.test.tsx, linkedRecordCard.test.tsx

e2e/tests/legacy-import.spec.ts
.env.example                                 # DRIVE_MODE
```

**Structure Decision**: The existing `api/` + `web/` + `e2e/` layout. New backend code follows the 008–013 split:
pure rules in `core/`, database work in `services/`, routes in `api/`. The `legacy` source and resolver live in one
module registered at startup, the way `match_service` registers `sijil`.

## Complexity Tracking

No constitution violation to justify. The background fetch job and the preview table are the minimum that lets the
preview show failed images while keeping the save all-or-nothing (research R8, R9).
