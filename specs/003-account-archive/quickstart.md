# Quickstart & Validation: 003 Account Archive

**Prerequisites**: The stack is running (`docker compose up -d --build`; migration `0003` runs at
api start). Use synthetic accounts only.

**Automated checks**: `scripts/test-all.sh`.
- **pytest** (`test_archive.py`): authorization, main-admin protection, session revocation, list
  and route exclusions, phone reservation, restore state, audit.
- **vitest**: the access fixture with the `archive` page.
- **Playwright** (`archive.spec.ts`): scenarios A–D.

| # | Scenario | Expected |
|---|---|---|
| A | The main admin presses «حذف» on a signed-in marketer and confirms | The row leaves «المسوّقون». The marketer's next tap shows «الحساب موقوف، راجع الإدارة». Signing in is refused |
| B | Open «أرشيف الحسابات» | The marketer is listed with the archive time (Baghdad) and «المدير…» as archiver |
| C | «استرجاع» | The marketer is back in «المسوّقون» as «موقوف». Signing in is still refused |
| D | «إعادة تفعيل» | The marketer signs in with the old password |
| E | An admin holding `marketers` | No «حذف» button. «أرشيف الحسابات» is not in the menu. `/admin/archive` redirects |
| F | Add an account with the archived phone | «رقم الهاتف مستخدم لحساب آخر» |
| G | «سجل العمليات» | «أرشفة حساب» and «استرجاع حساب من الأرشيف» entries, with the account's name |
