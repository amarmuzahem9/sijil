# Quickstart: Subscriber Deletion (011)

How to check 011 end to end.
- Routes: [contracts/api.md](./contracts/api.md).
- Stored fields: [data-model.md](./data-model.md).

## Prerequisites

- The app runs with `docker compose up`, using the fake card reader and the fake OTP sender, as in
  008–010.
- The accounts: the demo marketer from the seed, the main admin, and two admins the main admin creates
  in «الأدمنية والصلاحيات»: one with `review` only, and one with `review` and `delete`.
- Use test cards from `test-cards/` only. No real card images.

## Automated

```bash
docker compose exec api pytest tests/unit/test_request_number.py tests/unit/test_deletion_reasons.py
docker compose exec api pytest tests/integration -k "deletion or by_number or marketer_privacy or log_safety or audit_completeness or migration_0014 or admin_home"
cd web && npm test -- deletion
cd e2e && npx playwright test subscriber-deletion.spec.ts
```

All of these must pass, and the whole suites must stay green.

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the marketer, submit two pending requests for the same family (A, then B with «اشتراك إضافي» pointing to A). Note the admin home counts | — |
| 2 | Sign in as the `review`-only admin and open A | No «حذف» button. A direct API call gets 403 |
| 3 | Sign in as the `review` + `delete` admin, open A, and press «حذف» | The dialog. The final button stays disabled until a reason is chosen and the number typed («١٠٠٥» works) |
| 4 | Delete A with «طلب مكرر» | Banner «تم حذف بيانات هذا الطلب» with who, when and the reason. No names, numbers, images or location. A leaves the pending list. «بالانتظار» on the home page drops by 1, and «مرفوعة» is unchanged |
| 5 | Open B | The reason «اشتراك إضافي» is still there. The linked record shows «سجل محذوف (#T3C-…)» only |
| 6 | Open an old image link of A | Not found. On the server, A's image files are gone from the uploads volume |
| 7 | As the marketer, open «الطلبات» | A shows «محذوف» with the reason, number, tower and date only. No copy or share |
| 8 | As the marketer, start a new draft with A's phone, and request a code right away | The phone is accepted and the code is sent (the hourly limit starts again) |
| 9 | Reject B with «سبب آخر» and a note. Then, as the deleting admin, type B's number in «فتح طلب برقمه», open it, and delete it with «خطأ إدخال» | It opens and is deleted. The decision shows the reason's name only, and the note is gone |
| 10 | Accept a third request, then try to delete it | No button. The API gets 409 «لا يمكن حذف طلب مقبول أو مربوط» |
| 11 | Two browsers: one deletes a pending request while the other accepts it | The first wins. The other sees «تم حذف هذا الطلب مسبقاً» or the delete is refused |
| 12 | Submit a new request | It gets the next number. A's and B's numbers are not reused |
| 13 | As the main admin, open «سجل العمليات» | Two «حذف مشترك» lines with number, who, when, status and reason, and no personal data. The old pin and reject lines are unchanged |
| 14 | As the main admin, open «الأدمنية والصلاحيات» | The «حذف مشترك» switch is there. Turning it off for the admin hides the button |

The owner's Arabic manual test steps go in `manual-test-ar.md` at the end of the implementation, as in
008–010.
