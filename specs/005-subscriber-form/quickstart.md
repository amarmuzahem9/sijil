# Quickstart & Validation: 005 New Subscriber Form

**Prerequisites**:
- The stack is running: `docker compose up -d --build`. Migration `0005` runs at api start, and
  the `uploads` volume is created.
- The 004 acceptance data exists: area «العلم», tower ALM01, plan PLUS 20,000 / 35,000.
- A marketer account exists (`seed-demo`).
- Optional: set `GOOGLE_MAPS_API_KEY` and `GOOGLE_MAPS_MAP_ID` in `.env` to see the map. Without
  them, the «الخريطة غير متوفرة حالياً» path is used.
- Card images in tests are synthetic only: generated rectangles with the text «بطاقة تجريبية».

**Automated checks**: `scripts/test-all.sh`. The new coverage expected:

- **pytest**:
  - **Ownership**: a second marketer gets 404 on every draft route and on `/api/draft-images/…`.
    So do an admin without `review` and an anonymous caller. The owner, the main admin and a
    `review` admin can open the image, and each open writes one `image_access_log` row.
  - **Version**: PATCH with a stale `version` returns 409 `draft_conflict` with
    `same_session=false` from another session, and `true` from the same session. A current
    `version` saves and increases it by 1. An image upload increases it too.
  - **Delete**: the files of both sides are gone from `UPLOADS_DIR` and the rows are gone. One
    `draft.deleted` audit entry exists, and it holds no name, national ID, family number or
    phone.
  - **Images**: files over 5 MB, non-JPEG files, and images wider than 1600 px are refused.
    Replacing a side removes the old file.
  - **Copies**: names and prices are copied from the catalog on save. A deactivated tower is
    cleared with a `choice_unavailable` notice. A price change appears as `price_changed` on GET.
  - **Validation**: the shared `draft_validation_cases.json` (national ID with 11, 12 and 13
    digits and Arabic digits; phones per §8.1; empty fields).
  - **Log safety**: national IDs and family numbers do not appear in the app logs on errors.
  - **CLI**: `prune-uploads` removes only unreferenced files older than 1 hour.
- **vitest**:
  - `fitWithin` and the compression with a mocked canvas (longest edge 1600, JPEG 0.8, no
    upscaling).
  - `draftValidation` against the shared cases.
  - The merging logic of the autosave queue.
- **Playwright**: scenario A below, using two browser contexts signed in as the same marketer.

## Scenarios

| # | Scenario | Expected |
|---|---|---|
| A | **Acceptance**: On phone context 1, «إضافة مشترك جديد»; upload a front and a back image; fill the name, a 12-digit national ID and the family number; «استخدم موقعي الحالي» with a granted geolocation; choose العلم / ALM01. In context 2, same account, open «الطلبات ← مسودات» and the draft | Every value, the pin coordinates and both images appear |
| B | In context 2 change the address; wait in context 1 | Within 30 s, context 1 shows «تغيّرت المسودة من جهاز آخر». «تحميل الأحدث» shows the new address |
| C | Throttle the network to offline while typing the address | The badge reads «غير متصل». Back online, it reads «محفوظ» and the value is on the server |
| D | Upload a 4000×3000 synthetic photo | The progress bar runs, and the stored image is ≤ 1600 px and JPEG. Kill the request midway: «فشل الرفع» → «إعادة المحاولة» succeeds |
| E | Type the national ID `١٢٣٤٥٦٧٨٩٠١` (11 digits) and the phone `+964 780 123 4567` | «الرقم الوطني 12 رقماً» appears. The phone is accepted as 07801234567. «النواقص» lists the ID |
| F | A complete form | «النواقص»: «كل الحقول مكتملة». «إرسال» stays disabled with its note |
| G | Choose PLUS; as admin change its second price to 40,000; reopen the draft | «تغيّر السعر» shows, and the price line shows 40,000 |
| H | «حذف» a draft and confirm | It leaves the list. «سجل العمليات» (main admin) shows «حذف مسودة» without card data. The files are gone from the volume |
| I | Marketer B pastes marketer A's draft URL | «المسودة غير موجودة» |
| J | No map key configured | «الخريطة غير متوفرة حالياً». «استخدم موقعي الحالي» still sets the pin |

Arabic manual test steps for the owner (`manual-test-ar.md`) are written at the end of
implementation, as in earlier features.
