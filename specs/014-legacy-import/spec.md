# Feature Specification: Import of the Legacy Subscribers (Google Form file)

**Feature Branch**: `014-legacy-import`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "الفيزة 014: استيراد المشتركين القدامى. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام
المتعلقة) ولـ docs/features.md، وانتبه لمحرك الفحص (008) والطلب المحذوف (011) وعدّاد الربط والعمولة (013). بعد المواصفة
لخّصلي بالعربي شنو ينستورد ومنين، وشنو يتغيّر للأدمن والمسوّق، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §3.3 (permission `reports` covers import), §3.1 (the marketer
never sees anything about another subscriber), §6 intro (the check runs on every source, including imported legacy
subscribers), §6.1 (decision table; notes: legacy subscribers without a national ID are checked by family number
and phone only, and a legacy family match is treated as case 3; imported subscribers count as «existing»), §6.2
(comparison keys), §6.3 item 4 (historical username on a return), §6.4 (the review file shows the linked previous
subscription with its images), §7.3 (legacy numbers T3C-001 to T3C-109 kept in a separate field, never reused as
request numbers), §7.4 (deletion applies to requests only), §8.1 (phone normalization), §10 item 9 (import page,
`reports`), §12.1 (the legacy file: columns, 109 rows, no national ID, name rule, extra fields, Google Drive images,
review of duplicate and odd family numbers, «غير مكتمل»), §13 (private image storage, every image access logged,
audit log); constitution Principles I (check against imported legacy subscribers), II (identity documents), III
(audit; subscribers never physically deleted), VIII (tested rules), IX (server-side authorization), X (UTC storage).
`docs/features.md` holds no pending idea for this feature.

**Builds on**: 008 (the check engine with its source registry: a record without a national ID simply never matches
on it), 009 (return by phone or by identity, «إضافة اشتراك ثاني», historical username on a return), 010 (the review
file and its linked-record registry, «سجل غير متوفر»), 011 (deleted requests leave every check; «سجل محذوف»), 012
(notifications), 013 (counter and links count requests only).

**Out of scope (later features)**: the SAS file import and SAS expiry (015); the admin «المشتركون» page with search,
subscriber file and the «غير مكتمل» filter (018); filling a legacy subscriber's missing national ID from a later
request (018 or later, needs a rule in `docs/system.md`); reports and export (019). Card reading (OCR) is never run
on legacy images.

**Governance changes this feature needs** (approved by the owner on 2026-11-24): `docs/system.md` 1.19 — §12.1
(preview before saving, a re-upload adds only new legacy numbers, rows with status «ملغي» or «مرفوض» are imported
but never count in the check, no undo after confirmation, no card reading on legacy images, names kept as written).
No constitution change.

## Clarifications

### Session 2026-11-24

- Q: What happens when the legacy file is uploaded again after a first import? → A: Only rows whose legacy number
  is new are added; rows already imported are left unchanged.
- Q: Which «الحالة» values keep a legacy row out of the check? → A: «ملغي» and «مرفوض». Such rows are imported but
  never count as «existing»; every other value counts.
- The assumptions below (no undo after confirmation, preview expires after one hour, names kept as written, editing
  and the subscriber list left to 018) were approved as written.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The admin imports the legacy file after a preview (Priority: P1)

An admin with the `reports` permission (or the main admin) opens «الاستيراد» and chooses «المشتركون القدامى». They
upload the legacy file exported from the Google Form. Nothing is saved yet: the page shows a preview with the row
count, how many rows are ready, and every row that needs a look, grouped by problem (family number repeated in the
file, family number not 18 characters long, invalid or missing phone, phone repeated in the file, phone or family
number already held by an existing Sijil request, missing or repeated legacy number, missing images). The admin
resolves each flagged row, then presses «تأكيد الاستيراد». The rows are saved as legacy subscribers, and a summary
shows how many were imported, skipped, and marked «غير مكتمل».

**Why this priority**: Until the legacy subscribers are in Sijil, the anti-fraud check (Principle I) misses 109
known subscribers: a marketer could register one of them as new.

**Independent Test**: Upload a synthetic 109-row file with known problems; confirm the preview lists exactly those
rows under the right problems, that nothing is saved before confirmation, and that after confirmation the counts in
the summary match the rows.

**Acceptance Scenarios**:

1. **Given** a file with the 15 documented columns, **When** the admin uploads it, **Then** a preview appears and no
   legacy subscriber is saved.
2. **Given** a file missing a required column (for example «الرقم العائلي» or «ID») or not a readable sheet,
   **When** it is uploaded, **Then** the page names the problem in Arabic and offers no confirmation.
3. **Given** two rows with the same family number (comparison key §6.2), **When** the preview shows, **Then** both
   rows appear under «رقم عائلي مكرر في الملف», and for each the admin chooses «استيراد» or «تخطي».
4. **Given** a row whose family number is not 18 characters, **When** the preview shows, **Then** it appears under
   «طول غير معتاد للرقم العائلي» with the value as written; the admin may import it as is, correct it, or skip it.
5. **Given** a row whose phone fails §8.1, **When** the preview shows, **Then** it appears under «هاتف غير صالح»; if
   imported, it is saved without a phone and takes no part in the phone check.
6. **Given** a row whose phone or family number is already held by a pending, accepted or linked Sijil request,
   **When** the preview shows, **Then** it appears under «موجود في طلبات سِجلّ» with the request number, and the
   admin chooses «استيراد» or «تخطي».
7. **Given** every flagged row has a choice, **When** the admin confirms, **Then** the import is saved as one step
   (all chosen rows or none), audited, and the summary appears.
8. **Given** a flagged row without a choice, **When** the admin tries to confirm, **Then** confirmation is refused
   and the page points to the rows still waiting.

---

### User Story 2 - The check engine knows the legacy subscribers (Priority: P1)

After the import, every marketer check (the early warning while typing, and the authoritative check at submission)
also looks at the legacy subscribers, across all regions and towers, exactly as §6.1 says for a record that has no
national ID: it can match only on phone and family number.

**Why this priority**: This is the reason for the import.

**Independent Test**: Import a synthetic legacy row, then submit drafts that reuse its phone, its family number, or
a new phone and family; confirm each gets the §6.1 outcome.

**Acceptance Scenarios**:

1. **Given** a legacy subscriber with phone P, **When** a marketer enters P on a new draft, **Then** case 1 applies:
   «المشترك موجود سابقاً، هل يود العودة للخدمة؟» with «طلب العودة للخدمة» and «الاتصال بالإدارة», and at
   submission a new request with P is refused and the draft stays.
2. **Given** a legacy subscriber with family number F (any spelling with the same comparison key, for example `O`
   for `0`), **When** a marketer submits a new request with F and a free phone, **Then** case 3 applies: the request
   becomes «إضافة اشتراك ثاني» and waits for the admin («لهذه العائلة اشتراك سابق»).
3. **Given** a legacy subscriber, **When** a marketer submits a new request with a national ID that no one holds,
   a family number and phone that no legacy or Sijil record holds, **Then** nothing about the legacy data changes
   the outcome.
4. **Given** a return by phone that targets a legacy subscriber, **When** it is accepted, **Then** a new username is
   generated (§6.3 item 4: legacy records have no historical username).
5. **Given** any of the above, **When** the marketer sees the result, **Then** no name, phone, number, image or
   legacy number of the legacy subscriber is shown to them (§3.1).
6. **Given** a legacy row the admin skipped at import, **When** a marketer uses its phone or family number, **Then**
   it does not match (a skipped row is not saved).
7. **Given** a legacy subscriber whose status is «ملغي» or «مرفوض», **When** a marketer uses its phone or family
   number, **Then** it does not match.

---

### User Story 3 - The admin sees the legacy record in the review file (Priority: P2)

When a pending request is linked to a legacy subscriber (return by phone, or second subscription by family), the
review admin sees that record in the request file like any other linked previous subscription: legacy number
(T3C-0xx), full name, phone, the form date as registration date, the legacy status, the reason it is linked, and
its card images if they were imported; a record without images shows «غير مكتمل».

**Why this priority**: The admin decides cases 1 and 3 by comparing with the previous subscription; without this
view the matches are blind.

**Independent Test**: Create a pending request matching a synthetic legacy row; open the review file as a review
admin and confirm the fields and images; open the same as a marketer and confirm nothing is visible.

**Acceptance Scenarios**:

1. **Given** a pending request linked to a legacy subscriber, **When** a review admin opens it, **Then** the linked
   record shows with the source «مشترك قديم», the legacy number and the fields above, and never a request number.
2. **Given** the legacy record has images, **When** the admin opens one, **Then** it is served only after the
   permission check, and the access is logged (§13).
3. **Given** the legacy record has a missing image, **When** it is shown, **Then** it carries «غير مكتمل».
4. **Given** the extra fields (mother's name, mother's father's name, birth date), **When** the record is
   shown, **Then** they appear as «بيانات إضافية» for the admin only, and they never take part in a check. The
   e-mail columns are stored but not shown.

---

### User Story 4 - Legacy subscribers stay out of requests, counters and commissions (Priority: P2)

Legacy subscribers are subscribers, not requests. They have no marketer and no status in the request flow.

**Independent Test**: After importing, compare marketer home, admin home, «بانتظار الربط», «طلبات بالانتظار»,
notifications and the monthly counter with their values before the import.

**Acceptance Scenarios**:

1. **Given** an import of N rows, **When** it is saved, **Then** the admin home numbers (submitted, accepted,
   pending, linked, rejected), «بانتظار الربط», «طلبات بالانتظار», every marketer counter and «و M بلا عمولة»
   are unchanged, and no notification is sent.
2. **Given** a legacy number such as `T3C-005`, **When** it is typed in «فتح طلب برقمه» or in a marketer's request
   search, **Then** it opens or finds no request (legacy numbers are not request numbers, §7.3).
3. **Given** a legacy subscriber, **When** an admin looks for a «حذف» action on it, **Then** there is none: §7.4
   applies to requests only, and subscribers are never physically deleted (Principle III).
4. **Given** a later Sijil request that a review admin deletes (§7.4) while it is linked to a legacy record,
   **When** the deletion happens, **Then** the legacy record is unchanged.

---

### Edge Cases

- **Re-uploading the file**: rows whose legacy number is already imported are shown as «مستورد سابقاً» and left
  unchanged (not updated, not re-fetched); only rows with a new legacy number can be imported. Their family number
  and phone are also compared with the legacy subscribers already imported, and a match is flagged like a repeat
  in the file.
- **The «الحالة» column**: a row whose status is «ملغي» or «مرفوض» (after trimming spaces) is imported but never
  counts as «existing» in the check; the preview shows how many such rows there are, and they are not flagged for a
  conflict with Sijil requests or with other rows. Any other value, or an empty one, counts.
- **Images that cannot be fetched** (file not shared «لأي شخص لديه الرابط», deleted, not an image, too large): the
  row is still importable, without that image, and is marked «غير مكتمل»; the preview and the summary list it with
  the reason in Arabic.
- **Image fetching is slow or the network drops** mid-import: the save is all or nothing; a failed import saves no
  subscriber and no image, and the admin can start again.
- **Hidden direction marks, spaces, Arabic or Indic digits** in phones and numbers: phones follow §8.1, family
  numbers keep the written value and compare by the §6.2 key.
- **Names with odd characters** (digits, Latin letters, diacritics): the name is joined from the first three name
  columns as written, after trimming and collapsing spaces; it is not rejected (historical data). The 5.1 name
  rules apply only to new forms.
- **A family number that is empty**: the row is flagged «بلا رقم عائلي»; if imported, it matches only on phone.
- **A row with neither a valid phone nor a family number**: flagged «لا يشارك في الفحص»; the admin may still import
  it (kept as a record only, it can never match) or skip it.
- **The same legacy number twice**, or a missing one: flagged; a legacy number must be unique, so only one of the
  repeated rows can be imported.
- **Concurrent imports** by two admins: only one confirmation runs at a time; the second waits, is re-checked
  against what the first saved, and is refused with «تغيّرت البيانات منذ المعاينة» if any of its rows now needs a
  new choice.
- **A preview left unconfirmed**: it expires without saving anything.
- **Rejected or deleted Sijil requests** never block an import row and are not listed under «موجود في طلبات
  سِجلّ» (same rule as §6.1 and §7.4).

## Requirements *(mandatory)*

### Functional Requirements

**Upload and preview**

- **FR-001**: The «الاستيراد» page MUST offer «المشتركون القدامى» only to the main admin and admins holding
  `reports`; the server MUST refuse every import action to anyone else.
- **FR-002**: The system MUST accept the Google Form export as a spreadsheet (`.xlsx`) or a comma-separated file
  (`.csv`, UTF-8), recognize the columns of §12.1 by their Arabic headers, and refuse a file that lacks «الاسم
  الاول»، «الرقم العائلي»، «رقم الهاتف» or «ID», naming the missing column.
- **FR-003**: Uploading MUST NOT save any subscriber or image; it MUST produce a preview with the total, the ready
  rows, and every flagged row grouped by problem: family number repeated in the file, family number length not 18,
  family number empty, phone invalid or empty, phone repeated in the file, phone or family number held by a pending,
  accepted or linked Sijil request (with its request number), legacy number missing or repeated, image missing or
  not fetchable.
- **FR-004**: For each flagged row the admin MUST choose «استيراد» or «تخطي»; for an odd-length family number they
  MAY instead type a corrected value. The original file value MUST be kept next to a corrected one.
- **FR-005**: Confirmation MUST be refused while any flagged row has no choice.
- **FR-005a**: Each group of flagged rows MUST offer «تخطي للكل», which sets «تخطي» on every row of the group; the
  admin MUST still be able to change any of those rows afterwards.

**Saving**

- **FR-006**: On confirmation the system MUST save, as a single all-or-nothing step, one legacy subscriber per
  chosen row, holding: legacy number (`T3C-001` … `T3C-109`, separate from request numbers), the form timestamp,
  first, second and third names and the full name (first + second + third), family number as written and its
  comparison key, phone normalized by §8.1 (or none if invalid), the «الحالة» value, extra data (mother's name,
  mother's father's name, birth date, both e-mail columns), the import it came from, and the «غير مكتمل» mark when a
  card image is missing.
- **FR-007**: The system MUST fetch each Google Drive image link (`open?id=…`) after upload, before confirmation, and store the image in
  Sijil's private image storage (§13), front and back, named by legacy number and side. A link that cannot be
  fetched MUST NOT stop the import; that row is saved without it and marked «غير مكتمل».
- **FR-008**: Legacy images MUST never be sent to card reading (OCR).
- **FR-009**: The import MUST be written to the audit log: who, when, file name, rows imported, rows skipped, rows
  marked «غير مكتمل», and corrected family numbers by reference (the audit text MUST NOT carry family numbers or
  phones, Principle II and III).
- **FR-010**: After the save, the page MUST show a summary with the counts and the legacy numbers of the skipped
  and «غير مكتمل» rows, with no family numbers in it.

**Check engine**

- **FR-011**: Legacy subscribers MUST be a source of the check engine (§6, Principle I) for both the early check and
  the authoritative check at submission, across all regions and towers, matching on phone (§8.1) and family number
  (§6.2 key) only. They MUST never match on national ID.
- **FR-012**: A legacy record whose phone matches MUST give case 1; one whose family number matches with no phone
  match MUST give case 3 (§6.1 notes). Legacy records MUST never block a return as «pending».
- **FR-013**: A return accepted against a legacy target MUST get a newly generated username.
- **FR-014**: Nothing about a legacy record MUST reach a marketer, in any response or message (§3.1).

**Review file**

- **FR-015**: The review file MUST resolve a linked legacy record and show it to review admins with: source «مشترك
  قديم», legacy number, full name, phone, form date, «الحالة», reason linked, images (if any), «غير مكتمل» when
  incomplete, and the extra data as «بيانات إضافية». Like every linked record (010), it MUST NOT carry the family
  number.
- **FR-016**: Every opening of a legacy image MUST go through the permission check and be logged, like request
  images.

**Isolation from requests**

- **FR-017**: Legacy subscribers MUST NOT appear in, or change, any request list or count: «طلبات بالانتظار»,
  «بانتظار الربط», admin home numbers, marketer lists and counters, «و M بلا عمولة», commissions, notifications.
- **FR-018**: Legacy numbers MUST NOT be accepted as request numbers by «فتح طلب برقمه» or the marketer search.
- **FR-019**: Legacy subscribers MUST NOT be physically deleted; there is no delete action on them in this feature.

**Re-import and status**

- **FR-020**: Uploading the file again MUST add only rows whose legacy number is not imported yet; rows already
  imported MUST stay unchanged and appear in the preview as «مستورد سابقاً». Duplicate checks (FR-003) MUST also
  compare new rows with the legacy subscribers already imported.
- **FR-021**: A legacy subscriber whose status is «ملغي» or «مرفوض» MUST NOT count as «existing» in the check (it is
  not a source match, like a rejected request in §6.1); every other legacy subscriber counts.

### Key Entities

- **Legacy subscriber**: one person from the old Google Form. Legacy number, form timestamp, names and full name,
  family number (as written, corrected value if any, comparison key), phone (normalized or none), legacy status,
  extra data, «غير مكتمل» mark, the import it came from. No national ID, no username, no tower, no marketer.
- **Legacy image**: a front or back card image fetched from Google Drive, stored privately, tied to one legacy
  subscriber; the fetch outcome is kept when it failed.
- **Legacy import**: one confirmed import: who, when, file name, counts, and the per-row choice for flagged rows.
- **Import preview**: a temporary, unsaved reading of an uploaded file with its flagged rows; it expires if not
  confirmed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every one of the 109 legacy rows ends either imported or knowingly skipped, and the summary counts
  add up to the row count of the file.
- **SC-002**: After the import, 100% of new requests that reuse an imported legacy phone are stopped as case 1, and
  100% that reuse an imported legacy family number (same comparison key) go to the admin as a second subscription.
- **SC-003**: The admin finishes the whole import, from upload to summary, in under 15 minutes for the 109-row file,
  including the review of flagged rows.
- **SC-004**: No marketer screen, response or message ever shows any field of a legacy subscriber.
- **SC-005**: Admin home numbers, marketer counters and the «بانتظار الربط» list are identical before and after the
  import.
- **SC-006**: A failed import (network drop, refused file) leaves zero legacy subscribers and zero images saved.

## Assumptions

- The file is the Google Form export described in §12.1, about 109 rows; the admin downloads it from Google
  Sheets and uploads it; Sijil does not connect to Google Sheets.
- At import time the Drive image files are shared «لأي شخص لديه الرابط», and the server can reach Google Drive.
  Images are fetched once at import; the links are not used again.
- A preview stays valid for one hour, then expires.
- The «بيانات إضافية» are kept for the admin to compare with a later card; they are never checked or reported.
- Tests and examples use only synthetic rows and synthetic images (CLAUDE.md, constitution); the real file is
  imported only on the server.
- Legacy records are read-only in this feature; editing them, and showing them in a subscriber list with search and
  the «غير مكتمل» filter, comes with 018.
