# Implementation Plan: Reports and Export

**Branch**: `019-reports-export` | **Date**: 2026-11-27 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/019-reports-export/spec.md`;
- the owner's answers of 2026-11-27 (all A):
  - identity data and images only for the main admin and `reports` + `review`, ticked per export;
  - no marketer export;
  - no commission amounts on the reports page;
  - the spec assumptions approved;
- `docs/system.md` v1.25 §3.3, §7.4, §9, §10 items 4, 8 and 13, §11, §13, §15;
- the constitution v1.4.0 (no change).

## Summary

«التقارير والتصدير» stops being a placeholder: a filtered requests report with summaries, a ZIP export that leaves out
identity data unless an entitled admin ticks it, every export and download audited, and an export of «العمولات» built
from 017's own figures.

| Part | What |
|---|---|
| Period | pure `core/report_period.py`: week from Saturday, month, range in Baghdad days (R2) |
| Report | one filtered query, 50 per page, three summaries; no identity or money field (R3, R12) |
| Deleted | kept fields, «محذوف», no name, no image (R4) |
| Export | `exports` row + background job; the sheet is stored, the ZIP is streamed at download (R5, R6) |
| Sheet | openpyxl, RTL, two column sets, formula-safe text, relative image links (R9) |
| Download | one-use, 60-second ticket; permissions checked again; audited (R7, R8) |
| Storage | new `exports` volume on `api` only; removed after 24 h; never backed up (R10) |
| Commissions | `GET /commissions/export` from `commission_service.report`/`detail` (R11) |
| Pages | `/admin/reports`; an «تصدير» button on `/admin/commissions` |

Details: [research.md](./research.md).

**One deliberate tightening of the spec** (R6): the images are added to the ZIP at download time, so an image erased
by a deletion after the export was built is not sent. The spec's edge case said the file stays unchanged; this way
erased data never leaves, and the server never holds a multi-GB copy of the card images.

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new. openpyxl (already, 014) writes the sheet; the standard `zipfile` streams the ZIP.

**Storage**: PostgreSQL 16, migration `0021_exports` (the `exports` table and an index on `requests.submitted_at`).
There is a new Docker volume `exports`. See [data-model.md](./data-model.md).

**Testing**: pytest unit and integration, Vitest (from PowerShell), Playwright ([R14](./research.md#r14-tests-principle-viii-each-test-red-first)).
Each new test is run red before its code.

**Target Platform**: the company Linux server; the admin panel in the browser.

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**: with 20,000 requests, the report page loads in under 2 s (SC-001); an export of 1,000 requests
with images is ready in under 2 minutes while other pages answer normally (SC-002).

**Constraints**:
- No identity value or image in any export unless the box is ticked by the main admin or a `reports` + `review` admin.
  This is checked when the export is asked for, when it is built, and at download.
- Downloads go only to the requester, with a single-use ticket.
- No subscriber data in audit entries or logs; audit entries hold request numbers and counts.
- Export files are not in backups and are gone 24 h after ready.
- The reports page has no money; the commission export equals «العمولات».
- Marketers have no access.
- At most one export building per admin; 5,000 rows per export.

**Scale/Scope**:
- 1 migration (`0021_exports`), 1 model (`models/export.py`).
- api:
  - new pure `core/report_period.py`;
  - new services `report_service.py`, `export_service.py` (job, ticket, sweep, ZIP stream), `export_sheet.py` (request
    and commission workbooks);
  - new router `api/admin_reports.py` (reports + exports); changed `api/admin_commissions.py` (export route);
  - new schemas `schemas/reports.py`;
  - changed `errors.py` (7 codes), `config.py` (`exports_dir`), `main.py` (router, startup sweep, periodic sweep).
- compose: the `exports` volume on `api` in `docker-compose.yml` and the overlays that redefine `api` volumes; the
  `.env.example` comment for `EXPORTS_DIR`.
- web:
  - new `lib/reports.ts`, `pages/admin/reports/{Reports,ExportsList}.tsx`;
  - changed `router.tsx` (replace the placeholder), `pages/admin/placeholders.tsx` (drop `AdminReports`),
    `pages/admin/commissions/Commissions.tsx` (export button), `lib/commissions.ts`, `lib/auditFormat.ts` (3
    actions), `lib/labels.ts` (export states).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Check engine untouched; read-only over requests. |
| II. Protection of Identity Documents | ✅ | Identity columns and images only behind the opt-in and `reports` + `review`, checked three times; images read from private storage through the API only, and every image sent is written to `image_access_log` (`purpose = 'export'`, analysis C1); ZIP streamed, not stored; ticket single-use; nothing in logs. OTP and card readings never exported. |
| III. Permanent Audit Trail | ✅ | `requests.exported` (who, when, filters, numbers, identity flag), `export.downloaded`, `commissions.exported`; no personal data; append-only. |
| IV. Recorded Values Are Immutable | ✅ | The sheet shows stored values (names, prices at submission); commission figures come from the locked payment rows through 017's service; nothing is written to requests or payments. |
| V. Mobile-First and Arabic | ✅ | Arabic RTL page and sheet; status colors from `requestStatus.ts`; the page works at phone width; native download (no blob in memory). |
| VI. Simplicity | ✅ | No new service or library; the existing thread-pool job pattern; rules in `docs/system.md` 1.25 first. |
| VII. Fixed Technology Stack | ✅ | Same services; one new volume mounted only by `api` (`backup` does not mount it). |
| VIII. Tested Business Rules | ✅ | Period edges, column sets, formula safety, permission matrix, ticket, sweep, commission equality, performance (R14). |
| IX. Server-Side Authorization | ✅ | `require_permission("reports")` / `("commissions")`; identity right on the server; download re-checks the requester; marketers refused. |
| X. Time Handling | ✅ | UTC stored; Baghdad days, weeks and months computed on the server; sheet dates in Baghdad time. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/019-reports-export/
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
├── migrations/versions/0021_exports.py
├── app/
│   ├── config.py                         # exports_dir
│   ├── errors.py                         # period_invalid, no_rows, export_too_large, export_in_progress,
│   │                                     # identity_export_forbidden, export_not_ready/export_removed, ticket_invalid
│   ├── core/report_period.py             # new (R2)
│   ├── models/export.py                  # new
│   ├── schemas/reports.py                # new
│   ├── services/report_service.py        # new: filter, page, summaries, options (R3, R4, R13)
│   ├── services/export_sheet.py          # new: columns, request and commission workbooks (R9, R11)
│   ├── services/export_service.py        # new: create, job, ticket, download stream, sweep (R5–R8, R10)
│   ├── api/admin_reports.py              # new router
│   ├── api/admin_commissions.py          # + GET /export
│   └── main.py                           # router, startup and periodic sweep
└── tests/
    ├── unit/{test_report_period,test_export_sheet}.py
    └── integration/{test_reports_api,test_reports_privacy,test_exports_api,test_exports_sweep,
                     test_commission_export,test_report_performance}.py

web/src/
├── lib/{reports,commissions,auditFormat,labels}.ts
├── pages/admin/reports/{Reports,ExportsList}.tsx
├── pages/admin/commissions/Commissions.tsx
├── pages/admin/placeholders.tsx          # AdminReports removed
├── router.tsx
└── __tests__/{reports,commissionsExport}.test.tsx

docker-compose.yml (+ overlays that list api volumes)   # exports volume on api only
.env.example                                           # EXPORTS_DIR
api/tests/e2e_reports_seed.py                          # synthetic requests and images for the e2e
e2e/tests/reports-export.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout:
- the report and the export share one filter builder in `report_service`;
- `export_service` owns the lifecycle and the files;
- `export_sheet` only turns rows into workbooks, so its column rules are unit-tested;
- the commission export reuses `commission_service` and adds no second calculation.

## Complexity Tracking

No violations.
