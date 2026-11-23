# Feature Specification: Admin Review of Pending Requests

**Feature Branch**: `010-admin-request-review`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "الفيزة 010: مراجعة الأدمن للطلبات. ارجع لـ docs/system.md (الأقسام 6 و7) ولأسباب
الانتظار اللي انحفظت بـ 008 و009 (تعديل الأرقام، اشتراك إضافي، تعارض بالأرقام، طلب العودة). بعد ما تكتب المواصفة
لخّصلي بالعربي شنو يشوف الأدمن وشنو يگدر يسوي، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §3.3 (`review` permission), §5 (draft images seen only
by owner, main admin and `review`), §6.1 (decision table, reasons, notes), §6.2 (value comparison), §6.3
(return and second subscription), §6.4 (admin review), §7.1 (request types), §7.2 (statuses and allowed
transitions), §8.2 (username), §10 item 2 (page «طلبات بالانتظار»), §13 (image access logged, no card data
in logs); constitution Principles I (server decides, all reasons recorded), II (identity documents), III
(audit), IV (decisions stored on the request), IX (server-side authorization), X (time).

**Builds on**: 008 (requests, `request_reasons` with `family_exists` and `numbers_edited`, matched
records, original card readings kept on the request, pending result screen), 009 (type `return`, reasons
`return` with basis identity/phone and `numbers_conflict`, the stored historical username of a return).

**Out of scope (later features)**: link message, copy/share of the link message, request tabs and
notifications to the marketer (011); «بانتظار الربط» and «تم الربط» (012); legacy and SAS imports (013,
014) — their records appear as linked records once imported, and the SAS expiry date with them; the
subscriber search and file (017); commission amounts (016).

**Pending reasons this feature reviews** (stored by 008 and 009):

| Reason | Arabic | Stored with | Where it comes from |
|---|---|---|---|
| `family_exists` | اشتراك إضافي (عائلة موجودة) | one row per matched record | §6.1 row 3, type `additional` |
| `numbers_edited` | تعديل الأرقام | the edited fields (national ID, family number) | §6.1 row 4 |
| `numbers_conflict` | تعارض بالأرقام | one row per conflicting record | §6.1 row 2ب |
| `return` | إعادة للخدمة | one row per target record, with basis identity or phone | §6.3, type `return` |

A request may carry more than one reason (§6.1 note).

## Clarifications

### Session 2026-11-23

- Q: After a pin, the re-check finds a match that clashes with the request type (same person on a new
  request, national-ID conflict, return target no longer matching). What happens? → A: The admin decides
  with a clear red warning; accepting despite it needs a confirmation and is written to the audit log.
  The type does not change.
- Q: Rejection reason format? → A: A fixed list plus «سبب آخر» with a required text.
- Q: Is the admin home (§10 item 1) part of 010? → A: Yes, with today's and this month's counts.
- Q: How is a number pin audited, given Principle III (before/after) and Principle II (no identity
  numbers in logs)? → A: The audit entry points to the pin record, which holds the value before and
  after. Constitution amended to v1.2.1 to say so.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the pending list and open a request (Priority: P1)

An admin with `review` opens «طلبات بالانتظار». The page lists every request in status pending review,
oldest first, with its number, type, reasons, marketer, subscriber name, tower and submission time. The
admin can filter by reason. Opening a request shows the whole file: the card data and images, location,
subscription, phone, the reasons, and every linked earlier record with why it is linked.

**Why this priority**: every pending request from 008 and 009 is stuck today; nobody can even see them.

**Independent Test**: Submit one request for each reason (family, edited numbers, conflict, return by
identity, return by phone) as a marketer. Sign in as an admin with `review`: all five are listed with the
right reason labels; filtering by «تعارض بالأرقام» shows only that one; opening each one shows its linked
record(s) with the link basis. An admin without `review` sees neither the page nor the data, even by
direct address.

**Acceptance Scenarios**:

1. **Given** pending requests exist, **When** an admin with `review` opens «طلبات بالانتظار», **Then** each
   is listed with number `#T3C-…`, type (جديد / اشتراك إضافي / إعادة للخدمة), reason labels, marketer
   name, subscriber full name, tower and submission time (Baghdad time), oldest first, with a count.
2. **Given** the list, **When** the admin picks a reason filter, **Then** only requests carrying that reason
   are shown; a request with two reasons appears under both.
3. **Given** a request is opened, **Then** the admin sees: names, national ID, family number, card dates
   and place, front and back images, location on a map with address and landmark, area/tower/category
   with the two prices fixed at submission, the verified phone and verification time, the username it
   will get, the marketer, the submission time, and the reasons.
4. **Given** a request with linked records, **Then** for each linked record the admin sees its source
   (سِجلّ، قديم، SAS), name, username, phone, tower, registration date, status, images if any, and why it
   is linked (إعادة للخدمة بالرقم الوطني والعائلي، إعادة للخدمة بالهاتف، تعارض بالأرقام، عائلة موجودة).
5. **Given** an admin without `review` (or a marketer), **When** they request the list, a request file or
   its images, **Then** the server refuses and the page is not in their menu.
6. **Given** the admin opens any card image (of the request or of a linked record), **Then** the access
   is written to the log (who, when, which image).

---

### User Story 2 - Accept or reject (Priority: P1)

The admin decides. «قبول» moves the request to accepted (waiting for link). «رفض» needs a reason and moves
it to rejected. The decision is stored on the request (who, when, reason) and the marketer sees the new
status when opening the request. For a return request, accepting asks «هل تُحتسب عمولة للمسوّق؟».

**Why this priority**: the decision is the purpose of the review; without it 008/009's pending path never
ends.

**Independent Test**: Accept a family request: status accepted, username `{tower}-{phone}`, decision
stored with the admin and time, audit entry written; the marketer's request now shows «تمت الموافقة» and
the username. Reject a conflict request with reason «صورة البطاقة غير واضحة»: the marketer sees «تم رفض
الطلب» and the reason, and the same numbers and phone can be submitted again. Accept a return: the
commission question must be answered, the answer is stored, and the username is the historical one.

**Acceptance Scenarios**:

1. **Given** a pending request, **When** the admin presses «قبول» and confirms, **Then** its status becomes
   accepted, with the admin and time stored as the approval, and the request leaves the pending list.
2. **Given** a pending return request, **When** the admin presses «قبول», **Then** the question
   «هل تُحتسب عمولة للمسوّق؟» must be answered نعم or لا before the accept goes through, and the answer is
   stored on the request. New and second-subscription requests always count, with no question.
3. **Given** a pending request, **When** the admin presses «رفض», **Then** a reason is required; without it
   nothing changes. With it the status becomes rejected and the reason, admin and time are stored.
4. **Given** a request that is no longer pending (another admin decided first), **When** an admin tries to
   accept or reject it, **Then** nothing changes and the admin sees «تم البت في هذا الطلب مسبقاً» with the
   current status.
5. **Given** an accepted request, **When** the marketer opens it, **Then** it shows «تمت الموافقة» with the
   username and «نسخ التفاصيل» / «نسخ اليوزر» (from 008). **Given** a rejected request, **Then** it shows
   «تم رفض الطلب» and the reason. Nothing about any linked record reaches the marketer.
6. **Given** any accept or reject, **Then** the audit log has the action, who, when, request number, status
   before and after, the reason (for reject) and the commission answer (for return), without card data.
7. **Given** a rejected request, **Then** its phone, national ID and family number no longer count as
   existing (§6.1 note), so a new draft with them is checked as if the rejected request did not exist.

---

### User Story 3 - Check and pin edited numbers (Priority: P2)

For a request with «تعديل الأرقام», the admin sees, for each edited field, the card image, what the card
reading gave (face and MRZ where present), and what the marketer wrote. The admin pins the correct value.
The system then checks the pinned numbers again against all records and updates the reasons and links.

**Why this priority**: edited numbers are the main way to slip a fake identity past the check; the admin
needs to compare and fix them, but accepting/rejecting (Story 2) already works without pinning.

**Independent Test**: Submit a request where the marketer changed the family number from the reading.
As admin, open it: the image, the reading and the marketer's value are side by side. Pin the reading's
value, which matches an existing family: the request gains «اشتراك إضافي» with that record linked, the
type becomes second subscription, and accepting it still shows the 15-day reminder.

**Acceptance Scenarios**:

1. **Given** a request with `numbers_edited`, **Then** for each edited field the admin sees the card
   image, the original reading value(s) (or «لم تقرأه البطاقة»), and the marketer's value, with the
   differences visible.
2. **Given** that view, **When** the admin pins a value (the reading's, the marketer's, or one typed by the
   admin), **Then** the national ID is normalized and validated as 12 digits, the family number is kept as
   written with its comparison key, and the pinned value replaces the request's working value. The
   original reading and the marketer's value stay stored unchanged.
3. **Given** a pin, **Then** the request is checked again against all records, excluding itself: new
   matches add their reasons and linked records; reasons whose match no longer exists are kept but marked
   «لم يعد ينطبق»; the edited-numbers reason is marked «تم التثبيت».
4. **Given** the re-check finds a family match on a new request, **Then** its type becomes second
   subscription, the reason «اشتراك إضافي» is added, and acceptance is still the admin's decision (§6.4).
5. **Given** the re-check finds a match that does not fit the request type (the same person on a new or
   second-subscription request, a national-ID conflict that was not on the request before the pin, or
   a return whose target no longer matches),
   **Then** the type does not change, the file shows a clear red warning naming the clash (for example
   «تحذير: الأرقام المثبّتة تطابق مشتركاً موجوداً (نفس الشخص)، والطلب مرفوع كجديد»), and the admin decides.
   Pressing «قبول» while the warning stands opens a second confirmation «القبول رغم التحذير؟» that must be
   confirmed; the accept is written to the audit log as accepted despite the warning, with the warning
   kind. «رفض» works as usual.
6. **Given** any pin, **Then** the audit log has who, when, which request, which field, and a reference
   to the pin record. The pin record holds the value before and after; the audit entry never holds
   the national ID or family number values themselves (constitution III v1.2.1).

---

### User Story 4 - Rule reminders next to the buttons (Priority: P3)

When the request is a second subscription, the decision area shows the reminder «إذا كان للاشتراك الأول
15 يوماً أو أكثر متبقية: قبول. أقل من ذلك: رفض.» together with the first subscription's expiry date when
it is known («حسب آخر استيراد»), or «تاريخ الانتهاء غير متوفر».

**Why this priority**: the admin applies the rule by hand in SAS; the reminder only helps.

**Independent Test**: Open a family request: the reminder is shown next to the buttons, with «تاريخ الانتهاء
غير متوفر» for a sijil-only linked record. Open a new request with only edited numbers: no reminder.

**Acceptance Scenarios**:

1. **Given** a request with reason «اشتراك إضافي», **Then** the 15-day reminder appears next to «قبول» and
   «رفض», with the linked record's expiry when known or «تاريخ الانتهاء غير متوفر».
2. **Given** a return request, **Then** the commission question is announced next to «قبول» before it is
   pressed («سيُطلب تحديد احتساب العمولة»).

---

### User Story 5 - Admin home counts (Priority: P3)

Any admin opens the admin home and sees today's and this month's numbers: requests submitted, accepted,
pending, linked and rejected.

**Why this priority**: it gives a quick view of the work waiting, but the review works without it.

**Independent Test**: Submit three requests today (one auto-accepted, two pending), reject one of the
pending: today shows submitted 3, accepted 1, pending 1, rejected 1, linked 0; the month shows the same
plus earlier days.

**Acceptance Scenarios**:

1. **Given** any admin (with or without `review`), **When** they open «الرئيسية», **Then** they see two
   rows, «اليوم» and «هذا الشهر», each with مرفوعة، مقبولة، بالانتظار، تم الربط، مرفوضة.
2. **Given** a request submitted at 23:30 Baghdad time, **Then** it counts in that Baghdad day, not the
   next UTC day.
3. **Given** the counts, **Then** no name, phone or number of any subscriber appears on the page.

### Edge Cases

- Two admins open the same request and both decide: the first decision wins; the second gets «تم البت في
  هذا الطلب مسبقاً» and the page refreshes to the current status.
- An admin loses `review` while a request is open: the next action is refused by the server.
- The marketer who submitted the request is archived or stopped: the request stays reviewable and shows
  the marketer's name.
- A linked record was itself rejected after this request was submitted: it is still shown, with its
  current status, so the admin sees the history; it no longer counts as a match on a re-check.
- A return request linked to several target records (same person in two sources): all are shown.
- A request has no images (should not happen after 008) or an image file is missing: the file shows
  «الصورة غير متوفرة» and the decision is still possible.
- The admin pins a value equal to the marketer's: allowed; it confirms the value, the reason is marked
  «تم التثبيت» and the re-check still runs.
- A pinned national ID that is not 12 digits after normalization is refused with «الرقم الوطني يجب أن يكون
  12 رقماً».
- A rejection reason made only of spaces counts as empty.
- An accepted or rejected request cannot be changed by this feature: there is no undo (§7.2 has no such
  transition). A rejected subscriber is entered again by a new request.
- The main admin always has review rights.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide the admin page «طلبات بالانتظار», visible and usable only by the main
  admin and admins with `review`; the server MUST refuse every list, file, image, pin, accept and reject
  call from anyone else.
- **FR-002**: The list MUST show all requests in pending review, oldest submission first, with number,
  type, reason labels, marketer, subscriber full name, tower and submission time in Baghdad time, and the
  total count; it MUST be filterable by reason (اشتراك إضافي، إعادة للخدمة، تعديل الأرقام، تعارض بالأرقام).
- **FR-003**: The request file MUST show every stored field of the request (card data, images, location,
  subscription with fixed prices, phone and its verification time, the username it will get, marketer,
  submission time) and all its reasons with their state.
- **FR-004**: For each linked record the file MUST show source, name, username, phone, tower, registration
  date, current status, images if any, and the link basis in Arabic. This data is returned only to review
  admins and never to the marketer.
- **FR-005**: Every opening of a card image (request or linked record) MUST be logged with who, when and
  which image.
- **FR-006**: «قبول» MUST move a pending request to accepted and store the approving admin and time; it
  MUST be possible only from pending review.
- **FR-007**: Accepting a return request MUST require a نعم/لا answer to «هل تُحتسب عمولة للمسوّق؟», stored on
  the request; new and second-subscription requests MUST be stored as counting for commission.
- **FR-008**: «رفض» MUST require a non-empty reason, move a pending request to rejected, and store the
  reason, the admin and the time.
- **FR-009**: Accept and reject MUST be safe against concurrent decisions: only one decision per request
  is ever stored; a late one gets «تم البت في هذا الطلب مسبقاً».
- **FR-010**: The username of an accepted request MUST be the one fixed at submission (the historical one
  for a return, `{tower code}-{phone}` otherwise) and MUST NOT change at acceptance.
- **FR-011**: The marketer's view of their request MUST show «تمت الموافقة» with the username for an
  accepted request, and «تم رفض الطلب» with the reason for a rejected one, and MUST NOT include any linked
  record's data, the deciding admin's name, or the reasons' internal details (the decision time may be
  shown).
- **FR-012**: For `numbers_edited`, the file MUST show per edited field the card image, the original
  reading (face and MRZ) or «لم تقرأه البطاقة», and the marketer's value.
- **FR-013**: The admin MUST be able to pin the national ID and/or family number of a pending request; the
  pinned value MUST pass the same normalization and validation as the form (§6.2), and the original reading
  and marketer value MUST stay stored unchanged (Principle IV).
- **FR-014**: After a pin the system MUST re-run the §6.1 match against all sources (excluding the request
  itself and rejected requests), add new reasons and linked records, mark reasons that no longer apply as
  «لم يعد ينطبق» without deleting them, and mark the edited-numbers reason as «تم التثبيت». The
  «إعادة للخدمة» reason is never marked; a lost return target raises a warning instead (FR-019a).
- **FR-015**: If the re-check finds a family match on a new request, the request type MUST become second
  subscription with reason «اشتراك إضافي» and still need the admin's acceptance.
- **FR-016**: For a second-subscription request the decision area MUST show the 15-day reminder and the
  linked record's expiry date «حسب آخر استيراد» when known, otherwise «تاريخ الانتهاء غير متوفر».
- **FR-017**: Accept, reject and pin MUST be written to the audit log with who, when, request number, the
  status (or field) before and after, the rejection reason and the commission answer — never the national
  ID, family number, phone, names or images. A pin's before and after values are kept in its pin
  record, and the audit entry points to that record.
- **FR-018**: A rejected request MUST no longer count as existing in any later check (§6.1 note); this is
  already true in 008 and MUST stay true.
- **FR-019**: The rejection reason MUST be picked from a fixed list: «صورة البطاقة غير واضحة»،
  «الأرقام غير مطابقة للبطاقة»، «المتبقي من الاشتراك الأول أقل من 15 يوماً»، «المشترك لديه اشتراك فعّال»،
  «سبب آخر». «سبب آخر» MUST require a text, and the text field shows the hint «لا تكتب أي معلومة عن مشترك
  آخر». The marketer sees the picked reason, and for «سبب آخر» the text as written. The reason code and
  text are both stored.
- **FR-019a**: When a re-check after a pin finds a clash with the request type (FR-014: same person on a
  new or second-subscription request, a national-ID conflict that was not on the request before the
  pin, or a return whose target no longer matches), the type MUST stay as it is, the file MUST show a red warning naming the clash, and «قبول»
  MUST need a second confirmation «القبول رغم التحذير؟». Such an accept MUST be audited as accepted
  despite the warning, with the warning kind (no card data).
- **FR-020**: All new texts MUST be Arabic and RTL: «طلبات بالانتظار»، «قبول»، «رفض»، «سبب الرفض»،
  «هل تُحتسب عمولة للمسوّق؟»، «تثبيت القيمة»، «القراءة الأصلية»، «قيمة المسوّق»، «لم يعد ينطبق»،
  «تم التثبيت»، «تم البت في هذا الطلب مسبقاً»، «تاريخ الانتهاء غير متوفر».
- **FR-021**: The admin home page (§10 item 1), open to every admin, MUST show today's and this month's
  counts (Baghdad time) of requests: submitted, accepted, pending, linked, rejected. «Accepted» and
  «rejected» count by decision time (an automatic acceptance counts at submission), «submitted» by
  submission time, «linked» by link time (0 until 012), and «pending» is the current number pending. The
  counts carry no subscriber data.

### Key Entities

- **Request** (from 008/009): gains the decision — accepted by/at or rejected by/at with reason — and
  «counts for commission» (yes/no; always yes for new and second subscription). Its type may change from
  new to second subscription after a pin.
- **Pending reason** (from 008/009): gains a state — open, «تم التثبيت» (edited numbers after a pin),
  «لم يعد ينطبق» (match gone after a pin) — and the time and admin that changed it. Reasons added by a
  re-check are marked as added at review.
- **Pinned number**: the field (national ID or family number), the value before and the pinned value,
  which source it came from (reading, MRZ, marketer, typed by admin), who and when. The original reading and marketer value are kept.
- **Linked record**: source (sijil, legacy, SAS), reference and link basis; shown to review admins only.
- **Image access entry**: who opened which image and when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can open a pending request, compare it with its linked records and decide in under
  2 minutes for a single-reason request.
- **SC-002**: 100% of pending requests from every reason path of 008/009 appear in the list with the right
  labels and can be accepted or rejected in tests.
- **SC-003**: 0 requests end with two decisions in concurrent-decision tests.
- **SC-004**: In 100% of marketer-facing responses tested after accept and after reject, none contains any
  linked record's data or the reasons' internal details.
- **SC-005**: 100% of accepts, rejects, pins and image openings appear in the audit/access log, and none
  of those entries contains a national ID, family number, phone or name.
- **SC-006**: Every call of the review functions by a user without `review` is refused (100% of the
  tested calls).

## Assumptions

- Accepting a request with unpinned edited numbers accepts the marketer's values as they are; pinning is
  optional.
- The admin cannot edit other fields (names, phone, tower, category, location) during review; those
  edits belong to the subscriber file (017). The marketer's name edits are visible because the reading is
  shown next to the stored names.
- There is no undo of accept or reject in this feature; a rejected case is re-entered as a new request.
- The marketer sees the status change when opening the request; in-app and push notifications come in
  011, and so do the request tabs.
- The SAS expiry date exists only after 014; until then the reminder always shows «تاريخ الانتهاء غير
  متوفر» for sijil records.
- The live linked-record status shown is the current one; the reasons and links stored at submission are
  never rewritten, only marked by state.
- A second-subscription request accepted gets new-subscriber pricing (§6.4); the prices were already fixed
  at submission from the category, so nothing changes at acceptance.
- Pending requests are listed oldest first so none is forgotten; no automatic expiry of pending requests.
- The rejection reason list is fixed in this feature (not editable in the settings); a change to it is a
  system.md change.
