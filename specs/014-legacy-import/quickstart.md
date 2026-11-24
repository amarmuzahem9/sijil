# Quickstart: Import of the Legacy Subscribers (014)

How to check 014 end to end.
- Routes: [contracts/api.md](./contracts/api.md).
- Tables and rules: [data-model.md](./data-model.md). Decisions: [research.md](./research.md).

## Prerequisites

- The app runs with `docker compose up`, with the fake card reader, the fake OTP sender and `DRIVE_MODE=fake`.
- Accounts: the main admin; an admin with `reports` only; an admin with `review` only; the demo marketer.
- A **synthetic** legacy file, `api/tests/fixtures/legacy/legacy_sample.csv` (and the same as `.xlsx`): 12 rows with
  made-up names and numbers that cover every flag of research R6 and the statuses «تم», «ملغي», «مرفوض» and empty.
  Its image links use fake Drive ids (`fake-ok-…`, `fake-private-…`, `fake-missing-…`, `fake-html-…`) that the fake
  fetcher answers with generated images or failures. No real card image or subscriber data anywhere.
- The real file is imported only on the server, after deployment, by the owner.

## Automated

```bash
docker compose exec api pytest tests/unit -k "legacy"
docker compose exec api pytest tests/integration -k "legacy or match_sources or linked_records or migration_0017 or by_number or marketer_privacy or admin_home or linked_counter"
cd web && npm test -- legacyImport linkedRecordCard
cd e2e && npx playwright test legacy-import.spec.ts
```

All must pass, and the whole suites must stay green. Run Vitest from PowerShell (project note).

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the `review`-only admin, open «الاستيراد» | Not in the menu; the address answers «لا تملك صلاحية» |
| 2 | As the `reports` admin, upload a file without the «ID» column | «الملف ينقصه عمود: ID», no preview |
| 3 | Upload the sample file | «جارٍ سحب الصور» with progress, then the preview: totals, status values (3 rows «لا تُحسب في الفحص»), flagged rows grouped |
| 4 | Look at the database before confirming | No `legacy_subscribers` row |
| 5 | Press «تأكيد الاستيراد» with a flagged row left without a choice | Refused; the page points to the row |
| 6 | Choose for every flagged row (correct one odd family number), confirm | Summary with counts; skipped and «غير مكتمل» numbers listed; no family numbers shown |
| 7 | Open «سجل العمليات» as the main admin | One «استيراد المشتركين القدامى» line with counts only |
| 8 | Upload the same file again | Every row «مستورد سابقاً»; nothing to import; existing rows unchanged |
| 9 | As the marketer, start a new draft with a sample row's phone | «المشترك موجود سابقاً، هل يود العودة للخدمة؟»; nothing about the legacy subscriber visible |
| 10 | New draft with a sample row's family number written with `O` for `0`, a free phone, submit | «بانتظار موافقة المسؤول» as «إضافة اشتراك ثاني» |
| 11 | New draft with the phone of a row whose status is «ملغي» | No warning; normal flow |
| 12 | As the `review` admin, open the request of #10 | Linked record «مشترك قديم»: legacy number, name, phone, form date, «الحالة», «بيانات إضافية», images; no family number |
| 13 | Open one of its images | Image shown; `image_access_log` has a row with the legacy subscriber |
| 14 | Admin home, «بانتظار الربط», marketer counter | Same numbers as before the import |
| 15 | «فتح طلب برقمه» with `T3C-005` | «لا يوجد طلب بهذا الرقم» |
