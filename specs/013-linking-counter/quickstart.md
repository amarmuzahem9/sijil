# Quickstart: «تم الربط» and the Monthly Counter (013)

How to check 013 end to end.
- Routes: [contracts/api.md](./contracts/api.md).
- Stored fields and the counting rule: [data-model.md](./data-model.md).

## Prerequisites

- The app runs with `docker compose up`, with the fake card reader and the fake OTP sender, as in 008–012.
- Accounts: the demo marketer and a second marketer; the main admin; one admin with `link` only (no `review`).
- Test cards from `test-cards/` only. No real card images or subscriber data.

## Automated

```bash
docker compose exec api pytest tests/unit/test_unlink_reasons.py tests/unit/test_link_search.py
docker compose exec api pytest tests/integration -k "link or counter or admin_home or deletion or migration_0016 or notification"
cd web && npm test -- awaitingLink dashboard requests
cd e2e && npx playwright test linking-counter.spec.ts
```

All must pass, and the whole suites must stay green. Run Vitest from PowerShell (project note).

## Manual scenarios

| # | Do | Expect |
|---|---|---|
| 1 | As the marketer, submit a request that is auto-accepted | Home counter unchanged; the request is in «مقبولة» |
| 2 | As the `link`-only admin, open «بانتظار الربط» | The request is listed with number, name, username, phone, tower «اسم (رمز)», plan, marketer, acceptance date; no national ID, family number or image |
| 3 | Search «T3C-…», then the phone written `0780 123 4567`, then the username in lower case | The same row each time |
| 4 | Press «تم الربط» and confirm | The row leaves the list and appears under «المربوطة مؤخراً» |
| 5 | As the marketer, wait about 15 s, then open the home | Notification «تم ربط المشترك #T3C-…» with the name; «تم الربط هذا الشهر: 1»; the name in the latest links list |
| 6 | Open «الطلبات» ← «تم الربط» | The request with its link date; opening it shows green «تم الربط», the link date and the link message |
| 7 | Two admin browsers press «تم الربط» on another accepted request | One links; the other sees «تم ربط هذا الطلب مسبقاً»; one notification only |
| 8 | Admin undoes the first link with «ضُغط بالخطأ» | Back in «بانتظار الربط»; the marketer counter goes down by 1; notification «تم التراجع عن الربط» with «ضُغط بالخطأ»; the request is in «مقبولة» |
| 9 | Link it again | Counter goes up by 1 (not 2); the audit log shows link, undo, link with who and when |
| 10 | A return accepted with «لا» for commission, then linked | Counter unchanged; «و 1 بلا عمولة» appears under it |
| 11 | Main admin home | «تم الربط» today and month match the linked requests |
| 12 | Main admin opens the linked request by number and tries «حذف» | Refused: accepted and linked requests cannot be deleted |
| 13 | The second marketer opens the home | Counter 0; none of the first marketer's names |
| 14 | An admin without `link` | No «بانتظار الربط» in the menu; direct `/api/admin/links/awaiting` → 403 |
