# Quickstart: validating 017

Synthetic data only (no real cards or subscribers).

## Prerequisites

- `docker compose up` (services `web`, `api`, `db`, `proxy`, `ocr`, `backup`); migration `0020` applied on start.
- Default tiers: 0 → 5,000; 30 → 7,000; 50 → 10,000 (settings › الشرائح).
- Accounts: the main admin, an admin with `commissions` only, an admin with `link` only, an admin with
  `marketers` only, two marketers A and B.

## Automated

```powershell
docker compose exec api pytest -q tests/unit/test_commission.py tests/integration -k commission
cd web; npx vitest run commissions dashboard marketers   # from PowerShell (see memory note)
npx playwright test e2e/tests/commissions.spec.ts
```

Expected: all green; each new test was run red first.

## Manual scenarios

1. **Home tier** — link 27 requests of A this month: A's home shows 5,000, 135,000 and «باقيلك 3 وتصير 7,000
   للمشترك». Link 3 more: 7,000, 210,000, «باقيلك 20…». (spec US1)
2. **What does not count** — a return accepted with «لا» shows only in «بلا عمولة»; pending, rejected, accepted
   not linked, deleted requests and a legacy or SAS import change nothing. (FR-002, FR-003)
3. **Report** — as the `commissions` admin, open «العمولات», pick the previous month (set by the test clock): rows,
   totals and details match. The `link`-only admin has no menu entry and gets 403 on the URL. (US2)
4. **Pay** — «تم الدفع» on A's previous month: confirmation shows count, rate, amount; after confirm the row is
   locked and the audit log has «تسجيل دفع عمولة». A second click: «تم تسجيل الدفع لهذا الشهر مسبقاً». No button
   on the current month or a zero row. Change the tiers: the paid row does not move. (US3)
5. **Undo after pay** — as the `link` admin undo one of A's paid links: the paid row keeps its figures and shows
   «تراجع بعد الدفع» with the number, date and reason; the admin home shows «يوجد تراجع بعد الدفع» for the main
   admin and the `commissions` admin only, and not any more once the test clock is 31 days later (the report
   alert stays). Link it again: it shows under «مدفوع سابقاً», not in the count. (US4,
   FR-016)
6. **Marketer past months** — A opens «الأشهر السابقة»: the paid month shows «تم الدفع» with its locked
   figures, no payer; B never sees A's months. (FR-007)
7. **Marketers page** — the `marketers` admin sees A's count and amount equal to A's home. (US5, SC-002)

The Arabic manual test for the owner goes in `manual-test-ar.md` at the end of implementation.
