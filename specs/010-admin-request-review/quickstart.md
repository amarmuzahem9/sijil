# Quickstart: Admin Review (010)

How to check 010 end to end. The routes are in [contracts/api.md](./contracts/api.md) and the stored
fields in [data-model.md](./data-model.md).

## Prerequisites

- The app runs: `docker compose up` (with the fake card reader and the fake OTP sender, as in
  008/009).
- The demo seed has: one marketer, the main admin, one admin with `review` only, one admin with
  `settings` only.
- Test cards only, from `test-cards/`. No real card images.

## Automated

```bash
docker compose exec api pytest tests/unit/test_review_check.py tests/unit/test_rejection_reasons.py
docker compose exec api pytest tests/integration -k "admin or marketer_privacy or log_safety or audit_completeness or migration_0013"
cd web && npm test -- adminReview
cd e2e && npx playwright test admin-review.spec.ts
```

All of these must pass, and the whole suites must stay green.

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the marketer, submit 5 pending requests: a second subscription, edited numbers, a conflict, a return by identity, a return by phone | — |
| 2 | Sign in as the `review` admin and open «طلبات بالانتظار» | 5 rows, oldest first, with the right labels. The «تعارض بالأرقام» filter shows 1 |
| 3 | Open the second subscription | The linked record with «عائلة موجودة», the 15-day reminder, «تاريخ الانتهاء غير متوفر» |
| 4 | Accept it | The status is accepted. The marketer sees «تمت الموافقة» and the username |
| 5 | Open the return and press «قبول» | The commission question must be answered first. The answer appears in the decision |
| 6 | Reject the conflict with «سبب آخر» and no text | Refused. With text it goes through, and the marketer sees the text |
| 7 | On the edited-numbers request, pin the reading's family number that matches an existing family | The type becomes second subscription, «اشتراك إضافي» is added, and «تعديل الأرقام» shows «تم التثبيت» |
| 8 | Pin a national ID and family number of an existing subscriber on a new request | A red warning. «قبول» asks «القبول رغم التحذير؟». After confirming, the audit shows the accept despite the warning |
| 9 | Two browsers accept the same request | One wins, the other sees «تم البت في هذا الطلب مسبقاً» |
| 10 | Sign in as the `settings` admin | No «طلبات بالانتظار» in the menu. The direct address and API calls are refused |
| 11 | Open «الرئيسية» as any admin | Today and month counts match what was done above. «تم الربط» is 0 |
| 12 | As the main admin, open «سجل العمليات» | Accept, reject and pin entries with no national ID, family number, phone or names |

The Arabic manual test steps for the owner go in `manual-test-ar.md` at the end of the
implementation, as in 008 and 009.
