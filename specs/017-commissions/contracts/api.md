# API Contract: 017

Admin commission routes need the main admin or an admin with `commissions`
(`require_permission("commissions")`): `403 forbidden` otherwise, for marketers too. Marketer routes stay
`require_roles("marketer")` and read only the caller's requests. Times are UTC ISO 8601; months are `YYYY-MM`
in Baghdad time; amounts are integers in IQD.

## Changed: `GET /api/marketer/dashboard`

Adds the tier block; `linked_without_commission` now also counts requests already paid in an earlier month.

```json
{
  "linked_this_month": 27,
  "linked_without_commission": 2,
  "month_label": "تشرين الثاني 2026",
  "tier_rate": 5000,
  "expected_amount": 135000,
  "next_tier": { "remaining": 3, "rate": 7000 },
  "recent_links": []
}
```

`next_tier` is `null` in the top tier.

## New: `GET /api/marketer/commissions/months`

Finished months with a linked request or a payment, newest first.

```json
{
  "items": [
    { "month": "2026-10", "month_label": "تشرين الأول 2026", "count": 30, "without_commission": 1,
      "rate": 7000, "amount": 210000, "paid": true }
  ]
}
```

Paid months carry the locked figures. Never `paid_by`, `paid_at` or alerts.

## New: `GET /api/admin/commissions/months`

```json
{ "items": ["2026-11", "2026-10", "2026-09"], "current": "2026-11" }
```

## New: `GET /api/admin/commissions?month=2026-10`

`422 validation_error` for a malformed month or a month after the current one.

```json
{
  "month": "2026-10",
  "month_label": "تشرين الأول 2026",
  "finished": true,
  "total_amount": 360000,
  "rows": [
    {
      "marketer_id": 7,
      "marketer_name": "علي",
      "count": 30,
      "without_commission": 1,
      "paid_before": 0,
      "tier_min_count": 30,
      "rate": 7000,
      "amount": 210000,
      "payable": false,
      "payment": { "paid_by_name": "الأدمن", "paid_at": "2026-11-02T08:00:00Z", "count_today": 29 },
      "alerts": [
        { "number_label": "T3C-1042", "at": "2026-11-10T12:00:00Z", "reason": "not_linked_in_sas" }
      ]
    }
  ]
}
```

- `payment` is `null` on an unpaid row; then `count`, `rate`, `amount` follow today's tiers.
- `payable` = finished month, no payment, `count > 0`.
- Rows: marketers with a linked request in the month or a payment, ordered by name. Archived and stopped
  marketers included.

## New: `GET /api/admin/commissions/{month}/marketers/{marketer_id}`

```json
{
  "counted": [
    { "id": 42, "number_label": "T3C-1042", "full_name": "…", "type": "new",
      "tower_name": "العلم 3", "tower_code": "ALM03", "linked_at": "2026-10-03T09:00:00Z" }
  ],
  "without_commission": [],
  "paid_before": [ { "…": "…", "paid_month": "2026-09" } ]
}
```

For a paid row, `counted` is the stored list (with `linked_at` = current link time, or `null` if undone).
No phone, username, national ID, family number, card field or image link (allow-list schema).
`404 not_found` when the marketer has no row in that month.

## New: `POST /api/admin/commissions/{month}/marketers/{marketer_id}/pay`

Body: the figures shown in the confirmation.

```json
{ "count": 30, "amount": 210000 }
```

`200` with the updated row. One transaction: the payment, its requests, the audit entry `commission.paid`
(entity `commission_payment`, id `"7:2026-10"`, `after {marketer_id, month, count, tier_min_count, rate,
amount}`).

| Error | When |
|---|---|
| `409 month_not_finished` «لا يُسجَّل الدفع قبل نهاية الشهر» | current (or future) month |
| `409 nothing_to_pay` «لا يوجد عدد محسوب لهذا الشهر» | count 0 |
| `409 commission_changed` «تغيّرت الأرقام، راجعها من جديد» | figures differ from the body |
| `409 already_paid` «تم تسجيل الدفع لهذا الشهر مسبقاً» | already paid (also the second of two concurrent calls) |
| `404 not_found` | unknown marketer |

A refused call writes nothing.

## Changed: `GET /api/admin/home`

Adds `commission_alerts: int | null` — the number of undos after payment in the last 30 days; filled for the
main admin and `commissions` holders, `null` for every other admin. The warning shows when it is > 0.

## New: `GET /api/admin/marketers/month-summary`

`require_permission("marketers")`. Current month only.

```json
{ "month_label": "تشرين الثاني 2026", "items": [ { "marketer_id": 7, "count": 27, "amount": 135000 } ] }
```

## Web routes

| Path | Who | Page |
|---|---|---|
| `/admin/commissions` | main admin, `commissions` | «العمولات»: month picker, rows, details, «تم الدفع», alerts |
| `/commissions` | marketer | «الأشهر السابقة» |
| `/admin/marketers` | `marketers` | two new columns: «عدد الشهر»، «العمولة المتوقعة» |
| `/admin` | every admin | warning «يوجد تراجع بعد الدفع» → `/admin/commissions` when `commission_alerts > 0` |
