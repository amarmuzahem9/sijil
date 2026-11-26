# Feature Specification: Rewards and Commissions

**Feature Branch**: `017-commissions`

**Created**: 2026-11-26

**Status**: Clarified

**Input**: User description: "الفيزة 017: المكافآت والعمولات. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام المتعلقة)
ولـ docs/features.md. انتبه لحالات الطلب وقبوله، والطلب المحذوف (011)، وعدّاد الربط (013)، والمشتركين القدامى (014)
ومشتركي SAS (015) حتى ما ينحسب لهم عمولة بالغلط، وإن أي تعديل على مبلغ ينسجّل بسجل العمليات. بعد المواصفة لخّصلي
بالعربي شنو ينحسب ولمنو ومتى، وشنو يشوف المسوّق والأدمن، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §2 (terms «تم الربط», «الشريحة»), §3.3 (permission
`commissions`: the commission report and «تم الدفع»), §4.2 (marketer home: the current tier, the expected amount
and «باقيلك N»), §6.4 (`counts_commission` on an accepted return; new and additional always count), §6.5 (a
request counts once, in the month of its current link; an undone link counts in no month; the paid-month lock),
§7.2 (statuses; only `linked` counts), §7.4 (deleted requests never count), §9 (the whole commission rule),
§10 items 5 (marketers page: month count and commission), 6 (tiers in settings) and 11 (audit log), §12.1 and
§12.2 (legacy and SAS subscribers never enter a counter or a commission), §13 (audit); constitution Principles III
(audit trail), IV (recorded values immutable; a paid commission month is locked), VIII (tested commission tiers),
IX (server-side authorization, `commissions`), X (Baghdad month boundaries).

**Builds on**: 004 (the tier table, its validation, its audited replacement «reward_tiers.updated»; permission
`commissions` already exists), 010 (the commission answer on an accepted return, fixed after the decision), 011
(only pending or rejected requests can be deleted, so a deleted request was never linked), 013 (the link time,
the link and undo records, the counter rule «counted for commission in the month of the current link» with «و M
بلا عمولة», the recent links list with the undo), 014 and 015 (legacy and SAS subscribers are not requests and
have no marketer).

**Out of scope (later features)**: the admin subscriber search and file (018); reports, exports and the
submission/link date filter (019); notifications about payment (not in §4.4); browser Push (later).

**Governance changes this feature needs** (approved by the owner on 2026-11-26): `docs/system.md` 1.23 — §4.2
(the marketer's past months list), §6.5 (a request already paid in a locked month does not count again after a
re-link), §9 (amounts come from the tiers only; «تم الدفع» for a finished month only, no undo; the report's rows and
details; the alert «تراجع بعد الدفع» and the admin home warning), §10 item 5 (marketers page: count and expected
amount, no payment), §10 new page «العمولات» (`commissions`). No constitution change.

## Clarifications

### Session 2026-11-26

- Q: A request paid in a locked month, undone, then linked again later: does it count again? → A: No. It was
  already paid; it does not count in the month of the new link and shows as «مدفوع سابقاً» (FR-016).
- Q: Manual adjustments (bonus or deduction) on an unpaid month? → A: No. Every amount comes from the tiers only
  (FR-014).
- Q: Does the marketer see past months? → A: Yes: a list of past months with count, amount and «تم الدفع» or
  «غير مدفوع», without who paid (FR-007).
- The assumptions below were approved as written.
- Q (plan review): the alert has no dismiss, so the home warning would stay for good? → A: The home warning
  covers undos after payment in the last 30 days; the report keeps every alert (FR-015).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The marketer sees their tier and expected amount (Priority: P1)

A marketer opens the home. Under «تم الربط هذا الشهر: N» (013) they now see their current tier, the rate per
subscriber, the expected amount for this month, and how many more links they need for the next tier, for
example «عندك 27، باقيلك 3 وتصير 7,000 للمشترك». In the top tier the «باقيلك» line does not show.

**Why this priority**: The expected amount is what motivates the marketer every day (§4.2); it is the visible
half of this feature and it reuses the counter that already exists.

**Independent Test**: With the default tiers (0 → 5,000; 30 → 7,000; 50 → 10,000), link 27 synthetic requests of
one marketer this month: the home shows tier 5,000, expected 135,000 and «باقيلك 3 وتصير 7,000 للمشترك». Link 3
more: tier 7,000, expected 210,000, «باقيلك 20 وتصير 10,000 للمشترك».

**Acceptance Scenarios**:

1. **Given** a marketer with 0 counted links this month, **When** they open the home, **Then** they see the first
   tier's rate, expected amount 0, and «باقيلك N» to the second tier (if there is one).
2. **Given** a marketer with 50 counted links and tiers up to 50, **When** they open the home, **Then** they see
   rate 10,000, expected 500,000 (rate × all 50, §9) and no «باقيلك» line.
3. **Given** a marketer whose month has 5 counted links and 2 returns accepted with «لا», **When** they open the
   home, **Then** the expected amount is 5 × rate and the 2 show only as «و 2 بلا عمولة».
4. **Given** an admin with `settings` changes the tiers mid-month, **When** the marketer reopens the home,
   **Then** the tier and the amount follow the new tiers.
5. **Given** a link is undone (013), **When** the marketer reopens the home, **Then** the count, tier and amount
   go down accordingly.
6. **Given** a marketer with links in September (paid) and October (unpaid), **When** they open «الأشهر
   السابقة», **Then** September shows its locked count and amount with «تم الدفع», October its count and amount
   by today's tiers with «غير مدفوع», and neither shows who paid.

---

### User Story 2 - The admin reviews the monthly commission report (Priority: P1)

An admin with `commissions` (or the main admin) opens «العمولات», picks a month (the current month by default)
and sees one row per marketer who has links in that month: name, counted links, «بلا عمولة» links, tier rate,
amount, and the payment state («غير مدفوع» or «تم الدفع» with who and when). The month's total is shown. Opening a
row lists the counted requests behind the number: request number, subscriber name, type, tower and link date, so
a disputed number can be checked.

**Why this priority**: §9 and §3.3 require this report; payment depends on it.

**Independent Test**: For two synthetic marketers with links in October and November (including a return with
«لا», an undone link and a re-link in another month), the report of each month shows exactly the counts, rates
and amounts expected from §9, and a row's details list exactly its counted requests.

**Acceptance Scenarios**:

1. **Given** marketer A has 30 counted links in October, **When** the admin opens October, **Then** A's row shows
   30, rate 7,000, amount 210,000, «غير مدفوع».
2. **Given** a request linked in October and undone in November, **When** October is unpaid, **Then** it no
   longer counts in October (013), and the row shows the lower number.
3. **Given** an archived or stopped marketer with links in the month, **When** the admin opens that month,
   **Then** the marketer still has a row, under their name (§3.6).
4. **Given** an admin without `commissions`, **When** they open the report or call it directly, **Then** the page
   is not in their menu and the server refuses (Principle IX).
5. **Given** a marketer with no link in the month, **Then** they have no row.

---

### User Story 3 - The admin marks a month paid and it is locked (Priority: P1)

After paying a marketer for a finished month, the admin presses «تم الدفع» on the marketer's row, sees the count,
rate and amount that will be locked, and confirms. From then on that row shows the locked count, rate and amount,
who marked it and when, whatever happens later to tiers or links. The action is in the audit log.

**Why this priority**: Without the lock, a tier change or an undo would change what was already paid (§9,
Principle IV).

**Independent Test**: Mark October paid for marketer A at 30 × 7,000. Change the tiers, then undo one of A's
October links: October still shows 30, 7,000, 210,000, «تم الدفع», and now an alert on that row.

**Acceptance Scenarios**:

1. **Given** an unpaid finished month, **When** the admin confirms «تم الدفع», **Then** the count, the tier (its
   lowest count and rate), the amount, the counted requests, who and when are stored and one audit entry is
   written with the marketer, the month and the amount.
2. **Given** a paid month, **When** the tiers change, **Then** the paid month keeps its rate and amount; unpaid
   months (current one included) follow the new tiers (§9).
3. **Given** two admins press «تم الدفع» on the same row, **Then** the first one counts and the second sees «تم
   تسجيل الدفع لهذا الشهر مسبقاً», with no second audit entry.
4. **Given** the current month, **When** the admin looks at its rows, **Then** «تم الدفع» is not offered until the
   month ends (Baghdad time).
5. **Given** a row with 0 counted links (only «بلا عمولة» links), **Then** «تم الدفع» is not offered.

---

### User Story 4 - An undo after payment shows as an alert, never as a silent change (Priority: P2)

An admin with `link` undoes the link of a request whose current link falls in a paid month (013 still allows it).
The paid figures do not change. The commission report shows an alert on that marketer's paid row: «تراجع بعد
الدفع» with the request number, the undo date and reason, and the difference between the paid count and the
count today. The admin decides what to do outside the system. The undone request does not count in any month, as
in 013. If it is linked again later it does not count again, because it was already paid (FR-016).

**Why this priority**: §9 requires the alert. It is rarer than the flows above.

**Independent Test**: Pay October for A with 30; undo one of A's October links in November: October still shows
30 and 210,000 and an alert «تراجع بعد الدفع» naming the request; November is unchanged.

**Acceptance Scenarios**:

1. **Given** a paid month, **When** one of its counted requests is undone, **Then** the paid row keeps its
   figures and shows the alert with the request number, undo date and reason.
2. **Given** an undo after payment in the last 30 days, **When** an admin with `commissions` opens the admin
   home, **Then** they see a short warning «يوجد تراجع بعد الدفع» linking to the report (main admin and
   `commissions` holders only). After 30 days the home warning goes; the alert stays in the report.
3. **Given** the undo happens while the month is not paid, **Then** no alert appears; the number simply goes down.
4. **Given** a request paid in October and undone in November, **When** it is linked again in November, **Then**
   it does not count in November: the marketer's home shows it under «بلا عمولة», and the November report details
   list it under «مدفوع سابقاً» with its paid month.

---

### User Story 5 - The marketers page shows the month count and commission (Priority: P3)

An admin with `marketers` sees, for each marketer on «المسوّقون», the counted links of the current month and the
expected commission (§10 item 5), without the payment controls.

**Why this priority**: Listed in §10 but secondary; the report is the place for payment.

**Independent Test**: The marketers page shows for marketer A the same count and amount as A's home and as A's
row in the current month's report.

**Acceptance Scenarios**:

1. **Given** an admin with `marketers` only, **When** they open «المسوّقون», **Then** each marketer shows this
   month's count and expected amount, and there is no «تم الدفع».

---

### Edge Cases

- **Request not linked**: drafts, pending, rejected and accepted-not-linked requests never count, in any month.
  Only status `linked` counts (§7.2, §9).
- **Return accepted with «لا»**: linked but never counted for commission; shown as «بلا عمولة» on the home and in
  the report. New and additional requests always count (§6.4). The commission answer cannot be changed (010).
- **Deleted request (011)**: only pending or rejected requests can be deleted, so a deleted request was never
  linked. The rule stays enforced anyway: a deleted request never counts, never shows in the report details.
- **Legacy (014) and SAS (015) subscribers**: they are not requests and have no marketer; they never appear in a
  count, a report row, a detail list or a payment. A Sijil request that returns a legacy or SAS subscriber to
  service is a normal return request: it counts only when accepted with «نعم» and linked. An additional request
  for a family found among legacy subscribers counts like any additional.
- **SAS import**: never changes a link, a count or a payment (§12.2).
- **Link in one month, acceptance in another**: the month is the month of the current link (§6.5).
- **Link at 23:59 / 00:00 on the first of the month (Baghdad)**: falls in the Baghdad month of the link time
  (Principle X).
- **A paid month can only go down**: linking always happens now, so no new link can fall in a finished month; the
  only change to a paid month is an undo (User Story 4).
- **Undo, then re-link in a later month**: 013 counts it in the month of the new link, unless it was already paid
  in a locked month; then it never counts again (FR-016).
- **Paid, undone, never re-linked**: the paid row keeps its figures and its alert; nothing else counts it.
- **Tier change**: applies to every unpaid month, the current one and older unpaid ones; already audited by 004
  with the old and new tiers.
- **Count exactly on a boundary** (29, 30, 49, 50): the tier is the one with the highest lowest-count not above the
  count; at 30 the rate is 7,000 for all 30.
- **Marketer archived after the month**: their row and payment stay under their name.
- **A month with no tiers change and no links**: nothing to show, nothing to pay.

## Requirements *(mandatory)*

### Functional Requirements

**What counts (§6.4, §6.5, §7.2, §7.4, §9, §12)**

- **FR-001**: A marketer's count for a month MUST be the number of their requests that are linked now, whose
  current link time falls in that Baghdad month, and that count for commission (new and additional always; a
  return only when accepted with «نعم»). This is the 013 counter rule, applied to any month, not only the current
  one.
- **FR-002**: Drafts, pending, rejected, accepted-not-linked and deleted requests MUST never count. Legacy and SAS
  subscribers MUST never count, appear in a report row or detail, or be paid. A request MUST count at most once
  over all months. A request stored in a payment (FR-012) MUST NOT count in any later month, even after an undo
  and a new link (FR-016).
- **FR-003**: Linked returns accepted with «لا», and linked requests already paid in an earlier month (FR-016),
  MUST be shown separately as «بلا عمولة» on the marketer's side and MUST NOT change the tier or the amount.

**Tier and amount (§9)**

- **FR-004**: The tier of a count MUST be the tier with the highest lowest-count that is not above the count. The
  amount MUST be the tier rate × the whole count (no marginal steps).
- **FR-005**: An unpaid month (the current one included) MUST always use the tiers as they are now. A paid month
  MUST use the tier, rate, count and amount stored when it was marked paid, forever.

**Marketer home (§4.2)**

- **FR-006**: The home MUST show, for the current month: the tier rate, the expected amount and, when a higher
  tier exists, «عندك N، باقيلك K وتصير R للمشترك». All values are computed by the server from the marketer's own
  requests only (Principle IX).
- **FR-007**: The marketer MUST be able to open «الأشهر السابقة» from the home: one line per finished month in
  which they had a linked request or a payment, newest first, with count, «بلا عمولة» count, rate, amount and
  «تم الدفع» or «غير مدفوع». A paid month MUST show its locked figures; an unpaid month its figures by today's
  tiers. The marketer MUST NOT see who paid, when, or any alert (owner, Q3).

**Commission report (§3.3, §9)**

- **FR-008**: A page «العمولات» MUST be available to the main admin and to admins with `commissions`, and the
  server MUST refuse every other caller. It MUST offer a month picker (current month by default, any earlier
  month that has links or payments).
- **FR-009**: For the chosen month it MUST show one row per marketer with at least one linked request in that
  month (counted or «بلا عمولة»), or a payment: marketer name, count, «بلا عمولة» count, tier rate, amount,
  payment state (who, when). It MUST show the month total of amounts.
- **FR-010**: Opening a row MUST list the requests behind the count (request number, subscriber name, type,
  tower, link date), and separately the «بلا عمولة» ones and the «مدفوع سابقاً» ones (with their paid month).
  For a paid row it MUST list the requests stored at payment. It MUST NOT show national IDs, family numbers, phones or card images (Principle II).

**«تم الدفع» and the lock (§9, Principle IV)**

- **FR-011**: «تم الدفع» MUST be offered only on a row of a finished Baghdad month with a count above 0, and only
  to the main admin and `commissions` holders. It MUST need a confirmation that shows the count, rate and amount.
- **FR-012**: On confirmation the system MUST store, for that marketer and month: count, tier (lowest count and
  rate), amount, the list of counted requests, who and when. Only one payment per marketer and month; a second
  attempt MUST be refused with «تم تسجيل الدفع لهذا الشهر مسبقاً» and change nothing.
- **FR-013**: A payment MUST NOT be edited or removed (no undo of «تم الدفع»).
- **FR-014**: Every amount MUST come from the tiers only (FR-004, FR-005). There is no manual adjustment, bonus or
  deduction (owner, Q2).

**Undo after payment (§6.5, §9)**

- **FR-015**: Undoing the link of a request counted in a paid month MUST stay allowed (013) and MUST NOT change the
  paid figures. The paid row MUST show an alert «تراجع بعد الدفع» with the request number, undo date, undo reason,
  and the paid count against today's count; it stays in the report for good. The main admin's home and the home of
  `commissions` holders MUST show «يوجد تراجع بعد الدفع» while there is an undo after payment within the last 30
  days (owner, 2026-11-26).
- **FR-016**: A request stored in a payment, then undone, then linked again MUST NOT count in the month of the new
  link: it was already paid. It MUST show as «بلا عمولة» on the marketer's home and as «مدفوع سابقاً» (with its
  paid month) in the report details. This narrows the 013 re-link rule (§6.5) to requests not yet paid (owner,
  Q1).

**Audit (§10 item 11, §13, Principle III)**

- **FR-017**: Every change that affects an amount MUST be in the audit log with who, when and before/after: tier
  changes (already, 004, old and new tiers) and each «تم الدفع» (marketer, month, count, rate, amount). Audit
  entries MUST NOT carry subscriber personal data.
- **FR-018**: Refused actions (no permission, current month, already paid, zero count) MUST change nothing and
  write no payment.

**Marketers page (§10 item 5)**

- **FR-019**: «المسوّقون» MUST show for each marketer this month's count and expected amount, computed by the same
  rule as the home and the report, without payment controls.

**Tests (Principle VIII)**

- **FR-020**: The tier rule, the count rule across statuses, request types, deletion, legacy and SAS records, undo
  and re-link across months, the payment lock, the alert, and every permission refusal MUST be covered by tests;
  the home, the marketer's past months, the report and the marketers page MUST give the same number for the same
  marketer and month.

### Key Entities

- **Reward tier** (existing, 004): lowest count and rate per subscriber. Changes are audited.
- **Request** (existing): status, type, commission answer (010), current link time (013). Not changed by this
  feature.
- **Commission payment**: one per marketer and Baghdad month: count, tier lowest count, rate, amount, paid by,
  paid at. Append-only, never edited.
- **Paid request**: a request counted in a payment (payment, request). Lets the report show what was paid and lets
  the system know a request was already paid (FR-016, User Story 4). A request is in at most one payment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In tests over statuses, request types, deletions, legacy and SAS records, undos and re-links across
  month boundaries, the count and the amount match §9 in 100% of cases, and no request is counted twice.
- **SC-002**: For any marketer and month, the home (or past months list), the report and the marketers page show
  the same count and amount in 100% of tested cases; 0 requests are paid twice.
- **SC-003**: After «تم الدفع», 0 tier changes or undos change the paid count, rate or amount, in tests.
- **SC-004**: An admin finds a marketer's month and marks it paid in at most 3 actions after opening «العمولات»
  (pick month, «تم الدفع», confirm).
- **SC-005**: Every «تم الدفع» and every amount-affecting change appears in the audit log with who, when and the
  amount, in 100% of tested cases; 0 audit entries carry a national ID, family number or phone.
- **SC-006**: 0 callers without `commissions` (and not main admin) can read the report or mark a payment.

## Assumptions

- «تم الدفع» is for a finished month only; the current month is paid after it ends (Baghdad time).
- «تم الدفع» has no undo; the confirmation shows what will be locked. A mistaken payment is fixed outside the
  system and noted by the admin.
- A row exists only for marketers with links in the month; marketers with nothing linked are not listed.
- The alert «تراجع بعد الدفع» stays on the paid row as history; it has no «dismiss» action. The home warning
  covers the last 30 days only.
- The rate per subscriber is the tier's, independent of the plan or its prices.
- Paying a marketer sends no notification (§4.4 does not list one).
- The report has no export; exports come with 019.
- The admin home warning is shown only to the main admin and `commissions` holders.
- The marketer's past months list has no per-request details; their «تم الربط» tab already lists links by date.
- `docs/system.md` 1.23 records the answers and these defaults.
