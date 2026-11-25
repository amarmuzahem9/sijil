# Quickstart: Import of the SAS Subscribers (015)

How to check 015 end to end.
- Routes: [contracts/api.md](./contracts/api.md).
- Tables and rules: [data-model.md](./data-model.md).
- Decisions: [research.md](./research.md).

## Prerequisites

- The app runs with `docker compose up`, with the fake card reader and the fake OTP sender. No new env variable.
- Accounts: the main admin; an admin with `reports` only; an admin with `review` only; the demo marketer.
- Towers in the settings include `ALM03`, `KZF06`, `RBD01S` and `SMR01`.
- **Synthetic** SAS files in `api/tests/fixtures/sas/`. All usernames, names, phones and passwords are made up.
  - `sas_sample.csv` (and the same as `.xlsx`): about 20 rows that cover:
    - the three prefix shapes and an unknown prefix;
    - an empty and a repeated username;
    - an invalid and an empty phone;
    - a username phone that differs from the phone column;
    - a phone held by a pending synthetic request;
    - the username of an approved synthetic request;
    - unreadable dates.
    Every `ct_password` cell holds a unique marker `SYNTH-PW-…`.
  - `sas_sample_2.csv`: the same rows with one added, one phone and expiry changed, and one removed.
- The real file is imported only on the server, by the owner.

## Automated

```bash
docker compose exec api pytest tests/unit -k "sas"
docker compose exec api pytest tests/integration -k "sas or match_sources or linked_records or migration_0018 or marketer_privacy or admin_home or linked_counter or settings_areas_towers"
cd web && npm test -- sasImport linkedRecordCard
cd e2e && npx playwright test sas-import.spec.ts
```

All of these must pass, and the whole suites must stay green. Run Vitest from PowerShell (project note).

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the `review`-only admin, open «الاستيراد» | Not in the menu; the address answers «لا تملك صلاحية» |
| 2 | As the `reports` admin, upload a file without `username` | «الملف ينقصه عمود: username», no preview |
| 3 | Upload `sas_sample.csv` | Preview with counts, the mapping table with the unknown prefix, groups «بلا يوزر», «يوزر مكرر في الملف», «الهاتف في طلب سِجلّ» |
| 4 | Look at the database before confirming | No `sas_subscribers` row; no `SYNTH-PW-` anywhere |
| 5 | Confirm with the prefix unmapped | Refused; the page points to the prefix |
| 6 | Map the prefix, «تخطي للكل» on one group, change one row back to «استيراد», confirm | Summary with counts; skipped rows by SAS id and row number; no usernames or phones |
| 7 | «سجل العمليات» as the main admin | One «استيراد مشتركي SAS» line with counts only |
| 8 | The approved synthetic request whose username was in the file | Still «مقبول (بانتظار الربط)»; admin home, «بانتظار الربط» and the marketer counter unchanged |
| 9 | As the marketer, a new draft with a SAS row's phone, then one with the phone that is only in a username | Both: «المشترك موجود سابقاً، هل يود العودة للخدمة؟»; nothing about the SAS subscriber visible |
| 10 | «طلب العودة للخدمة» on that phone, submit; as the `review` admin open it | Linked record «مشترك SAS»: username, name, phone, tower, dates, expiry «حسب آخر استيراد» |
| 11 | Accept it | The request keeps the SAS username |
| 12 | Upload `sas_sample_2.csv` | Counts: 1 new, 1 «سيُحدَّث», 1 «غير موجود في آخر ملف»; the prefix is not asked again |
| 13 | Confirm; the marketer uses the removed row's phone | Still case 1 (the row still counts) |
| 14 | Settings: delete the tower the prefix was mapped to | Refused (in use) |
