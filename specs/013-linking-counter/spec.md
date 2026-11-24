# Feature Specification: «تم الربط» and the Monthly Counter

**Feature Branch**: `013-linking-counter`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "الفيزة 013: تم الربط والعدّاد. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام المتعلقة)
ولشغل 010 إلى 012: جدول انتقالات الحالات، ونصوص إشعارَي «تم ربط المشترك» و«تم التراجع عن الربط»، وترتيب تبويب «تم
الربط» حسب تاريخ الربط. وانتبه للطلب المحذوف. بعد المواصفة لخّصلي بالعربي شنو يتغيّر للمسوّق والأدمن، وشنو الأسئلة
اللي تحتاج قراري."

**System document references**: `docs/system.md` §2 (term «تم الربط»), §3.3 (permission `link`: «تم الربط» and
its undo), §4.2 (marketer home: «تم الربط هذا الشهر: N» and the latest linked subscribers this month), §4.3 (tab
«تم الربط»), §4.4 (notifications for link and undo), §6.4 (`counts_commission` on an accepted return), §6.5 (the
whole linking rule), §7.2 (`approved → linked`, `linked → approved`; link completion is its own recorded fact),
§7.4 (accepted and linked requests are never deleted), §8.4 (the link message stays for a linked request), §9
(monthly count = linked in the month and counted for commission), §10 items 1 and 3 (admin home «تم الربط» count;
page «بانتظار الربط»), §13 (link and undo are audited); constitution Principles I (status changes only through
allowed transitions), III (permanent audit trail), VIII (tested transitions and counts), IX (server-side
authorization), X (Baghdad month boundaries, UTC storage).

**Builds on**: 010 (accept, `counts_commission` on returns, first decision wins, admin home counts), 011 (deleted
requests: only pending or rejected, never accepted or linked), 012 (the transition table `approved → linked` and
`linked → approved` already allowed and tested; notification kinds `linked` and `unlinked` with the texts «تم
ربط المشترك» and «تم التراجع عن الربط»; the marketer «تم الربط» tab, ordered by submission until this feature;
the link message shown for linked requests).

**Out of scope (later features)**: the tier, the expected amount and «باقيلك N» on the marketer home, the
commission report and «تم الدفع» with its month lock and its alert on a later undo (017); the admin subscriber
search and file (018); reports and the submission/link date filter (019); browser Push (later).

**Governance changes this feature needs** (approved by the owner on 2026-11-24): `docs/system.md` 1.18 — §4.2
(counter counts links counted for commission, with «و M بلا عمولة» under it), §6.5 (fixed undo reasons, a
re-link counts in the month of the new link, undo from the recent links list), §10 item 3 (the page also lists
recent links with the undo button). No constitution change.

## Clarifications

### Session 2026-11-24

- Q: Does a return accepted with «لا» for commission count in the marketer's counter? → A: The counter counts
  only links counted for commission; under it «و M بلا عمولة» shows the others when there are any.
- Q: A request linked, undone, then linked again: which month does it count in? → A: The month of the new link;
  it counts once.
- Q: Undo reasons? → A: «لم يُربط فعلياً في SAS»، «ضُغط بالخطأ»، «ربط طلب آخر بدله»، «سبب آخر» — a fixed list,
  «سبب آخر» without text.
- The assumptions below (undo of a previous month allowed, no link message on the admin page, link needs only a
  confirmation) were approved as written.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The admin confirms «تم الربط» (Priority: P1)

An admin with the `link` permission opens «بانتظار الربط». It lists every accepted request that is not linked
yet, the one waiting longest first, with what the admin needs to find the subscriber in SAS: request number,
subscriber name, username, subscription phone, tower «اسم البرج (رمز البرج)», plan, marketer, and acceptance date.
After checking SAS by hand, the admin presses «تم الربط» on the row and confirms. The request leaves the list,
becomes «تم الربط» (green) everywhere, and its marketer is notified.

**Why this priority**: Linking is the moment the marketer earns the subscriber (§2, §6.5). Without it the
counter, the commission (017) and the second half of the request's life do not exist.

**Independent Test**: Accept a synthetic request (auto or by an admin). As an admin with `link` only, open
«بانتظار الربط», find it by its number, press «تم الربط» and confirm: the row disappears, the marketer's
notification icon shows a new «تم ربط المشترك», and the request shows status «تم الربط» with its link date.

**Acceptance Scenarios**:

1. **Given** accepted, not-linked requests, **When** an admin with `link` opens «بانتظار الربط», **Then** each
   appears once, oldest acceptance first, with number, name, username, phone, tower, plan, marketer and
   acceptance date, and nothing else (no national ID, family number or card image).
2. **Given** the list, **When** the admin types a request number (with or without «T3C-», any digits), a
   username, or a phone (any form, §8.1), **Then** the list narrows to the matching requests.
3. **Given** a row, **When** the admin presses «تم الربط» and confirms, **Then** the request's status becomes
   «تم الربط», its link time and the admin are recorded, it leaves the list, and an audit entry «تم الربط» is
   written (who, when, request number).
4. **Given** a successful link, **Then** the request's marketer gets exactly one notification «تم ربط المشترك»
   with the request number and the subscriber's name.
5. **Given** two admins press «تم الربط» on the same request, **Then** only the first takes effect; the second
   sees «تم ربط هذا الطلب مسبقاً», and no second notification or audit entry is created.
6. **Given** a request that is pending review, rejected, deleted or already linked, **When** anyone tries to link
   it (including by a direct call), **Then** the server refuses it and nothing changes.
7. **Given** an admin without `link`, **Then** the page is not in their menu and the server refuses its data and
   its actions; a marketer can never link.
8. **Given** a request accepted while «بانتظار الربط» is open, **Then** it appears on the next refresh.

---

### User Story 2 - The marketer sees the counter and the linked subscribers (Priority: P1)

On the marketer home, «تم الربط هذا الشهر: N» now shows the real number of the marketer's requests linked in the
current Baghdad month, and under it the latest subscribers linked this month (name + «تم الربط»). The «تم الربط»
tab of «الطلبات» lists the marketer's linked requests, newest link first, each with its link date.

**Why this priority**: The counter is what the marketer watches every day; it is the base of their commission
(§9). It has shown a fixed 0 since 001.

**Independent Test**: Link three synthetic requests of one marketer this month (one of them a return accepted
with «لا» for commission). The home counter shows the number set by the counter rule (see FR-011), the list
below it shows the linked names newest first, and the «تم الربط» tab shows the three ordered by link time.

**Acceptance Scenarios**:

1. **Given** a marketer with requests linked this month, **When** they open the home, **Then** «تم الربط هذا
   الشهر: N» shows the count defined by FR-011, and another marketer's links never count.
2. **Given** the first moment of a new Baghdad month, **Then** the counter starts from 0, and last month's links
   stay linked and listed in the «تم الربط» tab (the reset deletes nothing).
3. **Given** links this month, **Then** the home lists the latest of them, newest first, by subscriber name with a
   green «تم الربط» chip; tapping one opens the request.
4. **Given** the «تم الربط» tab, **Then** it lists all the marketer's linked requests across months, newest link
   first, each with its link date in Baghdad time.
5. **Given** a linked request, **When** its marketer opens it, **Then** the status is «تم الربط» (green), the link
   date is shown, and the link message with «نسخ رسالة الربط» and «مشاركة بالواتساب» is still there (§8.4).
6. **Given** a request linked while the marketer has the app open, **Then** the counter and the list show it on
   the next refresh, and the notification counter within about 15 seconds (012).

---

### User Story 3 - The admin undoes «تم الربط» with a reason (Priority: P2)

A link was pressed by mistake, or the subscriber was not really connected. An admin with `link` finds the request
in the «تم الربط» part of the page (recent links, searchable by number, username or phone), presses «التراجع عن
الربط», picks a reason from a fixed list, and confirms. The request goes back to «مقبول (بانتظار الربط)» and
returns to «بانتظار الربط»; it no longer counts for the marketer; the marketer is notified with the reason.

**Why this priority**: §6.5 allows the undo and the counter and the commission depend on it being exact; it is
less frequent than linking.

**Independent Test**: Link a synthetic request, then undo it with a reason: the marketer's counter goes down by
one, the request is back in «بانتظار الربط», the marketer receives «تم التراجع عن الربط» with the reason, and the
audit log shows the undo (who, when, reason). Link it again: the counter goes up by one, not two.

**Acceptance Scenarios**:

1. **Given** a linked request, **When** an admin with `link` presses «التراجع عن الربط», **Then** a reason must
   be chosen from the fixed list before confirming (FR-016).
2. **Given** a confirmed undo, **Then** the status becomes «مقبول (بانتظار الربط)», the request is back in
   «بانتظار الربط», the undo time, admin and reason are recorded, and an audit entry «تراجع عن الربط» is written
   (who, when, request number, reason).
3. **Given** a confirmed undo, **Then** the marketer gets exactly one notification «تم التراجع عن الربط» with the
   request number, the subscriber's name and the reason's name.
4. **Given** an undone request, **Then** it no longer counts in any month's linked count (marketer home, admin
   home), and leaves the marketer's «تم الربط» tab (it shows in «مقبولة» again).
5. **Given** a request linked, undone and linked again, **Then** it counts exactly once, in the month set by
   FR-013, and its full history (each link and undo, who, when, reason) stays recorded.
6. **Given** two admins undo the same link, **Then** only the first takes effect; the second sees «تم التراجع عن
   هذا الربط مسبقاً», with no second notification or audit entry.
7. **Given** a request that is not linked, **When** anyone tries to undo it, **Then** the server refuses it.

---

### User Story 4 - The admin home counts links (Priority: P3)

The admin home's «تم الربط» number for today and for the month, fixed at 0 since 010, now counts requests linked
in that Baghdad day and month, by link time.

**Why this priority**: A summary number; the work is done by Stories 1 and 3.

**Independent Test**: Link two synthetic requests today and undo one: the admin home shows «تم الربط» = 1 for today
and for the month.

**Acceptance Scenarios**:

1. **Given** links today, **Then** the admin home's «تم الربط» today and month show the number of requests whose
   current link falls in that Baghdad day and month.
2. **Given** an undone link, **Then** it is not counted.
3. **Given** the admin home, **Then** it still shows counts only, no subscriber data.

---

### Edge Cases

- **Deleted requests**: only pending or rejected requests can be deleted (§7.4), so a deleted request is never in
  «بانتظار الربط», can never be linked, and never counts. The server still refuses link and undo on a deleted row
  with the deletion error (011), and the lists exclude deleted rows even if one ever appeared there.
- **Deleting a linked or undone request**: refused, as for any accepted request (§7.4); now testable with real
  linked rows. A request that was linked then undone is accepted, so it stays non-deletable.
- **Notifications on a deleted request**: unchanged from 012 (number and «محذوف» only); a linked request cannot
  reach that state.
- **Link across midnight or month end**: the month is the Baghdad month of the link time; a link at 23:59 on
  the last day counts in that month, at 00:00 in the next.
- **Undo of a link from a previous month**: the previous month's count goes down (see FR-013 for the month of a
  later re-link). The paid-month lock and its admin alert come with 017 (§9).
- **Return accepted with «لا» for commission**: it is linked like any request; whether it shows in the marketer's
  counter follows FR-011.
- **Archived or stopped marketer**: their accepted requests can still be linked and undone, they still count
  toward the marketer's month; the marketer simply does not see it until restored (§3.6).
- **Renamed tower, plan or marketer**: the «بانتظار الربط» row uses the names stored on the request for tower and
  plan, and the marketer's current name (same rule as the link message, 012).
- **Admin with `link` but without `review`**: sees only the linking details of the row (FR-002), never the card
  images or identity numbers, and cannot open the review file.
- **Many waiting requests**: the list pages or loads more as the admin scrolls; search finds any of them.
- **Link pressed twice by the same admin (double tap)**: one link, one notification.

## Requirements *(mandatory)*

### Functional Requirements

**«بانتظار الربط» page (§6.5, §10 item 3)**

- **FR-001**: The page MUST be shown and served only to the main admin and to admins with `link`; the server MUST
  refuse its data and actions to anyone else (Principle IX).
- **FR-002**: It MUST list every accepted, not-linked, not-deleted request, oldest acceptance first, with request
  number, subscriber full name, username, subscription phone, tower «اسم البرج (رمز البرج)», plan, marketer
  current name and acceptance date (Baghdad time). It MUST NOT show the national ID, family number, card images or
  any other card field.
- **FR-003**: The page MUST offer a search by request number (with or without «T3C-», Latin, Arabic or Indic
  digits), username, or phone (normalised per §8.1).
- **FR-004**: The page MUST also show recently linked requests (newest link first, same columns plus link date and
  who linked), searchable the same way, each with «التراجع عن الربط».

**Linking (§6.5, §7.2)**

- **FR-005**: «تم الربط» MUST ask for a confirmation, then move the request from accepted to linked through the
  §7.2 transition check, recording the link time and the admin.
- **FR-006**: Linking MUST be refused for any request that is not accepted, or is deleted, or is already linked;
  of two concurrent links only the first MUST take effect, and the second MUST see «تم ربط هذا الطلب مسبقاً».
- **FR-007**: Each successful link MUST create exactly one notification «تم ربط المشترك» for the request's
  marketer (number and name, 012) and one audit entry (who, when, request number), in the same transaction as
  the change; a refused link MUST create neither.

**Undo (§6.5, §7.2)**

- **FR-008**: «التراجع عن الربط» MUST require a reason from the fixed list (FR-016) and a confirmation, then move
  the request from linked to accepted through the §7.2 check, recording the undo time, the admin and the reason.
- **FR-009**: Undo MUST be refused for a request that is not linked; of two concurrent undos only the first MUST
  take effect, and the second MUST see «تم التراجع عن هذا الربط مسبقاً».
- **FR-010**: Each successful undo MUST create exactly one notification «تم التراجع عن الربط» with the request
  number, the subscriber's name and the reason's name, and one audit entry (who, when, request number, reason);
  a refused undo MUST create neither. The acceptance (time, admin, commission answer) MUST stay as it was.

**Counter (§4.2, §6.5, §9)**

- **FR-011**: The marketer's «تم الربط هذا الشهر: N» MUST count that marketer's requests that are linked now,
  whose current link time falls in the current Baghdad month, and that count for commission (new and additional
  always; a return only when accepted with «نعم», §6.4). Linked returns accepted with «لا» in the same month MUST
  be shown under it as «و M بلا عمولة», only when M > 0 (owner, Q1).
- **FR-012**: A request MUST count at most once, whatever the number of links and undos. Month boundaries MUST be
  Baghdad midnight on the first of the month, with times stored in UTC (Principle X). The reset at a new month
  deletes nothing.
- **FR-013**: An undone link MUST stop counting in the month it was in; when the request is linked again, it
  MUST count in the Baghdad month of the new link (the current link time), once (owner, Q2).
- **FR-014**: The marketer home MUST list the latest requests linked this month (up to 10, newest first) by
  subscriber name with a green «تم الربط» chip, each opening the request; empty when none.
- **FR-015**: The admin home «تم الربط» for today and month MUST count requests currently linked whose link time
  is in that Baghdad day or month (all marketers, counts only).

**Undo reasons**

- **FR-016**: The undo reason MUST be chosen from a fixed list with no free text (so no personal data reaches the
  notification or the audit, like the deletion reasons of 011): «لم يُربط فعلياً في SAS»، «ضُغط بالخطأ»، «ربط
  طلب آخر بدله»، «سبب آخر» (without text) (owner, Q3).

**Marketer views (§4.3, §8.4)**

- **FR-017**: The marketer's «تم الربط» tab MUST list their linked requests ordered by link time, newest first,
  each showing its link date; an undone request MUST leave it and appear in «مقبولة».
- **FR-018**: A linked request's page MUST show status «تم الربط» in green, its link date, and the link message
  with its two buttons (012); an undone request shows «مقبول (بانتظار الربط)» again.
- **FR-019**: The marketer MUST only see links of their own requests: counter, list, tab and notifications are
  filtered by the server (Principle IX). The marketer never sees who linked or undid.

**Deleted requests (§7.4)**

- **FR-020**: Link and undo MUST be refused on a deleted request; deleted requests MUST never appear in «بانتظار
  الربط» or its recent links, and MUST never count. Deleting a linked or an undone (accepted) request MUST stay
  refused.

**Statuses and history (§7.2, Principle III)**

- **FR-021**: Every allowed and every refused link and undo transition MUST be covered by tests, including link of
  a deleted, pending, rejected or linked request and undo of a non-linked one (Principle VIII).
- **FR-022**: Each link and each undo MUST be kept as its own record (request, kind, admin, time, undo reason),
  never edited or removed, so the request's link history stays readable after any number of changes.

### Key Entities

- **Request** (existing): gains its current link time and linking admin (empty when not linked). Status `linked`
  is already allowed. The acceptance time and the commission answer are untouched by link and undo.
- **Link event**: one link or one undo of one request: kind (link or undo), admin, time, and for an undo the
  reason code. Append-only; the request's history and the audit read from it.
- **Undo reason**: a fixed list of codes with Arabic labels (FR-016), mirrored in the interface, like the rejection
  and deletion reasons.
- **Notification** (existing, 012): kinds `linked` and `unlinked` are now emitted; `unlinked` carries the undo
  reason code.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin links a request found by its number in at most 3 actions from opening «بانتظار الربط»
  (search, «تم الربط», confirm).
- **SC-002**: In tests over links, undos and re-links across month boundaries, the marketer counter and the admin
  home count match the expected number in 100% of cases, and no request is ever counted twice.
- **SC-003**: After a link or an undo, the marketer's notification counter shows it within 15 seconds while the
  app is open (012), and the home counter on the next open or refresh.
- **SC-004**: 0 refused link or undo attempts (wrong status, deleted, concurrent, no permission) change a request,
  create a notification or write an audit entry, in tests.
- **SC-005**: 0 screens available to a `link`-only admin show a national ID, a family number or a card image.
- **SC-006**: Every link and undo appears in the audit log with who, when and (for undo) the reason, in 100% of
  tested cases.

## Assumptions

- The «بانتظار الربط» page holds two lists: waiting (accepted, not linked) and recent links (for the undo); the
  undo is not on the marketer's side and not in the review file, so an admin with `link` and without `review`
  can still undo.
- Recent links show every linked request (paged, newest first), not only the current month, so an older mistake
  can be undone; the paid-month lock comes with 017.
- The admin does not see the link message on this page; the row's columns are what SAS checking needs (§6.5
  does not ask for it).
- Linking needs no extra input besides the confirmation (no SAS username edit, no note).
- The marketer's home list shows up to 10 links of the current month; the full list is the «تم الربط» tab.
- The counter on the marketer home refreshes when the home is opened or refocused; the 15-second poll stays for
  the notification counter only (012).
- An archived marketer's requests keep counting in their month (their record stays, §3.6).
- `docs/system.md` 1.18 records the owner's answers (undo reasons, counter rule, re-link month) and the second
  list on «بانتظار الربط».
