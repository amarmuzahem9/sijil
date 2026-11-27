# Quickstart: validating 019

Synthetic data only, on the owner's machine. Never export real card images.

## Prerequisites

- `docker compose up` (migration `0021_exports`; the new `exports` volume is mounted on `api` only).
- Accounts:
  - the main admin;
  - admins with `reports` only, `reports` + `review`, `review` only, and `commissions` only;
  - two marketers.
- Synthetic requests in October and November across two towers, two marketers and every status, including:
  - one submitted 31 October 23:30 Baghdad and linked 2 November;
  - one undone link;
  - one deleted request;
  - one whose name starts with «=».
- A paid October and an unpaid November (017), then a tier change.

## Automated

```powershell
docker compose exec api pytest -q tests/unit/test_report_period.py tests/unit/test_export_sheet.py tests/integration -k "report or export or commission_export"
cd web; npx vitest run reports commissionsExport   # from PowerShell
bash scripts/e2e.sh                                # the full Playwright suite, local stack only
```

Expected: all green; each new test was run red first; `test_report_performance` within SC-001 and SC-002.

## Manual scenarios

1. **Filters** (US1, FR-003): October by submission date lists the 31 October request; October by link date does
   not, and November by link date does. The undone link is absent from link-date filters, and the summaries add up
   to the total.
2. **Deleted** (FR-006): it shows «محذوف» with no name; in the sheet it has kept fields only and no image.
3. **Export as `reports` only** (FR-008, FR-009): no box; the ZIP has `requests.xlsx` without identity columns and
   no `cards/`.
4. **Export with the box** (FR-010):
   - As the main admin, tick «تضمين الرقم الوطني والعائلي والصور».
   - The ZIP has the identity columns and `cards/T3C-<n>-front.jpg` and `-back.jpg`, and each link in the sheet opens
     its image in the extracted folder.
   - The «=» name shows as text.
5. **Audit** (FR-011): «سجل العمليات» shows «تصدير طلبات» with the request numbers and «تنزيل تصدير» for each
   download, with no name or phone.
6. **Download guard** (FR-012):
   - Copy a download link and open it a second time, or after a minute: it is refused.
   - Another admin cannot download the export.
   - Remove `review` from a `reports` + `review` admin with a ready identity export: the download is refused and the
     file is gone.
7. **Commissions** (US3, FR-015): «تصدير» on «العمولات» for October and November matches the page row by row after
   the tier change. The paid month keeps its figures, and the file has no phone or ID.
8. **No money on reports** (FR-016) and **marketer** (FR-014): the reports page has no amount; a marketer has no
   export button, and direct calls are refused.
9. **Expiry** (FR-013): after 24 h (or with the clock moved in tests) the file is removed and the row reads «انتهت
   صلاحية الملف».

The Arabic manual test for the owner goes in `manual-test-ar.md` at the end of implementation.
