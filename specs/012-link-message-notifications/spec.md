# Feature Specification: Link Message, Request Statuses and Notifications

**Feature Branch**: `012-link-message-notifications`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "الفيزة 012: رسالة الربط وحالات الطلب والإشعارات. ارجع لـ docs/system.md (جدول الفيزات §16
والأقسام المتعلقة) ولشغل 008 إلى 011، وانتبه للطلب المحذوف. بعد المواصفة لخّصلي بالعربي شنو يتغيّر للمسوّق والأدمن، وشنو
الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §1 (second goal: the link message), §2 (terms «رسالة الربط»،
«تم الربط»), §3.1 (the marketer sees only their own requests and nothing about another subscriber), §4.1
(bottom bar with «الإشعارات»), §4.3 (requests list, search, tabs, colours, request page), §4.4 (in-app
notifications and optional Push), §5.5 («نسخ التفاصيل» is not the link message), §6.4 (accept, reject, reason
shown to the marketer, first decision wins), §7.2 (statuses, colours, allowed transitions), §7.4 (deleted
request as the marketer sees it), §8.4 (link message format and buttons), §13 (no sensitive data in messages);
constitution Principles I (status changes only through allowed transitions), II (no sensitive data in the link
message), V (Arabic, RTL, consistent status colours), VI (simplicity), VIII (tested status transitions), IX
(marketer reaches only their own requests).

**Builds on**: 005 (marketer app shell with the «الإشعارات» tab as a placeholder), 008 (requests, result screen,
«نسخ التفاصيل», «نسخ اليوزر»), 009 (return and additional requests), 010 (accept, reject with reason from a
fixed list, first decision wins), 011 (deleted requests: marked «محذوف», personal data erased).

**Numbering note**: specs 008–010 call this work "011" and «تم الربط» "012"; since 011 (deletion) was inserted,
this is 012 and «تم الربط» is 013 (`docs/system.md` §16).

**Out of scope (later features)**: pressing «تم الربط», undoing it, the «بانتظار الربط» admin page and the
monthly counter (013); browser Push notifications (later, owner decision 2026-11-24) — this feature only prepares the notifications those two events will send and the
«تم الربط» tab that will list them; the tier and expected amount on the marketer home (017); the admin
subscriber search and file (018); reports and export (019).

**Governance changes this feature needs** (approved by the owner on 2026-11-24): `docs/system.md` 1.17 —
§4.4 (deletion notifies the marketer; auto-acceptance does not; notifications hold no personal data; Push
later) and §8.4 (tower line «اسم البرج (رمز البرج)»). No constitution change.

## Clarifications

### Session 2026-11-24

- Q: Tower line in the link message: §8.4 shows «ALM03 (العلم)», «نسخ التفاصيل» uses «اسم البرج (رمز البرج)»?
  → A: «اسم البرج (رمز البرج)», the same as «نسخ التفاصيل»; §8.4 is updated.
- Q: Does deleting a request notify its marketer? → A: Yes: «تم حذف الطلب» with the request number and the
  deletion reason only.
- Q: Is browser Push part of 012? → A: No. In-app notifications only; Push comes later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Copy or share the link message of an accepted request (Priority: P1)

A marketer opens one of their requests that is accepted (auto-accepted at submission, or accepted by an admin).
Under the request details they see the «رسالة الربط» block in the fixed format of §8.4 and two buttons:
«نسخ رسالة الربط» copies the text, and «مشاركة بالواتساب» opens WhatsApp with the text ready so the marketer
picks the technicians' group and sends it.

**Why this priority**: This is the second goal of the system (§1): after acceptance, the marketer must hand the
technicians a correct, complete message so the subscriber gets connected. Without it, accepted requests go
nowhere.

**Independent Test**: Submit a synthetic request that is auto-accepted, open it as its marketer, press «نسخ رسالة
الربط» and paste the text: it matches the §8.4 format line by line, with the real map link of the pin, and has
no national ID, family number, image or code. Press «مشاركة بالواتساب»: WhatsApp opens with the same text.

**Acceptance Scenarios**:

1. **Given** an accepted request, **When** its marketer opens it, **Then** the link message is shown with the
   lines: «طلب ربط جديد | رقم الطلب: #T3C-…», الاسم, الهاتف, اليوزر, البرج, الفئة with both prices, العنوان,
   الموقع (a map link built from the saved pin), المسوّق.
2. **Given** the link message, **When** the marketer presses «نسخ رسالة الربط», **Then** the exact text is
   copied and a short confirmation «تم النسخ» appears.
3. **Given** the link message, **When** the marketer presses «مشاركة بالواتساب», **Then** WhatsApp (app or
   web) opens with the text filled in and no recipient chosen.
4. **Given** a request that is pending review, rejected, or deleted, **When** its marketer opens it, **Then**
   no link message and no share button are shown.
5. **Given** a linked request (once 013 exists), **When** its marketer opens it, **Then** the link message is
   still shown (§8.4: accepted or linked).
6. **Given** any link message, **Then** it never contains the national ID, the family number, any image or
   image link, or an OTP code.
7. **Given** a return request accepted with its historical username, **Then** the link message carries that
   username and the subscription's phone.
8. **Given** a request accepted while its marketer had it open, **When** the marketer reloads or returns to it,
   **Then** the link message appears without having to submit again.

---

### User Story 2 - The marketer is notified when an admin decides (Priority: P1)

When an admin accepts or rejects one of a marketer's requests, the marketer gets an in-app notification. The
«الإشعارات» icon in the bottom bar (side bar on large screens) shows the number of unread notifications. The
notifications page lists them newest first; each one says what happened, to which request (number and
subscriber name), and when. Tapping one opens the request and marks it read.

**Why this priority**: Today the marketer only learns of a decision by opening each request. Without a signal,
accepted requests wait and their link messages are not sent, and rejected ones are not redone.

**Independent Test**: As a marketer, submit a request that goes pending review. As an admin, accept it. Within
about 15 seconds the marketer's notification icon shows «1»; the list shows «تمت الموافقة على الطلب #T3C-…»
with the subscriber's name; tapping it opens the request with its link message and the counter goes to 0.

**Acceptance Scenarios**:

1. **Given** a pending request, **When** an admin accepts it, **Then** its marketer gets one notification
   «تمت الموافقة على الطلب» with the request number, the subscriber's name and the time.
2. **Given** a pending request, **When** an admin rejects it, **Then** its marketer gets one notification «تم
   رفض الطلب» with the number, the name and the rejection reason's name.
3. **Given** two admins decide the same request, **Then** only the first (effective) decision creates a
   notification.
4. **Given** a request auto-accepted at submission, **Then** no notification is created (the marketer sees
   the result at once).
5. **Given** unread notifications, **When** the marketer opens the app on any page, **Then** the icon shows the
   unread count; with none unread it shows no number.
6. **Given** a notification, **When** the marketer taps it, **Then** the request opens and that notification
   becomes read.
7. **Given** several unread notifications, **When** the marketer presses «تعليم الكل كمقروء», **Then** all
   become read and the counter disappears.
8. **Given** a marketer, **Then** they never see a notification about another marketer's request.
9. **Given** an admin decides while the marketer's app is open, **Then** the counter updates without a manual
   reload, within about 15 seconds.

---

### User Story 3 - Requests list with search, tabs and fixed colours (Priority: P2)

The marketer's «الطلبات» page has the tabs «بالانتظار»، «مقبولة»، «تم الربط»، «مرفوضة»، «مسودات», each status
in its fixed colour (§7.2), and a search box that finds the marketer's own requests by subscriber name, phone,
or request number.

**Why this priority**: As requests accumulate, the marketer needs to find a request fast (for example when a
subscriber calls) to copy its link message again. The tabs already exist; search and the «تم الربط» tab are
missing.

**Independent Test**: With several synthetic requests in different statuses, search by part of a name, by a
phone written with spaces or Arabic digits, and by «1004» or «T3C-1004»: only the marketer's own matching
requests appear, each with its coloured status.

**Acceptance Scenarios**:

1. **Given** the requests page, **Then** the statuses are shown with these labels and colours everywhere:
   بانتظار المراجعة (orange), مقبول (بانتظار الربط) (blue), مرفوض (red), تم الربط (green), مسودة (grey).
2. **Given** the search box, **When** the marketer types part of a subscriber's name, **Then** matching
   requests of that marketer appear across all statuses, each with its status chip.
3. **Given** the search box, **When** the marketer types a phone in any accepted form (spaces, dashes, Arabic
   digits, 964 prefix), **Then** it is normalised (§8.1) before matching.
4. **Given** the search box, **When** the marketer types a request number with or without «T3C-», in Latin or
   Arabic digits, **Then** that request appears if it is theirs.
5. **Given** a deleted request, **When** the marketer searches by its number, **Then** it appears marked
   «محذوف»; searching by its former name or phone does not find it (the data is erased).
6. **Given** the «تم الربط» tab, **Then** it lists the marketer's linked requests (empty until 013 links any).
7. **Given** a search, **Then** another marketer's requests are never returned, even with an exact number.

---

### User Story 4 - Deleted requests and notifications (Priority: P2)

A request can be deleted (011) after a notification about it was created (for example a rejection that was
later deleted as a duplicate). Notifications must not keep, or bring back, the personal data that deletion
erased.

**Why this priority**: The deletion feature promises that erased data is gone from every screen. Notifications
are a new screen and must keep that promise.

**Independent Test**: Reject a synthetic request (the marketer gets a notification with the subscriber's name),
then delete it. The marketer's notification now shows only the request number and «محذوف», and opening it shows
the deleted view of 011.

**Acceptance Scenarios**:

1. **Given** a notification about a request that was later deleted, **When** the marketer views the list,
   **Then** it shows the event, the request number and «محذوف», and no name.
2. **Given** such a notification, **When** the marketer taps it, **Then** the deleted view of 011 opens (reason,
   number, tower, dates only, no copy or share buttons).
3. **Given** a pending or rejected request, **When** an admin deletes it (011), **Then** its marketer gets one
   notification «تم حذف الطلب» with the request number and the deletion reason's name only, and tapping it
   opens the deleted view.
4. **Given** a deletion refused (already deleted, or the request is accepted), **Then** no notification is
   created.

---

### User Story 5 - Notifications for «تم الربط» and its undo are ready for 013 (Priority: P3)

The notification list knows two more events, «تم ربط المشترك» and «تم التراجع عن الربط» (with the undo reason),
so that feature 013 only has to emit them when an admin presses «تم الربط» or undoes it.

**Why this priority**: §4.4 asks for these notifications, but the actions themselves come with 013; this story
only fixes their wording and behaviour now.

**Independent Test**: Covered by automated tests that create each event directly and check its Arabic text and
that it opens the request; end-to-end in 013.

**Acceptance Scenarios**:

1. **Given** a «linked» event on a marketer's request, **Then** the notification reads «تم ربط المشترك» with
   the number and the name.
2. **Given** an «undo linked» event, **Then** the notification reads «تم التراجع عن الربط» with the number, the
   name and the reason.

---

### Edge Cases

- A request accepted by an admin while its marketer is on the request page: the page shows the new status and
  the link message on the next refresh or poll.
- A request whose subscriber name contains only the required names (no surname, «لا يوجد لقب على البطاقة"): the
  link message uses the full name as computed (§5.1) without an empty gap.
- The address or the landmark is empty: the «العنوان» line shows whichever exists, without a dangling comma.
- The marketer's account is renamed after acceptance: «المسوّق» shows the marketer's current name (the same
  rule as «نسخ التفاصيل»).
- The tower or the plan is renamed or stopped after submission: the link message uses the names stored on the
  request at submission (§5, §5.3).
- The device does not allow copying (older browser, no permission): the text is shown selectable and a message
  «تعذّر النسخ، انسخ النص يدوياً» appears.
- WhatsApp is not installed on the phone: the share opens WhatsApp Web in the browser.
- A notification about a request whose marketer account was later archived: the account cannot sign in, so it
  is never seen; nothing else changes.
- Many notifications: the list shows the newest first and loads older ones as the marketer scrolls.
- A rejection with «سبب آخر»: the notification shows «سبب آخر» only; the written note is read inside the
  request page (it is erased if the request is deleted, 011).
- Search with fewer than 2 characters, or only spaces: no search runs, the current tab is shown.

## Requirements *(mandatory)*

### Functional Requirements

**Link message (§8.4)**

- **FR-001**: The marketer's request page MUST show the link message only when the request's status is
  accepted or linked, and never for a pending, rejected, or deleted request.
- **FR-002**: The link message MUST follow the §8.4 format exactly, one item per line:
  «طلب ربط جديد | رقم الطلب: #T3C-N», «الاسم: full name», «الهاتف: subscription phone», «اليوزر: username»,
  «البرج: tower name (tower code)» (the same form as «نسخ التفاصيل», §5.5), «الفئة: plan | التجريبي X
  د.ع | الثاني Y د.ع», «العنوان: address، landmark», «الموقع: https://maps.google.com/?q=lat,lng», «المسوّق:
  marketer name».
- **FR-003**: Prices MUST be written with thousands separators and «د.ع», from the prices stored on the
  request; names of tower, area and plan MUST come from the values stored at submission.
- **FR-004**: The map link MUST be built from the pin saved on the request, with the coordinates as stored (no
  rounding that moves the point by more than a few metres).
- **FR-005**: The link message MUST NOT contain the national ID, the family number, images or image links, or
  any OTP code, and the server MUST be the one that composes it, so no hidden field can leak.
- **FR-006**: «نسخ رسالة الربط» MUST copy the exact text and confirm with «تم النسخ»; on failure the text stays
  visible and selectable with «تعذّر النسخ، انسخ النص يدوياً».
- **FR-007**: «مشاركة بالواتساب» MUST open WhatsApp with the text ready and no recipient preset.
- **FR-008**: «نسخ التفاصيل» and «نسخ اليوزر» (§5.5) MUST stay as they are; the link message is a separate block.
- **FR-009**: Only the request's own marketer MUST be able to get its link message from the marketer app.

**Statuses and transitions (§7.2)**

- **FR-010**: Every status label and colour MUST be the same on every marketer and admin screen: بانتظار
  المراجعة orange, مقبول (بانتظار الربط) blue, مرفوض red, تم الربط green, مسودة grey; a deleted request keeps
  its status and carries a grey «محذوف» mark (011).
- **FR-011**: The server MUST allow only the transitions of §7.2: submission to accepted or pending review;
  pending review to accepted or rejected; accepted to linked; linked back to accepted. Any other change MUST be
  refused, and a deleted request MUST NOT change status. Each allowed and refused transition MUST be covered by
  tests (Principle VIII), including the two linked transitions that 013 will use.

**Requests list (§4.3)**

- **FR-012**: The «تم الربط» tab MUST list the marketer's linked requests, newest link first once 013 records
  the link time (until then, newest submission first).
- **FR-013**: The requests page MUST offer one search box that matches the marketer's own submitted requests by
  subscriber name (part of the full name, ignoring diacritics and extra spaces), by phone (normalised per §8.1),
  or by request number (with or without «T3C-», Latin, Arabic or Indic digits). Results span all statuses and
  show each status chip.
- **FR-014**: Search MUST never return another marketer's requests, and MUST match a deleted request by its
  number only.
- **FR-015**: Drafts MUST stay in their own tab and are not searched (they have no number and are not
  requests).

**In-app notifications (§4.4)**

- **FR-016**: A notification MUST be created for the request's marketer when an admin accepts it, when an admin
  rejects it, and (from 013) when it is linked and when the link is undone. Auto-acceptance at submission MUST
  NOT create a notification.
- **FR-017**: Each decision MUST create at most one notification; a refused second decision (already decided)
  MUST create none.
- **FR-018**: A notification MUST show the event in Arabic («تمت الموافقة على الطلب»، «تم رفض الطلب»، «تم ربط
  المشترك»، «تم التراجع عن الربط»، «تم حذف الطلب»), the request number, the subscriber's full name (none for a
  deleted request), the time in Baghdad time, and for a rejection, an undo or a deletion the reason's name.
- **FR-019**: A notification MUST NOT store a copy of the subscriber's personal data; the name is shown from the
  request at display time, so after deletion (011) it shows the number and «محذوف» only.
- **FR-020**: The «الإشعارات» icon MUST show the number of the marketer's unread notifications (none shown at
  zero), and update while the app is open within about 15 seconds without reload.
- **FR-021**: Opening a notification MUST open its request and mark it read; «تعليم الكل كمقروء» MUST mark all
  of the marketer's notifications read.
- **FR-022**: The list MUST be newest first and load older notifications progressively.
- **FR-023**: A marketer MUST only reach their own notifications; the server MUST check this on every call
  (Principle IX).
- **FR-024**: A successful deletion (011) MUST create one notification «تم حذف الطلب» for the request's
  marketer, carrying the request number and the deletion reason's name only; a refused deletion MUST create
  none.
- **FR-025**: Push notifications are not part of this feature; the in-app list and counter are the only
  channel, and the system MUST NOT depend on Push when it is added later.

### Key Entities

- **Notification**: one event for one marketer about one request. Holds the marketer, the request, the event
  kind (accepted, rejected, linked, link undone, deleted), the time, the read time, and for rejection, undo
  and deletion the reason's name. Holds no subscriber name, phone, numbers or address.
- **Link message**: not stored; composed by the server from the request's stored values each time it is shown,
  so it always reflects stored names and prices and never outlives an erasure.
- **Request** (existing): adds nothing for this feature except what 013 will add for linking.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an accepted request, a marketer can copy or share the link message in at most 2 taps from
  opening the request.
- **SC-002**: 100% of link messages in automated tests match the §8.4 line format and contain none of: national
  ID, family number, image links, OTP code.
- **SC-003**: After an admin decides, the marketer's counter shows the new notification within 15 seconds while
  the app is open, and on the next app open otherwise.
- **SC-004**: A marketer finds one of their requests by name, phone or number in under 10 seconds, and never
  sees another marketer's request (0 leaks in tests).
- **SC-005**: After a request is deleted, 0 screens available to the marketer (list, request page, notifications,
  search) show its erased name or phone.
- **SC-006**: Every allowed and every forbidden status transition of §7.2 has a passing test.

## Assumptions

- Only the marketer sees the link message in 012. The admin sees it with the «بانتظار الربط» page in 013 if
  needed (§6.5 does not ask for it).
- «الهاتف» in the link message is the subscription phone saved on the request.
- Auto-accepted requests do not notify, because the marketer sees «تمت الموافقة» on the result screen at the
  same moment (§4.4 speaks of a change of status the marketer did not make).
- The counter updates by asking the server every 15 seconds while the app is open (the same approach as the
  draft change check in 005); no live connection is added.
- Notifications are kept; there is no automatic cleanup in this feature.
- Admin screens do not change, except that their accept and reject actions now notify the marketer and the
  status labels and colours follow FR-010.
- Marketer search is part of §4.3 and is built here; the admin subscriber search stays in 018.
- `docs/system.md` 1.17 records the owner's answers: §4.4 (deletion notifies, auto-acceptance does not,
  notifications hold no personal data, Push later), §8.4 (tower line «اسم البرج (رمز البرج)»).
