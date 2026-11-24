# Feature Specification: Subscriber Deletion (Erase a Request's Personal Data)

**Feature Branch**: `011-subscriber-deletion`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "فيزة «حذف مشترك» حسب docs/features.md وقراراتي السابقة: الحذف بس للطلبات اللي
بالانتظار والمرفوضة، تنمسح البيانات الشخصية والصور ويبقى سطر فارغ حتى العمولة والتقارير تبقى صحيحة، صلاحية «حذف»
يعطيها الأدمن الرئيسي، تأكيد بكتابة رقم الطلب، و«سبب الحذف» من قائمة (طلب مكرر، طلب تجريبي، خطأ إدخال، سبب آخر).
بسجل العمليات سطر بدون بيانات شخصية. بعد المواصفة لخّصلي بالعربي شنو الأسئلة اللي تحتاج قراري."

**Source of the owner's decisions**: `docs/features.md` «حذف مشترك (بعد الفيزة 010)», decisions of
2026-11-23, plus the reason list given in the input above.

**System document references**: `docs/system.md` §3.2 (main admin has every permission), §3.3 (admin
permissions), §5 (draft deletion as the existing precedent), §6.1 (decision table: the check runs against
all Sijil requests), §6.4 (request file, pin rows, rejection), §7.2 (statuses), §7.3 (request number),
§8.3 (OTP limit per phone), §10 items 1, 2, 7, 11 (admin home, pending list, admins and permissions, audit
log), §13 (image storage), §15 (backups); constitution Principles II (identity documents), III (permanent
audit trail, no physical deletion of requests), IV (recorded values immutable), IX (server-side
authorization).

**Builds on**: 002 (admin permissions), 007 (OTP challenges per phone), 008 (requests, reasons, matched
records), 009 (return requests with a stored historical username), 010 (admin request file, pins,
rejection, admin home counts).

**Governance changes this feature needs** (approved by the owner on 2026-11-24):

- **Constitution, Principle III** — today: "Requests and subscribers MUST NOT be physically deleted; they may
  only be deactivated." Amendment (MINOR, 1.2.1 → 1.3.0): a request in status pending review or rejected
  MAY have its personal data and card images erased by an admin holding `delete`; the request row stays
  with its non-personal fields, and the erasure is audited without personal data. Entries in the audit log
  are never altered; an entry that pointed to an erased pin row then shows «سجل محذوف».
- **`docs/system.md`** — new version 1.15: a new permission `delete` in §3.3, a new subsection for
  subscriber deletion, the deleted mark in §7.2, the box «فتح طلب برقمه» in §10, the audit line in §13, the
  backup note in §15, and the feature plan in §16 renumbered (this feature becomes 011, the later ones shift
  by one).

**Out of scope**: deleting accepted or linked requests (never allowed); deleting imported legacy or SAS
subscribers (014, 015); deleting drafts (already done by 005); purging the data from existing backups
(they expire on their own schedule, see Assumptions); privacy requests from subscribers (not the goal of
this feature); the subscriber search and file (018); reports and export (019) beyond the rule that a
deleted request shows as an empty row.

## Clarifications

### Session 2026-11-24

- Q: Does «سبب آخر» need a free text? → A: No. It is saved as «سبب آخر» only, so no free text can carry
  personal data.
- Q: What does the marketer see for a deleted request? → A: It stays in their list marked «محذوف», with the
  reason, the request number, the tower and the date only.
- Q: How does an admin reach a rejected request to delete it? → A: A box «فتح طلب برقمه» that opens any
  request file by its number.
- Q: Is the reviewer's rejection note kept on a deleted request? → A: No. The rejection reason's name stays;
  the written note is erased from the request. The copy inside the earlier «رفض» audit line stays, since
  audit lines are never altered (Principle III); only the main admin sees the audit log.
- Q: Governance? → A: The owner approves the constitution amendment to 1.3.0, `docs/system.md` 1.15, the
  renumbering of the feature plan (§16), and that deleting needs both `review` and `delete`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delete a duplicate or test request from its file (Priority: P1)

An admin who holds `delete` opens the file of a request that is pending review or rejected (for example a
request the marketer submitted twice, or a test request made during training). The file shows a «حذف»
button. The admin presses it, picks a reason from the list «طلب مكرر»، «طلب تجريبي»، «خطأ إدخال»، «سبب آخر»,
and types the request number to confirm. The system erases the subscriber's personal data and card images,
keeps an empty row with the request's number, marketer, status, dates, tower, plan and the two prices, and
writes one line «حذف مشترك» to the audit log. The file now shows «تم حذف بيانات هذا الطلب» with who deleted
it, when, and the reason.

**Why this priority**: This is the whole purpose of the feature: correcting mistakes (duplicate or test
requests) without leaving real people's data in the system and without breaking counts or history.

**Independent Test**: As the main admin, submit a test request that ends pending review, open its file,
delete it with reason «طلب تجريبي» typing its number, then confirm the personal fields and images are gone
from every screen, the image files are gone from storage, the row remains with its number, and the audit
log holds one deletion line with no personal data.

**Acceptance Scenarios**:

1. **Given** a pending review request and an admin with `delete`, **When** the admin presses «حذف», picks
   «طلب مكرر» and types the request number exactly, **Then** the personal data and images are erased, the
   row remains with its kept fields, the request leaves the pending list, and the file shows the deletion
   with who, when and the reason.
2. **Given** a rejected request opened through «فتح طلب برقمه», **When** an admin with `delete` deletes it,
   **Then** the same erasure happens; the rejection decision (who, when, the reason's name) stays on the row
   and the reviewer's written note is erased.
3. **Given** the confirmation dialog, **When** the typed number does not match the request number, **Then**
   the final delete button stays disabled and nothing is erased.
4. **Given** the confirmation dialog, **When** no reason is selected, **Then** the final delete button stays
   disabled.
5. **Given** a deleted request, **When** the main admin opens the audit log, **Then** there is one line
   «حذف مشترك» with the request number, who deleted it, when, the status at deletion and the reason, and
   no name, phone, national ID, family number, address, location or username.
6. **Given** a deleted request, **When** anyone tries to open its card images by their old links, **Then**
   the image is not found.
7. **Given** a deleted request, **When** an admin opens its file again, **Then** no «حذف» button is shown
   (deletion happens once and cannot be undone).

---

### User Story 2 - The phone and the numbers become free again (Priority: P1)

After a duplicate or wrong request is deleted, the marketer must be able to file the correct request for the
same person and the same phone without being blocked by the deleted one.

**Why this priority**: A duplicate or a wrongly entered request would otherwise keep blocking the real
request (the phone is "used", the national ID "exists"). Freeing them is the practical result of deletion.

**Independent Test**: Delete a pending request, then start a new draft with the same phone, national ID and
family number; the phone is accepted, OTP can be requested at once, and the decision check finds no match
against the deleted request.

**Acceptance Scenarios**:

1. **Given** a deleted request whose phone was 07801234567, **When** a marketer enters that phone in a new
   draft, **Then** the phone is not reported as used because of the deleted request.
2. **Given** a deleted request, **When** a new request is submitted with the same national ID and family
   number, **Then** the decision check does not match it against the deleted request.
3. **Given** a phone that had reached the limit of 5 codes per hour on the deleted request, **When** the
   request is deleted, **Then** the OTP codes tied to that phone are deleted and a new code can be requested
   for that phone at once.
4. **Given** a deleted request, **When** a new request is submitted, **Then** it gets the next new request
   number; the deleted request's number is never reused.

---

### User Story 3 - The main admin grants the «حذف» permission (Priority: P2)

The main admin can give or remove the permission «حذف» (`delete`) for any added admin from the admins and
permissions page, like the other permissions. The main admin always holds it.

**Why this priority**: Deletion is sensitive; only the main admin and admins they trust should be able to do
it. The main admin can already delete without this story, so it comes second.

**Independent Test**: As the main admin, give `delete` to an added admin who has `review`; that admin sees
«حذف» on a pending request file. Remove it; the button disappears and a direct delete attempt is refused by
the server.

**Acceptance Scenarios**:

1. **Given** the admins and permissions page, **When** the main admin opens an added admin, **Then** a
   switch «حذف» appears with the other permissions, off by default.
2. **Given** an admin without `delete`, **When** they open a request file, **Then** no «حذف» button is shown,
   and a direct deletion attempt is refused by the server.
3. **Given** the main admin, **When** they open the permissions of their own account, **Then** «حذف» is
   always on and cannot be turned off.
4. **Given** a change to an admin's `delete` permission, **When** it is saved, **Then** it is audited like
   any other permission change.

---

### User Story 4 - Other requests and screens show «سجل محذوف» (Priority: P2)

Other requests may point to the deleted one: a reason «اشتراك إضافي» (family exists), «تعارض بالأرقام» or
«إعادة للخدمة» whose matched record is the deleted request. These keep their reasons (reasons are never
deleted), and the matched record shows «سجل محذوف» with its request number instead of its data.

**Why this priority**: Without it, a reviewer would see broken or empty data on another request; with it, the
reviewer knows the match was removed and decides with that knowledge.

**Independent Test**: Create a pending request B whose reason matches request A, delete A, open B's file:
the reason is still listed and the linked record shows «سجل محذوف (#T3C-…)», with no name, phone, numbers or
images of A.

**Acceptance Scenarios**:

1. **Given** a pending request B with a reason whose matched record is deleted request A, **When** an admin
   opens B, **Then** the reason stays and the linked record shows «سجل محذوف» with A's request number only.
2. **Given** the same case, **When** the admin accepts or rejects B, **Then** the decision works as before;
   deleting A does not change B's type or reasons by itself.
3. **Given** an audit line that referred to a pin row of the deleted request, **When** the main admin opens
   the audit log, **Then** the line is still shown unchanged and its link shows «سجل محذوف».
4. **Given** the admin home counts, **When** a pending request is deleted, **Then** the current «بالانتظار»
   count drops by one, and today's and this month's «مرفوعة» and «مرفوضة» counts do not change.

---

### User Story 5 - The marketer sees that a request was deleted (Priority: P3)

The marketer who submitted the deleted request sees what happened to it in their requests, without seeing
any personal data that was erased.

**Why this priority**: The marketer needs to know the request was removed on purpose (and why) so they do not
chase it, but this does not block the admin-side correction.

**Independent Test**: Delete a marketer's pending request, sign in as that marketer and open their requests:
the request appears marked «محذوف» with its reason, number, tower and date, and no name or phone.

**Acceptance Scenarios**:

1. **Given** a deleted request, **When** its marketer opens their requests, **Then** it stays in the list
   marked «محذوف» with the reason, the request number, the tower and the date, and none of the erased data.
2. **Given** a deleted request, **When** its marketer opens it, **Then** they see the same fields only and no
   copy or share buttons.

---

### User Story 6 - Open any request by its number (Priority: P2)

An admin with `review` types a request number in the box «فتح طلب برقمه» and the request file opens,
whatever its status. This is how a rejected request is reached for deletion until the subscriber search
(018) exists.

**Why this priority**: Without it, a rejected request cannot be reached from any admin screen, so it cannot
be deleted.

**Independent Test**: As an admin with `review`, type the number of a rejected request (with or without
«T3C-», Western or Arabic-Indic digits): its file opens. Type a number that does not exist: «لا يوجد طلب بهذا
الرقم».

**Acceptance Scenarios**:

1. **Given** an admin with `review`, **When** they type an existing request number, **Then** that request's
   file opens, in any status (pending review, approved, rejected, linked, deleted).
2. **Given** a number that matches no submitted request, **When** the admin opens it, **Then** they see «لا
   يوجد طلب بهذا الرقم» and nothing else.
3. **Given** an admin without `review`, **Then** the box is not shown and the server refuses a direct
   attempt the same way as a missing request.

---

### Edge Cases

- **Accepted or linked request**: no «حذف» button; a direct attempt is refused by the server with a clear
  message «لا يمكن حذف طلب مقبول أو مربوط».
- **Draft**: drafts are not requests; this feature does not touch draft deletion (§5).
- **Two admins at once**: one deletes while the other is reviewing or deleting the same request. The first
  action wins. The second sees «تم حذف هذا الطلب مسبقاً» (or, if the request was accepted first, deletion is
  refused because it is no longer pending).
- **Accept or reject arrives after deletion**: refused; a deleted request cannot be decided.
- **Pin after deletion**: refused; a deleted request has nothing to pin.
- **Typed number format**: the confirmation accepts the number with or without the «T3C-» prefix and with
  Arabic-Indic digits (for example «T3C-1005», «1005», «١٠٠٥»); any other value keeps the button disabled.
- **Image files already missing on disk**: deletion still completes; the missing file is noted in the
  application log (by image id only, no personal data).
- **Erasure fails half-way** (for example storage error): the request must not end half-erased; either the
  whole erasure completes or nothing changes and the admin sees an error and can retry. Image files are
  removed only after the data erasure is saved, and a file left behind by a failure is removed by the
  regular uploads clean-up, since no record points to it any more.
- **Return request**: its username is the historical one taken from the target record and contains a phone,
  so it is erased with the other fields.
- **Rejection note («سبب آخر» text written by the reviewer)**: erased from the request; the reason's name
  stays. The copy inside the earlier «رفض» audit line is not altered.
- **Marketer archived**: deletion still works; the row keeps the marketer's name as all their requests do.

## Requirements *(mandatory)*

### Functional Requirements

**Permission and access**

- **FR-001**: The system MUST add a new admin permission «حذف» (`delete`). The main admin always holds it and
  it cannot be removed from them; for added admins it is off by default and the main admin turns it on or off
  from the admins and permissions page.
- **FR-002**: The «حذف» button MUST appear only on the admin request file, only to an admin who can open that
  file and holds `delete`, and only when the request is pending review or rejected and not yet deleted.
- **FR-003**: The server MUST refuse a deletion from anyone without `delete`, for a request in any other
  status (draft, approved, linked), and for a request already deleted, whatever the screen showed.

**Confirmation and reason**

- **FR-004**: Pressing «حذف» MUST open a confirmation that states what will happen («ستُمسح البيانات الشخصية
  وصور البطاقة نهائياً ولا يمكن التراجع») and asks for a reason and the request number.
- **FR-005**: The reason MUST be chosen from a fixed list: «طلب مكرر»، «طلب تجريبي»، «خطأ إدخال»، «سبب آخر».
  No reason takes a free text; «سبب آخر» is saved as is.
- **FR-006**: The final delete button MUST stay disabled until a reason is chosen and the typed request number
  matches the request (with or without the «T3C-» prefix, Western or Arabic-Indic digits). The server MUST
  check the number again and refuse a mismatch.

**What is erased**

- **FR-007**: Deletion MUST erase from the request: all name fields (subscriber and mother, and the full
  name), national ID (stored, typed and submitted values), family number (stored, submitted values and its
  comparison key), birth date, card issue and expiry dates, birth place, issuing authority, all other card
  fields, the national-ID check result, all card readings, phone, username, address, nearest landmark, and
  location (coordinates, source, accuracy), and the reviewer's written rejection note.
- **FR-008**: Deletion MUST erase the request's number pins (the before and after values), and from its
  reasons any stored personal detail if one exists (today reasons hold only field names and the return basis), keeping
  each reason's type and the reference to the matched record.
- **FR-009**: Deletion MUST remove every card image file of the request from storage, and its image records
  MUST no longer lead to any file.
- **FR-010**: Deletion MUST delete the OTP codes tied to the request's phone, except the code of a draft
  being verified right now, so the per-phone limit (5 codes per hour) starts again for that phone
  (system.md v1.16 §7.4).

**What is kept**

- **FR-011**: The row MUST keep: request number, marketer, type, status at deletion, all recorded dates and
  times (OTP verified, submitted, decision), area, tower code and name, plan name, trial price and second
  price, and the rejection decision when there is one (who, when, the reason's name).
- **FR-012**: The row MUST carry a deletion mark: deleted at, deleted by, and the reason.
- **FR-013**: A deleted request's number MUST never be reused.

**Effects on the rest of the system**

- **FR-014**: A deleted request MUST NOT appear in the pending list, MUST NOT be accepted, rejected or pinned,
  and MUST NOT take part in any check (phone used, national ID exists, family match, number conflict, return
  match).
- **FR-015**: Wherever another request points to a deleted request as a matched record, the system MUST show
  «سجل محذوف» with its request number only, to admins only; reasons on other requests stay as recorded and
  are not changed by the deletion.
- **FR-016**: The admin home «بالانتظار» count MUST exclude deleted requests; the «مرفوعة» and «مرفوضة»
  counts for any day or month MUST stay the same as before the deletion.
- **FR-017**: The opened file of a deleted request MUST show «تم حذف بيانات هذا الطلب» with who deleted it,
  when, the reason, and the kept fields only.

**Audit**

- **FR-018**: Each deletion MUST write one audit line «حذف مشترك» with: request number, who deleted it, when,
  status at deletion (before) and deleted with the reason (after), and nothing else from the request: no
  name, phone, username, national ID, family number, address, landmark, location or card data.
- **FR-019**: Existing audit lines MUST NOT be changed or removed by a deletion, including the «رفض» line that
  holds the reviewer's note. A line that links to an erased pin row shows «سجل محذوف» for that link.
- **FR-020**: The application logs MUST record the deletion by request number only, with no personal data.

**Marketer view**

- **FR-021**: The marketer who submitted the request MUST still see it in their requests, marked «محذوف»,
  with the deletion reason, the request number, the tower and the date only; no erased data and no copy or
  share buttons. It stays under the tab of its status at deletion (pending or rejected), with the tag.

**Reaching the request**

- **FR-022**: The admin panel MUST offer a box «فتح طلب برقمه» to admins with `review`. It opens the file of
  the submitted request with that number in any status, accepts the number with or without «T3C-» and with
  Western or Arabic-Indic digits, and shows «لا يوجد طلب بهذا الرقم» when none matches. The server refuses
  callers without `review` the same way as a missing request.
- **FR-023**: Deleting needs both `review` (to open the file) and `delete`. The main admin holds both.

### Key Entities

- **Request (deleted)**: the same request row, now holding only its non-personal fields (FR-011) plus the
  deletion mark (deleted at, deleted by, reason). Its status stays
  the status it had when it was deleted.
- **Deletion reason**: a fixed list of four values: duplicate request (طلب مكرر), test request (طلب تجريبي),
  entry error (خطأ إدخال), other (سبب آخر).
- **Admin permission `delete`**: a new switch beside `review`, `link`, `settings`, `marketers`, `reports`,
  `commissions`.
- **Audit line «حذف مشترك»**: who, when, the request number, status before, the deletion and its reason after;
  no personal data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a deletion, none of the erased fields (FR-007, FR-008) can be found for that request on
  any screen, in any response the system sends, or in the database outside existing backups: 0 fields left.
  The one exception is the reviewer's rejection note inside the earlier «رفض» audit line, which stays
  unchanged by the owner's decision (FR-019).
- **SC-002**: After a deletion, 0 card image files of that request remain in storage.
- **SC-003**: Right after deleting a duplicate, the marketer can start, verify and submit the correct request
  for the same phone and the same person in one attempt, without being blocked by the deleted one.
- **SC-004**: The admin home counts «مرفوعة» and «مرفوضة» for today and this month are identical before and
  after any deletion; «بالانتظار» drops by exactly one when a pending request is deleted.
- **SC-005**: 100% of deletions produce exactly one audit line, and 0 audit lines from a deletion contain
  personal data.
- **SC-006**: 100% of deletion attempts on accepted or linked requests, or by an admin without `delete`, are
  refused by the server.
- **SC-007**: An admin completes a deletion from the open request file (press «حذف», choose a reason, type the
  number, confirm) in under 30 seconds.

## Assumptions

- Feature numbering: this feature is 011; the plan in `docs/system.md` §16 is renumbered so the later
  features shift by one (approved).
- Deletion is final. There is no undo and no archive of the erased data.
- The deletion mark is separate from the status: the status keeps its value at deletion (pending review or
  rejected), so history and counts by status at decision time stay correct.
- Backups keep the erased data until they expire: 30 days for nightly backups, and with no limit for weekly
  backups on the external drive. The owner knows and accepts this (`docs/features.md`).
- Image access log lines and earlier audit lines stay as they are; they hold request numbers and image ids,
  not personal data (constitution Principle II already keeps identity numbers out of the audit text).
- The rejection decision (who, when, the reason's name) is kept as an immutable decision (Principle IV); the
  reviewer's free-text note is erased from the request by the owner's decision, and its copy in the earlier
  audit line stays.
- No notification is sent to the marketer at deletion (notifications come in a later feature); FR-021 only
  covers what the marketer sees in their requests.
- Reports and export (019) will show a deleted request as an empty row with its kept fields; this feature only
  guarantees the data is in that shape.
