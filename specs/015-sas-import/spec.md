# Feature Specification: Import of the SAS Subscribers

**Feature Branch**: `015-sas-import`

**Created**: 2026-11-25

**Status**: Clarified

**Input**: User description: "الفيزة 015: استيراد مشتركي SAS. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام
المتعلقة) ولـ docs/features.md، واستعمل نفس نمط استيراد 014 (المعاينة، «تخطي للكل»، الحفظ الكامل أو لا شي، السجلات بلا
بيانات شخصية). وانتبه لمحرك الفحص (008) والطلب المحذوف (011) وعدّاد الربط (013) والمشتركين القدامى (014). بعد المواصفة
لخّصلي بالعربي شنو ينستورد ومنين، وشنو يتغيّر للأدمن والمسوّق، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §2 (SAS: no programmatic link, matching is manual; username
format), §3.1 (the marketer never sees anything about another subscriber), §3.3 (permission `reports` covers
import), §6 intro (the check runs on every source, including imported SAS subscribers), §6.1 (decision table;
imported subscribers count as «existing»; a rejected or deleted request does not), §6.3 item 4 (a return keeps the
historical username if there is one), §6.4 (the review file shows the linked previous subscription), §6.5 (link
and undo are manual, by an admin holding `link`), §7.4 (a deleted request leaves every check), §8.1 (phone
normalization), §8.2 (username), §10 item 9 (import page, `reports`), §12.2 (the SAS file: columns, update by
username, `ct_password` never read nor stored, tower code from the username with a manual mapping table for the
rest, rows without a phone, expiry shown «حسب آخر استيراد»), §13 (audit log, no card data in logs); constitution
Principles I (check against imported SAS subscribers), II (`ct_password` never read nor stored; no sensitive data in
logs), III (audit; subscribers never physically deleted), IV (historical username), VIII (tested rules), IX
(server-side authorization), X (UTC storage). `docs/features.md` holds no pending idea for this feature.

**Builds on**: 008 (the check engine and its source registry: a source with no national ID and no family number
can match on phone only), 009 (return by phone, historical username on a return), 010 (the review file, its
linked-record registry with the `expiry` field reserved for SAS, «سجل غير متوفر», the re-check after a pin), 011
(deleted requests leave every check; «سجل محذوف»), 013 (link, undo and the monthly counter count requests only and
stay manual), 014 (the import page, the preview with groups, «تخطي للكل», all-or-nothing confirmation, one hour
expiry, one confirmation at a time, audit without personal data, legacy subscribers as a source).

**Out of scope (later features)**: the admin «المشتركون» page with search and subscriber file (018); reports and
export (019); any programmatic connection to SAS (never: constitution, Additional Constraints). Marking a Sijil
request «تم الربط» from the SAS file is never done by the import: linking stays a manual admin action (§6.5).

**Governance changes this feature needs** (approved by the owner on 2026-11-25): `docs/system.md` 1.20 — §12.2
gains: preview before saving with groups and «تخطي للكل» (same as §12.1); confirmation saves all or nothing, no
undo; re-upload updates the existing rows by username and adds new ones; a row missing from a new file stays, still
counts, and is marked «غير موجود في آخر ملف»; both the phone column and the phone inside the username count in the
check; the tower mapping chosen by the admin is remembered for the next imports; a SAS row whose username equals a
Sijil request's username is the same subscriber, not a conflict; the import never changes a request, a link or a
counter; the audit entry carries no usernames and no phones (a SAS username contains the phone). `docs/features.md`
gains the idea of a SAS hint in «بانتظار الربط». No constitution change.

## Clarifications

### Session 2026-11-25

- Q: Which phone does a SAS subscriber hold for the check when the username's phone differs from the phone column
  or the column is empty? → A: Both: the phone column and the phone inside the username each count (FR-012).
- Q: What happens to a stored SAS subscriber missing from a new file? → A: It stays, still counts in the check, and
  is marked «غير موجود في آخر ملف» for the admin (FR-022).
- Q: Should «بانتظار الربط» show a «موجود في SAS» hint? → A: No, not in this feature; the idea goes to
  `docs/features.md` (FR-023).
- The proposed §12.2 changes were approved as written.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The admin imports the SAS file after a preview (Priority: P1)

An admin with the `reports` permission (or the main admin) opens «الاستيراد» and chooses «مشتركو SAS». They upload
the subscribers file exported from SAS. The `ct_password` column is dropped the moment the file is read: it never
reaches the preview, the storage or the logs. Nothing is saved yet. The page shows a preview: the row count, how
many rows are new, how many update an existing SAS subscriber, how many are unchanged, and every row that needs a
look, grouped by problem. Above the groups, a table lists every username prefix whose tower could not be found, with
the number of rows behind it, for the admin to map to a tower. The admin maps the prefixes, resolves each flagged
row (row by row, or with «تخطي للكل» per group), then presses «تأكيد الاستيراد». The rows are saved, and a summary
shows how many were added, updated, unchanged and skipped.

**Why this priority**: Until the SAS subscribers are in Sijil, the anti-fraud check (Principle I) misses every
subscriber registered in SAS before Sijil: a marketer could register one of them as new with the same phone.

**Independent Test**: Upload a synthetic SAS file with known problems (unknown prefixes, invalid phones, repeated
usernames, a phone held by a pending Sijil request, a `ct_password` column with values); confirm the preview lists
exactly those rows under the right groups, that the password values appear nowhere, that nothing is saved before
confirmation, and that after confirmation the counts in the summary match the rows.

**Acceptance Scenarios**:

1. **Given** a file with the 12 documented columns, **When** the admin uploads it, **Then** a preview appears and
   no SAS subscriber is saved or changed.
2. **Given** a file with a `ct_password` column holding values, **When** it is uploaded, previewed and confirmed,
   **Then** no screen, stored record, temporary preview, audit entry or log line contains any of those values.
3. **Given** a file missing `username` or `phone`, or not a readable sheet, **When** it is uploaded, **Then** the
   page names the problem in Arabic and offers no confirmation.
4. **Given** usernames such as `KZF06-07801234567`, `RBD-01S-07801234567` and `SMR-01-07801234567`, **When** the
   preview shows, **Then** their towers are found by the known rules (tower codes KZF06, RBD01S, SMR01 when those
   towers exist in the settings) and they are not flagged.
5. **Given** usernames whose prefix matches no tower, **When** the preview shows, **Then** each distinct prefix
   appears once in the mapping table with its row count, and the admin picks a tower for it or «بلا برج».
6. **Given** a row whose phone fails §8.1, or is empty, **When** the preview shows, **Then** it is counted under
   «بلا هاتف صالح»; if imported, it is saved without a phone and takes no part in the phone check.
7. **Given** a row whose phone is held by a pending, accepted or linked Sijil request with a different username,
   **When** the preview shows, **Then** it appears under «الهاتف في طلب سِجلّ» with the request number, and the
   admin chooses «استيراد» or «تخطي».
8. **Given** a group of flagged rows, **When** the admin presses «تخطي للكل», **Then** every row of the group is
   set to «تخطي», and the admin can still change any of them afterwards.
9. **Given** every flagged row has a choice and every unknown prefix has a mapping, **When** the admin confirms,
   **Then** the import is saved as one step (all of it or nothing), audited, and the summary appears.
10. **Given** a flagged row without a choice or a prefix without a mapping, **When** the admin tries to confirm,
    **Then** confirmation is refused and the page points to what is still waiting.

---

### User Story 2 - The check engine knows the SAS subscribers (Priority: P1)

After the import, every marketer check (the early warning while typing, and the authoritative check at submission)
also looks at the SAS subscribers, across all regions and towers. A SAS subscriber has no national ID and no family
number, so it can match on phone only: a match is case 1 of §6.1.

**Why this priority**: This is the reason for the import.

**Independent Test**: Import a synthetic SAS row, then start drafts that reuse its phone, a new phone, and a return
by its phone; confirm each gets the §6.1 outcome and that nothing about the SAS row reaches the marketer.

**Acceptance Scenarios**:

1. **Given** a SAS subscriber with phone P, **When** a marketer enters P on a new draft, **Then** case 1 applies:
   «المشترك موجود سابقاً، هل يود العودة للخدمة؟» with «طلب العودة للخدمة» and «الاتصال بالإدارة», and at
   submission a new request with P is refused and the draft stays.
2. **Given** a SAS subscriber with phone P, **When** a marketer submits a return by phone P and the admin accepts
   it, **Then** the request keeps the SAS username as its historical username (§6.3 item 4).
3. **Given** SAS subscribers only, **When** a marketer submits a new request whose phone no source holds, **Then**
   nothing about the SAS data changes the outcome (a SAS record never gives case 2, 2ب or 3).
4. **Given** any of the above, **When** the marketer sees the result, **Then** no name, phone, username, tower,
   expiry or any other field of the SAS subscriber is shown to them (§3.1).
5. **Given** a SAS row the admin skipped, **When** a marketer uses its phone, **Then** it does not match (a skipped
   row is not saved), unless another source holds the phone.
6. **Given** a re-import that changes the phone of an existing SAS subscriber from P1 to P2, **When** a marketer
   then uses P1 or P2, **Then** P2 matches and P1 no longer matches through that subscriber.
7. **Given** a pending Sijil request whose numbers the admin pins (010), **When** the re-check runs after the
   import, **Then** it sees the SAS subscribers too, under the existing 010 warning rules.

---

### User Story 3 - The admin sees the SAS record in the review file (Priority: P2)

When a pending request is linked to a SAS subscriber (a return by phone), the review admin sees that record in the
request file like any other linked previous subscription: source «مشترك SAS», username, full name (firstname +
lastname), phone, tower «اسم البرج (رمز البرج)» or «بلا برج», SAS creation date as registration date, the expiry
with «حسب آخر استيراد» and that import's date, last online, and the SAS package (group).

**Why this priority**: The admin decides a return by comparing with the previous subscription, and the extra-month
rule (§6.4: 15 days or more remaining) needs the expiry.

**Independent Test**: Create a pending return matching a synthetic SAS row; open the review file as a review admin
and confirm the fields; open the same as a marketer and confirm nothing is visible.

**Acceptance Scenarios**:

1. **Given** a pending request linked to a SAS subscriber, **When** a review admin opens it, **Then** the linked
   record shows with the source «مشترك SAS» and the fields above, never a request number and never card images
   (SAS holds none).
2. **Given** the expiry is in the past, **When** it is shown, **Then** it reads as expired, still «حسب آخر
   استيراد».
3. **Given** a later re-import changed that subscriber's expiry, **When** the file is opened again, **Then** it
   shows the new expiry and the new import date.

---

### User Story 4 - The SAS import stays out of requests, links and counters (Priority: P2)

SAS subscribers are subscribers, not requests. Importing them never changes a request, its status, its link, the
monthly counter or any notification, even when the SAS file contains the username of an approved Sijil request.

**Independent Test**: With approved, linked, unlinked, rejected and deleted synthetic requests in place, import a
SAS file that contains some of their usernames; compare marketer home, admin home, «بانتظار الربط», «المربوطة
مؤخراً», «طلبات بالانتظار», notifications and the monthly counter with their values before the import.

**Acceptance Scenarios**:

1. **Given** an approved request whose username is in the SAS file, **When** the import is confirmed, **Then** the
   request stays «مقبول (بانتظار الربط)»; only the admin's «تم الربط» links it (§6.5).
2. **Given** an import of N rows, **When** it is saved, **Then** the admin home numbers, «بانتظار الربط»,
   «طلبات بالانتظار», every marketer counter and «و M بلا عمولة» are unchanged, and no notification is sent.
3. **Given** a SAS row whose username equals a Sijil request's username, **When** the preview shows, **Then** it is
   counted as «نفس اليوزر في سِجلّ» (the same subscriber) and imported without asking; it is not a conflict.
4. **Given** a SAS row whose phone is held only by a rejected or deleted Sijil request, **When** the preview shows,
   **Then** it is not flagged (§6.1, §7.4).
5. **Given** a SAS subscriber, **When** an admin looks for a «حذف» action on it, **Then** there is none: §7.4
   applies to requests only, and subscribers are never physically deleted (Principle III).

---

### User Story 5 - The admin re-imports the SAS file whenever needed (Priority: P2)

SAS changes every day. The admin uploads a fresh export when they want the check and the expiries up to date. Rows
are matched to the stored SAS subscribers by username: new usernames are added, known ones are updated with the
file's values, identical ones are left as they are. The tower mappings chosen last time are applied again without
asking.

**Independent Test**: Import a synthetic file, then upload a second one that adds a row, changes the phone and
expiry of another, leaves one identical and omits one; confirm the preview counts and the saved result.

**Acceptance Scenarios**:

1. **Given** a stored SAS subscriber, **When** a new file has the same username (compared upper-case) with other
   values, **Then** the preview counts it under «سيُحدَّث» and confirmation updates it.
2. **Given** a prefix mapped to a tower in a previous import, **When** a new file uses it, **Then** it is mapped
   the same way and does not appear in the mapping table; the admin may still change it there.
3. **Given** a stored SAS subscriber whose username is not in the new file, **When** the import is confirmed,
   **Then** it stays unchanged, still counts in the check, and is marked «غير موجود في آخر ملف»; a later file that
   holds it again clears the mark.

---

### Edge Cases

- **The `ct_password` column**: dropped at reading, whatever its header case or position; if the file has no such
  column, nothing changes. A file whose only problem is that column's values is still imported.
- **The same username twice in the file** (compared upper-case): flagged «يوزر مكرر في الملف»; only one of them can
  be imported, and the admin picks which one or skips both.
- **An empty username**: flagged «بلا يوزر» and cannot be imported (the username is the key of §12.2).
- **The same phone on several SAS rows** (different usernames): informational, not flagged; every imported row
  counts, and each gives case 1 alone.
- **A phone held by a legacy subscriber (014)**: informational only; both sources keep counting.
- **A SAS row whose phone is held by a pending, accepted or linked Sijil request with another username**: flagged
  (US1 scenario 7), because SAS and Sijil disagree on who owns the phone.
- **The phone in the username differs from the phone column**, or the phone column is empty while the username holds
  a phone: both phones count in the check (FR-012), and the review file shows both when they differ.
- **Hidden direction marks, spaces, Arabic or Indic digits** in phones: §8.1. Usernames are kept as written and
  compared upper-case.
- **Names with odd characters**: kept as written after trimming and collapsing spaces; the 5.1 name rules apply only
  to new forms. An empty name is allowed.
- **Unreadable dates** in `expiration`, `created_at` or `last_online`: the field is saved empty, the row is still
  imported, and the preview counts such rows.
- **A prefix mapped to a tower that the admin later stops or renames** in the settings: the SAS record keeps
  pointing to the tower; the review file shows the current tower name.
- **A large file** (thousands of rows): the preview groups and counts; it lists flagged rows only, not every ready
  row.
- **Concurrent imports**, of SAS or legacy, by two admins: only one confirmation runs at a time; the second waits,
  is re-checked against what the first saved, and is refused with «تغيّرت البيانات منذ المعاينة» if any of its rows
  now needs a new choice.
- **A preview left unconfirmed**: it expires after one hour without saving anything.
- **A failed save** (server error mid-way): nothing from that import is saved or updated.

## Requirements *(mandatory)*

### Functional Requirements

**Upload and preview**

- **FR-001**: The «الاستيراد» page MUST offer «مشتركو SAS» only to the main admin and admins holding `reports`; the
  server MUST refuse every SAS import action to anyone else.
- **FR-002**: The system MUST accept the SAS export as a spreadsheet (`.xlsx`) or a comma-separated file (`.csv`,
  UTF-8), recognize the columns of §12.2 by their headers, and refuse a file that lacks `username` or `phone`, naming
  the missing column.
- **FR-003**: The `ct_password` column MUST be discarded when the file is read, before anything is kept: it MUST NOT
  be stored, kept in the preview, shown, logged or written to the audit.
- **FR-004**: Uploading MUST NOT save or change any SAS subscriber or tower mapping; it MUST produce a preview with
  the total, the counts of new, updated, unchanged and informational rows («بلا هاتف صالح», «نفس اليوزر في سِجلّ»,
  «تاريخ غير مقروء», «غير موجود في آخر ملف»), the table of unknown prefixes, and every flagged row grouped by problem: username empty,
  username repeated in the file, phone held by a pending, accepted or linked Sijil request under another username
  (with its request number).
- **FR-005**: The tower code MUST be taken from the username by the known rules: the part before the final phone
  (`07` and 9 digits), with its dashes removed and upper-cased, equal to the code of a tower in the settings (for
  example `KZF06-…` → KZF06, `RBD-01S-…` → RBD01S, `SMR-01-…` → SMR01). A prefix that gives no tower MUST appear in
  the mapping table, once per distinct prefix with its row count, for the admin to map to an existing tower or to
  «بلا برج».
- **FR-006**: For each flagged row the admin MUST choose «استيراد» or «تخطي»; each group MUST offer «تخطي للكل»,
  which sets «تخطي» on every row of the group, and the admin MUST still be able to change any of those rows
  afterwards.
- **FR-007**: Confirmation MUST be refused while any flagged row has no choice or any unknown prefix has no mapping.

**Saving**

- **FR-008**: On confirmation the system MUST save, as a single all-or-nothing step: one SAS subscriber per new
  chosen row and the new values on each updated row, each holding the SAS id, the username as written, firstname,
  lastname and full name, the phone normalized by §8.1 (or none), the tower (or none), expiration, created_at,
  last_online, group_name, parent_name, notes, and the import it last came from; and the tower mappings chosen in the
  preview, to be reused by later imports.
- **FR-009**: The import MUST be written to the audit log: who, when, file name, rows added, updated, unchanged,
  skipped, rows without a valid phone, and prefixes mapped. The audit entry and the application logs MUST NOT carry
  usernames, phones, names, or the `ct_password` values (a SAS username contains the phone).
- **FR-010**: After the save, the page MUST show a summary with the counts; skipped rows MUST be identified by their
  SAS id and row number, not by username or phone.

**Check engine**

- **FR-011**: SAS subscribers MUST be a source of the check engine (§6, Principle I) for the early check, the
  authoritative check at submission, and the 010 re-check after a pin, across all regions and towers, matching on
  phone (§8.1) only. They MUST never match on national ID or family number, and MUST never block a return as
  «pending».
- **FR-012**: A SAS subscriber MUST hold for the check both the phone of the phone column and the phone inside its
  username (the final `07` and 9 digits), each normalized by §8.1, when they differ or when one of them is missing;
  a match on either gives case 1. The review file shows both when they differ.
- **FR-013**: A return accepted against a SAS target MUST keep the SAS username as its historical username (§6.3
  item 4); when the target set holds both a Sijil request and a SAS subscriber with a username, the newest Sijil
  request's username wins, as in 009.
- **FR-014**: Nothing about a SAS record MUST reach a marketer, in any response or message (§3.1).

**Review file**

- **FR-015**: The review file MUST resolve a linked SAS record and show it to review admins with: source «مشترك
  SAS», username, full name, phone, tower «اسم البرج (رمز البرج)» or «بلا برج», SAS creation date, expiry with
  «حسب آخر استيراد» and that import's date, last online, and group_name. Notes and parent_name are stored but not
  shown in this feature.

**Isolation from requests**

- **FR-016**: The import MUST NOT change any request: not its status, username, link, link history, decision or
  commission answer, even when the file holds the request's username.
- **FR-017**: SAS subscribers MUST NOT appear in, or change, any request list or count: «طلبات بالانتظار»،
  «بانتظار الربط»، «المربوطة مؤخراً», admin home numbers, marketer lists and counters, «و M بلا عمولة»,
  commissions, notifications.
- **FR-018**: A SAS row whose username equals (upper-case) the username of a Sijil request MUST be imported without
  a choice and counted «نفس اليوزر في سِجلّ»; rejected and deleted requests MUST never flag a SAS row.
- **FR-019**: SAS subscribers MUST NOT be physically deleted; there is no delete action on them.
- **FR-020**: SAS subscribers MUST NOT be searchable by the marketer nor openable by «فتح طلب برقمه».

**Re-import**

- **FR-021**: Uploading the file again MUST match rows to stored SAS subscribers by username (upper-case): new
  usernames are added, known ones with any different value are updated, identical ones are left unchanged.
- **FR-022**: A stored SAS subscriber whose username is not in the new file MUST be kept unchanged, MUST still count
  in the check, and MUST be marked «غير موجود في آخر ملف» (with the date of the import that first missed it); the
  preview counts such rows. The mark is cleared when a later file holds the username again.
- **FR-023**: This feature MUST leave «بانتظار الربط» and «المربوطة مؤخراً» unchanged: no SAS hint is shown there.
  The idea of a hint «موجود في SAS حسب آخر استيراد» is recorded in `docs/features.md` for later.

### Key Entities

- **SAS subscriber**: one subscriber from the SAS file, keyed by username. SAS id, username as written, firstname,
  lastname, full name, phone (normalized or none), the phone inside the username, tower (or none), the mark «غير
  موجود في آخر ملف» with its date, expiration, created_at, last_online, group_name,
  parent_name, notes, the import that last wrote it. No national ID, no family number, no images, no marketer, never
  any password.
- **Tower mapping**: a username prefix that the rules could not resolve, and the tower (or «بلا برج») the admin
  chose for it; reused by later imports.
- **SAS import**: one confirmed import: who, when, file name, counts (added, updated, unchanged, skipped, without
  phone), and the per-row choices for flagged rows.
- **Import preview**: a temporary, unsaved reading of an uploaded file (without `ct_password`) with its flagged rows
  and unknown prefixes; it expires after one hour if not confirmed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every row of the SAS file ends either added, updated, unchanged or knowingly skipped, and the summary
  counts add up to the row count of the file.
- **SC-002**: After the import, 100% of new requests that reuse a phone of an imported SAS subscriber are stopped as
  case 1.
- **SC-003**: Zero `ct_password` values exist anywhere in Sijil after any upload, preview or import, checked by
  searching storage, logs and audit for the synthetic values.
- **SC-004**: The admin finishes a re-import, from upload to summary, in under 10 minutes for a file of 10,000 rows
  when the prefixes are already mapped.
- **SC-005**: No marketer screen, response or message ever shows any field of a SAS subscriber.
- **SC-006**: Admin home numbers, marketer counters, «بانتظار الربط» and the status of every request are identical
  before and after an import.
- **SC-007**: A failed import leaves the stored SAS subscribers and tower mappings exactly as they were.

## Assumptions

- The file is the SAS subscribers export with the 12 columns of §12.2; the admin downloads it from SAS and uploads
  it; Sijil never connects to SAS.
- The SAS file may hold several thousand rows (assumed up to about 20,000); the preview lists only flagged rows and
  counts the rest.
- An expired SAS subscriber (expiry in the past) still counts as «existing»: they are a former subscriber, and the
  right path for them is a return (case 1).
- Usernames are compared upper-case, as in the 013 link search; the value as written is what is stored and shown.
- The tower is information for the admin only; it plays no part in the check (the check runs across all towers).
- A preview stays valid for one hour, and only one confirmation (SAS or legacy) runs at a time, as in 014.
- `notes` and `parent_name` are kept for later features (018) and are not shown now.
- Tests and examples use only synthetic rows (CLAUDE.md, constitution); the real SAS file is imported only on the
  server.
- SAS records are read-only in this feature except through re-import; a subscriber list with search comes with 018.
