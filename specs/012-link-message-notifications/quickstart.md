# Quickstart: Link Message, Request Statuses and Notifications (012)

How to check 012 end to end.
- Routes: [contracts/api.md](./contracts/api.md).
- Stored fields: [data-model.md](./data-model.md).

## Prerequisites

- The app runs with `docker compose up`, with the fake card reader and the fake OTP sender, as in 008–011.
- Accounts: the demo marketer and a second marketer, the main admin (has `review` and `delete`).
- Test cards from `test-cards/` only. No real card images or subscriber data.

## Automated

```bash
docker compose exec api pytest tests/unit/test_link_message.py tests/unit/test_request_status.py tests/unit/test_request_search.py
docker compose exec api pytest tests/integration -k "notification or link_message or request_search or migration_0015 or marketer_privacy or admin_decide or deletion"
cd web && npm test -- linkMessage notifications requestSearch
cd e2e && npx playwright test link-message-notifications.spec.ts
```

All must pass, and the whole suites must stay green.

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the marketer, submit a request that is auto-accepted, and open it | «رسالة الربط» block in the §8.4 format; «البرج: اسم البرج (رمز)»; a map link to the pin; no national ID or family number. No new notification |
| 2 | Press «نسخ رسالة الربط», paste in a note | The same text, line by line |
| 3 | Press «مشاركة بالواتساب» | WhatsApp opens with the text and no recipient |
| 4 | Submit a request that goes pending (edit a number) and open it | No link message |
| 5 | As the admin, accept it; stay as the marketer on another page for 15 s | The «الإشعارات» icon shows 1 |
| 6 | Open «الإشعارات», tap the row | «تمت الموافقة على الطلب #T3C-…» with the name; the request opens with its link message; the badge disappears |
| 7 | Submit another pending request; admin rejects it with «سبب آخر» and a note | Notification «تم رفض الطلب» with «سبب آخر» only (no note); the note shows in the request page |
| 8 | Admin deletes that rejected request («طلب مكرر») | A new notification «تم حذف الطلب» with number and reason; the earlier rejection notification now shows the number and «محذوف», no name |
| 9 | Two admin browsers accept the same pending request | One notification only |
| 10 | Search in «الطلبات»: part of a name; the phone as `0780 123 4567`; «١٠٠٤»; the deleted request's former name; its number | Own matches with status chips; the deleted one is found by number only |
| 11 | Sign in as the second marketer and search the first marketer's request number | Nothing found; `/api/notifications/{id}` of the other marketer gives 404 |
| 12 | «تعليم الكل كمقروء» | The badge goes away |
| 13 | Check the labels | «مقبول (بانتظار الربط)» blue, the other colours per §7.2 on marketer and admin screens |
