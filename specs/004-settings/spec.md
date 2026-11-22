# Feature Specification: Settings

**Feature Branch**: `004-settings`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "الفيزة 004: صفحة الإعدادات. ارجع لـ docs/system.md الأقسام 2 و5.3 و8.3 و9 و10.
المطلوب (بصلاحية settings): المناطق: اسم. إضافة، تعديل، تفعيل/إيقاف. الأبراج: رمز (أحرف إنجليزية كبيرة وأرقام،
فريد، مثل ALM01)، اسم، المنطقة التابع لها، تفعيل/إيقاف. الفئات: الاسم (مثل PLUS)، سعر الشهر التجريبي، سعر الشهر
الثاني (بالدينار، أعداد صحيحة)، تفعيل/إيقاف. شرائح المكافآت: قائمة (أقل عدد مشتركين، سعر المشترك بالدينار).
القيم الافتراضية: 0 → 5,000، 30 → 7,000، 50 → 10,000. مدة صلاحية رمز OTP بالدقائق (الافتراضي 60). لا حذف لأي عنصر
مستخدم في طلب؛ فقط إيقاف. العنصر الموقوف لا يظهر في الاستمارة الجديدة ويبقى ظاهراً في الطلبات القديمة. تغيير
الأسعار يطبق على الطلبات الجديدة فقط ويُسجل في سجل العمليات بالقيمة القديمة والجديدة. الأرقام تُعرض بفواصل
الآلاف (20,000). معيار القبول: الأدمن ينشئ منطقة «العلم» وبرج ALM01 وفئة PLUS بسعري 20,000 و35,000."

**System document references**: `docs/system.md` v1.3 §2 (terms: region, tower, category, tier),
§5.3 (subscription section of the form), §8.3 (OTP validity), §9 (tiers), §10 page 6 «الإعدادات»;
constitution Principles III (audit) and IV (recorded values are immutable).

**Builds on**: feature 002 (the `settings` permission, page map, audit log and viewer).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Regions and towers (Priority: P1)

An admin with the `settings` permission opens «الإعدادات», adds the region «العلم», then adds the
tower ALM01 named «العلم 1» under it. Both are active and listed. Later the admin can rename them,
move a tower to another region, or deactivate either one.

**Why this priority**: Every request (feature 005) starts with region → tower; without them the
form cannot be built, and the acceptance criterion needs both.

**Independent Test**: Sign in as an admin holding only `settings`, add «العلم» and ALM01, rename
the tower, deactivate and reactivate the region, and see each change in «سجل العمليات».

**Acceptance Scenarios**:

1. **Given** an admin with `settings`, **When** they add region «العلم», **Then** it appears in the
   regions list as «فعّال».
2. **Given** a region with the same name already exists (ignoring extra spaces), **When** another is
   added, **Then** it is refused with «الاسم مستخدم».
3. **Given** region «العلم», **When** the admin adds tower code `alm01` named «العلم 1» in it,
   **Then** the code is stored as `ALM01` and the tower is listed under «العلم».
4. **Given** tower ALM01 exists, **When** another tower with code `ALM01` (any letter case) is
   added, **Then** it is refused with «رمز البرج مستخدم».
5. **Given** a code with characters other than English letters and digits (e.g. `ALM-01`,
   `ALM 01`, Arabic letters), **Then** it is refused with «الرمز أحرف إنجليزية كبيرة وأرقام فقط».
6. **Given** a tower or region, **When** the admin deactivates it, **Then** it shows «موقوف» and
   stays in the list; reactivating restores «فعّال».
7. **Given** an admin without `settings` or a marketer, **Then** the page is not in the menu, and
   the server refuses every settings action.

---

### User Story 2 - Categories and prices (Priority: P1)

The admin adds category «PLUS» with a trial-month price of 20,000 and a second-month price of
35,000 dinars. Prices show with thousands separators. Changing a price later applies to new
requests only and is recorded with the old and new values.

**Why this priority**: Prices are recorded on every request (§5.3) and are part of the
acceptance criterion.

**Independent Test**: Add PLUS with 20,000 / 35,000, change the second price to 40,000, and check
that the list shows «40,000» and that «سجل العمليات» shows 35,000 → 40,000.

**Acceptance Scenarios**:

1. **Given** the admin adds «PLUS» with 20000 and 35000, **Then** the list shows «20,000» and
   «35,000» and the category is «فعّال».
2. **Given** a price typed as «20,000», «٢٠٠٠٠» or « 20000 », **Then** it is accepted as 20000.
3. **Given** a price that is negative, has decimals, is empty, or is larger than 10,000,000, **Then**
   it is refused with a clear Arabic message.
4. **Given** a category name already used (ignoring letter case and spaces), **Then** it is refused.
5. **Given** the admin changes a price, **Then** one audit entry records the category, the old and
   the new price.
6. **Given** a price change, **Then** requests created before it keep their recorded prices
   (enforced from feature 005 onward; Principle IV).

---

### User Story 3 - Reward tiers (Priority: P2)

The admin sees the reward tiers pre-filled with 0 → 5,000, 30 → 7,000, 50 → 10,000, and can edit
them as a list: change a value, add a tier, or remove one, then save the whole list.

**Why this priority**: Needed for commissions (feature 016), but nothing reads tiers before then.

**Independent Test**: Open the tiers section, see the three defaults, add 80 → 12,000, save, and
check the audit entry shows the list before and after.

**Acceptance Scenarios**:

1. **Given** a new system, **When** the admin opens the tiers, **Then** they show 0 → 5,000,
   30 → 7,000, 50 → 10,000, each with its range («0 إلى 29», «30 إلى 49», «50 فأكثر»).
2. **Given** an edited list, **When** saved, **Then** it is validated: the first tier starts at 0,
   minimum counts are whole numbers and strictly increasing with no duplicates, prices are whole
   positive dinars, and at least one tier exists; otherwise it is refused with the reason.
3. **Given** a valid save, **Then** one audit entry records the whole list before and after.
4. **Given** a tier change, **Then** it applies to every month not yet marked «تم الدفع»,
   including the current one; a paid month keeps the tier and amount saved at payment (owner
   decision, system.md §9 v1.3). Only one current tier list is kept.

---

### User Story 4 - OTP validity (Priority: P3)

The admin sets how many minutes an OTP code stays valid (default 60).

**Why this priority**: Used from feature 007 (OTP); a default exists.

**Independent Test**: Change 60 to 30, see 30 after reload and an audit entry 60 → 30.

**Acceptance Scenarios**:

1. **Given** a new system, **Then** the value shows 60 minutes.
2. **Given** a whole number from 5 to 1,440, **When** saved, **Then** it is stored and audited with
   old and new values; other values are refused with the allowed range.

### Edge Cases

- Names are trimmed and inner spaces collapsed; empty names or names over 100 characters are
  refused. Category names are stored as typed; their uniqueness check ignores letter case.
- Tower codes are uppercased on save, 2–20 characters, English letters and digits only.
- A tower needs a region; a deactivated region can still be chosen when editing an existing tower,
  but new towers can only be added to active regions.
- Deactivating a region does not change its towers' own state, but none of its towers appear in the
  new-request form while the region is deactivated.
- Saving with no change writes no audit entry.
- Two admins editing the same item: the last save wins; both saves are audited.
- Numbers in Arabic-Indic digits or with thousands separators are accepted in every numeric field.
- Deleting (owner decision, system.md §10 v1.3): an item that is not used (no request or
  subscriber refers to it, and for a region, no tower belongs to it) can be deleted after a
  confirmation, and the deletion is audited with the deleted values. A used item shows no «حذف»
  and the server refuses to delete it with «العنصر مستعمل، يمكن إيقافه فقط».

## Requirements *(mandatory)*

### Functional Requirements

**Access**

- **FR-001**: Only the main admin and admins holding `settings` MAY view or change settings (page
  map of feature 002). The server MUST refuse everyone else.

**Regions**

- **FR-002**: Admins MUST be able to add a region (name), rename it, and deactivate/reactivate it.
  Region names MUST be unique (ignoring extra spaces).

**Towers**

- **FR-003**: Admins MUST be able to add a tower with a code, a name and its region, edit them, and
  deactivate/reactivate it. Codes are stored uppercase, MUST match English letters and digits only
  (2–20 characters), and MUST be unique regardless of letter case.
- **FR-004**: New towers MUST belong to an active region. The list MUST show each tower's region.

**Categories**

- **FR-005**: Admins MUST be able to add a category with a name, a trial-month price and a
  second-month price, edit them, and deactivate/reactivate it. Names MUST be unique ignoring case
  and spaces. Prices MUST be whole dinars from 0 to 10,000,000.
- **FR-006**: A price change MUST apply to new requests only: prices are copied onto each request
  when it is submitted (§5.3) and never recalculated.

**Tiers**

- **FR-007**: The system MUST start with the tiers 0 → 5,000, 30 → 7,000, 50 → 10,000 (§9).
- **FR-008**: Admins MUST be able to edit the tiers as a whole list (change, add, remove rows) under
  the validation of US3 scenario 2. The list MUST be shown with each tier's range.

**OTP**

- **FR-009**: The system MUST start with an OTP validity of 60 minutes; admins MUST be able to set
  a whole number from 5 to 1,440.

**Lifecycle**

- **FR-010**: Regions, towers and categories MAY be deleted only while unused (no request or
  subscriber refers to them; for a region, no tower belongs to it); once used they can only be
  deactivated. Deactivated items MUST NOT be offered in the new-request form and MUST keep
  showing on existing requests (enforced by the request features).

**Audit and display**

- **FR-011**: Every change (add, edit, deactivate, reactivate, delete of any item; the tier list; the OTP
  validity) MUST write one audit entry with old and new values. Price changes MUST show both prices.
- **FR-012**: All money values MUST be shown with thousands separators (20,000) and the unit
  «د.ع»; numeric inputs MUST accept Arabic-Indic digits and separators.
- **FR-013**: All screens MUST be Arabic, right-to-left, and usable on a phone.

### Key Entities

- **Region**: name, active state.
- **Tower**: code (unique, uppercase), name, region, active state.
- **Category**: name (unique), trial-month price, second-month price (whole dinars), active state.
- **Reward tier**: minimum monthly count, price per subscriber; the tiers form one ordered list.
- **System setting**: OTP validity in minutes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Acceptance: an admin holding `settings` creates region «العلم», tower ALM01 and
  category PLUS (20,000 / 35,000) in under 3 minutes from a phone.
- **SC-002**: 100% of settings actions by users without `settings` (other than the main admin) are
  refused by the server.
- **SC-003**: 100% of invalid codes, duplicate names/codes and invalid prices are refused with an
  Arabic reason.
- **SC-004**: 100% of price, tier and OTP changes produce one audit entry with old and new values.
- **SC-005**: 100% of money values on the settings page show thousands separators.

## Assumptions

- Tower codes may be edited while no request uses them (always true until feature 005); once
  used, the code is locked. Changing a code never alters usernames already recorded on requests.
- A tower may be moved to another region; requests record their own region and tower, so old
  requests are not affected.
- The new-request form (feature 005) and OTP (feature 007) read these settings; this feature only
  manages them.
- Regions, towers and categories start empty; tiers and OTP validity start with the defaults.
- Tests use made-up regions and towers only where real ones are not needed; «العلم» and ALM01 are
  the owner's own examples from §2.
