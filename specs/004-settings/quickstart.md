# Quickstart & Validation: 004 Settings

**Prerequisites**:
- The stack is running (`docker compose up -d --build`; migration `0004` runs at api start).
- The tiers and the OTP setting are seeded.
- If the browser shows an old screen, see README «إذا لم يظهر تعديل جديد في المتصفح».

**Automated checks**: `scripts/test-all.sh`. The new coverage expected:

- **pytest**:
  - **Authorization**: a `settings` admin and the main admin pass; an admin without `settings`
    and a marketer get 403. The catalog is open to any signed-in user.
  - **Towers**: the code is uppercased and unique ignoring case, and invalid codes are refused.
  - **Delete**: a used tower cannot be deleted, through both the registry check and the FK
    backstop. An area with towers cannot be deleted. Unused items delete and are audited.
  - **Validation**: the price range, the tier list rules, and the OTP range.
  - **Audit**: one entry per change, with the old and new price.
  - **Catalog**: only active items, and no towers of inactive areas.
- **vitest**:
  - `parseMoney` and `formatMoney` (Arabic digits, separators).
  - The tier range labels.
- **Playwright**: the acceptance path (scenario A) for an admin holding only `settings`.

| # | Scenario | Expected |
|---|---|---|
| A | **Acceptance**: an admin with only «الإعدادات» adds area «العلم», tower `alm01` named «العلم 1», and plan «PLUS» with `20000` / `٣٥٬٠٠٠` | Lists show «العلم», «ALM01 · العلم 1 · العلم», and «PLUS 20,000 د.ع / 35,000 د.ع» |
| B | Add tower `ALM01` again, or `ALM-01` | «رمز البرج مستخدم» / «الرمز أحرف إنجليزية كبيرة وأرقام فقط» |
| C | Change PLUS second price to 40,000 | «سجل العمليات» shows «تعديل فئة», with سعر الشهر الثاني 35,000 → 40,000 |
| D | Delete area «العلم» while it has ALM01 | No «حذف» shown. A direct API delete returns «العنصر مستعمل، يمكن إيقافه فقط» |
| E | Delete an unused plan | It is removed after confirmation and audited as «حذف فئة» |
| F | Tiers tab | 0 إلى 29 → 5,000; 30 إلى 49 → 7,000; 50 فأكثر → 10,000. Saving a list whose first tier is 5 is refused |
| G | عام tab | 60. Saving 3 is refused, and saving 30 is stored and audited |
| H | Deactivate area «العلم». As a marketer, call `GET /api/catalog` | No «العلم» and no ALM01 |
| I | Admin without «الإعدادات» | No menu item, and `/admin/settings` redirects |
