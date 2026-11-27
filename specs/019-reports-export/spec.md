# Feature Specification: Reports and Export

**Feature Branch**: `019-reports-export`

**Created**: 2026-11-27

**Status**: Clarified

**Input**: User description: "الفيزة 019: التقارير والتصدير. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام المتعلقة) ولـ
docs/features.md. انتبه إن التصدير أخطر باب لتسريب البيانات: الرقم الوطني والعائلي والصور ما تطلع إلا لمن يحق له، وكل تصدير
ينسجّل بسجل العمليات (منو وشنو ومتى). وحدد شنو تقدر صلاحية reports تشوف وتصدّر، لأننا أجّلنا هذا القرار من 018. والمسوّق
يصدّر طلباته بس إذا سمحنا إله أصلاً. والتقارير تعتمد أرقام العمولات المقفولة بـ 017 مثل ما هي، وتبقى سريعة ويّا آلاف
المشتركين. بعد المواصفة لخّصلي بالعربي شنو التقارير، وشنو ينصدّر وبأي صيغة، ومنو يقدر، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §3.1 (the marketer sees only their own requests), §3.3 (permission
`reports`: reports, export and import; `commissions`: the commission report), §7.2 (statuses and colors), §7.4
(deleted requests keep only their kept fields), §9 (commission figures; a paid month is locked; "the export comes in
019"), §10 items 4, 8 and 13 (who sees identity numbers and images, decided in 018; «التقارير والتصدير»; «العمولات»),
§11 (filters, submission date or link date, the ZIP with `requests.xlsx` and `cards/`), §13 (export is audited;
images only through the server for an account entitled to them), §15 (backups); constitution Principles II
(identity documents), III (audit), IV (locked commission figures), IX (server-side authorization), X (Baghdad days
and months).

**Builds on**: 004 (areas, towers, plans), 010 (decisions, request images), 011 (deleted requests and their kept
fields), 013 (link time and link history), 017 (commission figures, payments, locked months), 018 (national ID,
family number, card fields and images are for the main admin and `review` only; the subscriber file).

**Out of scope (later features)**: a ministry template (§11: none for now); scheduled or e-mailed reports; exports
of legacy or SAS subscribers (imported data, not requests; 018 shows them); charts; any change to commission rules
(017) or to who sees what on screen (018).

**Governance changes**: recorded in `docs/system.md` 1.25 (§9 the commission export, §11 who sees and exports what,
the columns, the opt-in, limits and keeping time, §13 the export audit entries).

## Clarifications

### Session 2026-11-27

- Q: Who may export national ID, family number, card fields and images? → A: the main admin, and admins with both
  `reports` and `review` (FR-009).
- Q: Can a marketer export their own requests? → A: no, not in this feature (FR-014).
- Q: Does the reports page show commission amounts to `reports` without `commissions`? → A: no; the reports page
  shows counts only, amounts stay on «العمولات» (FR-016).
- The assumptions below (week from Saturday, 24 hours, 5,000 limit, no ZIP password, no legacy/SAS export) were
  approved as written.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The admin filters the requests report (Priority: P1)

An admin with `reports` (or the main admin) opens «التقارير والتصدير», picks a period (this week, this month, or
from–to), chooses whether the period applies to the submission date or the link date (§11), and may narrow by area,
tower, marketer, plan, status and type. The page shows the matching requests (number, name, tower, plan, marketer,
status with its color, type, submission date, link date) with their total, and summary counts by status, by tower
and by marketer. Opening a row opens the request's file under 018's rules.

**Why this priority**: §11 is the base of every export; admins have no way today to look at requests by period.

**Independent Test**: With synthetic requests across two towers, two marketers and three statuses in October and
November, filtering "October, by link date, tower A" lists exactly the requests linked in October in tower A, and
each summary adds up to the list total.

**Acceptance Scenarios**:

1. **Given** a request submitted on 31 October 23:30 Baghdad time and linked on 2 November, **When** the admin filters
   October by submission date, **Then** it is listed; **When** they filter October by link date, **Then** it is
   not.
2. **Given** "this week" and "this month", **Then** they follow Baghdad time (the week starts on Saturday, see
   Assumptions).
3. **Given** a request that is not linked now, **When** the filter is by link date, **Then** it does not appear.
4. **Given** a deleted request that matches the filters, **Then** it appears as «محذوف» with its kept fields only
   (§7.4), and no name.
5. **Given** several filters at once, **Then** only requests matching all of them are listed, and the summaries
   match the list.
6. **Given** an admin with `reports` and without `review`, **Then** no national ID, family number, card field or
   image appears anywhere on the page (018).
7. **Given** a marketer, or an admin without `reports`, **When** they open the page or call it directly, **Then**
   the server refuses.

---

### User Story 2 - The admin exports the filtered requests (Priority: P1)

From the same filters, the admin presses «تصدير». The system builds a ZIP holding `requests.xlsx` (one row per
request, Arabic headers). Only when the admin is entitled (FR-009) and ticks «تضمين الرقم الوطني والعائلي والصور»
does the sheet carry the identity columns and the ZIP a `cards/` folder with `T3C-1001-front.jpg` and
`T3C-1001-back.jpg`, linked from the sheet by relative links (§11). The admin downloads it. The audit log records the
export: who, when, the filters, which request numbers, and whether identity data and images were included.

**Why this priority**: §11 asks for this export; §13 requires it to be audited; it is the riskiest way data leaves
the system.

**Independent Test**: As the main admin, export a filter of 3 synthetic requests with the box ticked: the ZIP has a
sheet of 3 rows and 6 images named by request number, each link opens its image in the extracted folder, and one
audit entry lists the 3 request numbers. As a `reports`-only admin, the same export has no identity columns, no
`cards/` folder and no option to tick.

**Acceptance Scenarios**:

1. **Given** an export of N requests, **Then** the sheet has N rows in the report's order, with the columns of
   FR-007.
2. **Given** the box is not ticked (the default), **Then** the file has no national ID, family number, card field
   or image, whoever asked.
3. **Given** a deleted request in the filter, **Then** its row holds the kept fields and «محذوف» only, and no images.
4. **Given** an export, **Then** one audit entry «تصدير طلبات» is written (FR-011) and each download adds
   «تنزيل تصدير»; neither holds a name, phone, national ID or family number.
5. **Given** filters that match no request, **Then** no file is made and the admin sees «لا توجد طلبات بهذه
   الفلاتر».
6. **Given** a subscriber name or address beginning with «=», «+», «-» or «@», **Then** it opens in the sheet as
   plain text and never runs as a formula.
7. **Given** a large export, **Then** the app stays usable while it is built, and the admin sees «جارٍ التجهيز»
   then «تنزيل».
8. **Given** another admin, **When** they try to download someone else's export, **Then** the server refuses.

---

### User Story 3 - The commission report is exported with its locked figures (Priority: P2)

On «العمولات» (017), an admin with `commissions` (or the main admin) presses «تصدير» for the chosen month and gets a
sheet: one row per marketer (count, «بلا عمولة», tier rate, amount, paid or not, who paid and when, the «تراجع بعد
الدفع» notes) with the month total, and a second sheet with the requests behind each count (number, name, type,
tower, link date, «بلا عمولة», «مدفوع سابقاً» with its month). The figures are exactly those on the screen: locked
for a paid month, today's tiers for an unpaid one.

**Why this priority**: §9 moved this export to 019; the user asked that reports rely on 017's locked figures as they
are, so the export must never recompute a paid month.

**Independent Test**: For a paid October and an unpaid November, change the tiers, then export both months: every
number in the sheets equals «العمولات» for each marketer.

**Acceptance Scenarios**:

1. **Given** a paid month and a later tier change, **Then** the export keeps the paid figures (017).
2. **Given** an undo of a link after payment, **Then** the paid row keeps its figures and carries the «تراجع بعد
   الدفع» note, as on screen.
3. **Given** an archived or stopped marketer, **Then** their row stays under their name.
4. **Given** any commission export, **Then** it has no national ID, family number, phone or image (§9), and it is
   audited as «تصدير عمولات» with who, when and the month.

---

### User Story 4 - The marketer has no export (Priority: P3)

A marketer keeps their request list (§4.3) and gets no export in this feature (FR-014, owner decision 2026-11-27).

**Why this priority**: the user asked to decide it explicitly; it guards against data leaving on a phone.

**Independent Test**: Logged in as a marketer, the app shows no export button, and direct calls to the report,
export and download endpoints are refused.

---

### Edge Cases

- **Period boundaries**: «من» and «إلى» are whole Baghdad days, both included; 23:59 on the last day is in, 00:00
  the next day is out (Principle X).
- **Undone links**: the current link time counts (013); a request whose link was undone has no link date until it
  is linked again.
- **Drafts**: never appear in reports or exports (they were not submitted).
- **Filters with no match**: the page shows 0 and «تصدير» is not offered.
- **Over the limit**: an export above the limit (Assumptions) is refused with «ضيّق الفلاتر، الحد 5,000 طلب».
- **An image file missing on disk**: the export completes; the cell reads «الصورة غير متوفرة» and the audit entry
  counts missing images.
- **Archived marketer**: still offered in the marketer filter; their requests stay under their name (§3.6).
- **Deactivated or renamed tower, area or plan**: rows show what the request stored (§5.3, §6 item 6).
- **Permission removed while an export is being built or before download**: the download checks again and is
  refused; a file built with identity data for someone who lost `review` is removed, not served.
- **A request deleted after the export was built**: its sheet row stays as built (removed at the normal time,
  FR-013), but its erased images are no longer sent in a later download (§7.4; plan R6).
- **Two admins export at the same time**: each gets only their own file.

## Requirements *(mandatory)*

### Functional Requirements

**Who (§3.3, §10, Principle IX)**

- **FR-001**: «التقارير والتصدير» and its export MUST be open to the main admin and to admins with `reports`; the
  server MUST refuse every other caller, including marketers.
- **FR-002**: What a `reports` admin sees on the report page MUST follow 018: name, phone, username and the request's
  other fields, and no national ID, family number, card field or image unless they also hold `review`.

**The requests report (§11)**

- **FR-003**: Filters MUST be: period (this week, this month, from–to in Baghdad days), date kind (submission or
  link), area, tower, marketer (archived included), plan, status, type. Only the period is required.
- **FR-004**: The report MUST list the matching submitted requests (number, name, tower «اسم البرج (رمز البرج)»,
  plan, marketer, status with its color, type, submission date, link date), 50 per page, with the total, newest
  first by the chosen date kind.
- **FR-005**: The report MUST show summary counts for the filter: by status, by tower and by marketer, each adding up
  to the total.
- **FR-006**: Deleted requests MUST show as «محذوف» with their kept fields only (§7.4).

**The requests export (§11, §13)**

- **FR-007**: The export MUST be a ZIP holding `requests.xlsx` with Arabic headers and one row per request in report
  order: number, full name, phone, username, area, tower, plan, trial and second price, marketer, type, status,
  submission date, acceptance date, link date, address, nearest landmark, location link, rejection reason, deletion
  mark and reason. Identity columns and images only per FR-008 and FR-009.
- **FR-008**: National ID, family number, the other card fields and the `cards/` images MUST be left out unless the
  requester ticks «تضمين الرقم الوطني والعائلي والصور» for that export; the box starts unticked and is shown only
  to those FR-009 allows.
- **FR-009**: Only the main admin and admins holding both `reports` and `review` MAY tick the box and export national
  ID, family number, card fields and card images (the same rule as 018). A `reports`-only admin MUST NOT see the box,
  and the server MUST refuse an export with identity data from them.
- **FR-010**: Images, when included, MUST be in `cards/` named `T3C-<number>-front.jpg` and `T3C-<number>-back.jpg`,
  and the sheet MUST link to them by relative paths that work in the extracted folder.
- **FR-011**: Every export MUST write one audit entry «تصدير طلبات» with who, when, the filters, the row count, the
  list of exported request numbers, whether identity data and images were included, and the number of missing
  images. The entry is written when the file becomes ready, which is when data leaves into a file; an export that
  fails before that writes none, since no data left. Every download MUST write «تنزيل تصدير» with who and when, and
  every card image sent in a download MUST be recorded in the image access log like any other image open (§13,
  Principle II). No entry MAY hold a name, phone, national ID, family number or image (§13, Principle III).
- **FR-012**: An export MUST contain only what its requester may see when it is built; its download MUST be refused
  to anyone but the requester and re-check the requester's permissions. Text from subscribers MUST open as plain
  text in the sheet, never as a formula.
- **FR-013**: An export file MUST be removed from the server after the time limit (Assumptions), MUST NOT go into
  the backups, and MUST NOT be reachable except through the download that FR-012 guards.

**The marketer**

- **FR-014**: A marketer MUST have no export in this feature: no button in their app, and the server MUST refuse
  every export or download call from a marketer account. Their list (§4.3) stays as it is.

**Commission figures (§9, 017)**

- **FR-015**: «العمولات» MUST offer «تصدير» of the chosen month to the main admin and to `commissions` admins: a
  sheet with the marketer rows and the month total, and a sheet with the requests behind each count, both exactly as
  on screen: locked figures for a paid month, today's tiers for an unpaid one. No national ID, family number, phone
  or image. Audited as «تصدير عمولات» (who, when, month).
- **FR-016**: «التقارير والتصدير» MUST show counts only and no commission amount, tier rate or payment, to anyone;
  amounts are seen and exported only on «العمولات» (FR-015).

**Speed**

- **FR-017**: The report and its summaries MUST stay fast with tens of thousands of requests (SC-001), and building
  an export MUST NOT slow the app for other users (SC-002).

### Key Entities

- **Request** (existing): its stored values from submission, decision, link and deletion; its images.
- **Report filter**: period, date kind, area, tower, marketer, plan, status, type.
- **Export**: requester, kind (requests or commissions), filters or month, row count, identity included or not,
  state (preparing, ready, failed, removed), file, created and removed times. Never visible to another user.
- **Audit entry** (existing): «تصدير طلبات», «تصدير عمولات», «تنزيل تصدير», with request numbers and counts, no
  personal data.
- **Commission figures** (existing, 017): payments and today's tiers, read only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With 20,000 requests, a filtered report page with its summaries appears in under 2 seconds.
- **SC-002**: An export of 1,000 requests with images is ready in under 2 minutes, while other users' pages keep
  answering in their usual time.
- **SC-003**: In tests, 0 exports carry identity data or images for a requester FR-009 does not allow, or for an
  export where the box was not ticked; 0 downloads succeed for anyone but the requester; 0 export calls succeed for a
  marketer; 0 commission amounts appear on the reports page.
- **SC-004**: 100% of exports and downloads appear in the audit log with their request numbers, and 0 audit entries
  carry a name, phone, national ID or family number.
- **SC-005**: For every marketer and month tested, the exported commission figures equal «العمولات» in 100% of cases,
  also after a tier change.
- **SC-006**: 0 export files remain on the server after their time limit, and 0 appear in a backup.

## Assumptions

- "This week" starts on Saturday in Baghdad time; "this month" is the Baghdad calendar month.
- An export is built in the background; a ready file is kept for 24 hours, then removed. It may be downloaded again
  within that time (each download audited).
- One export holds at most 5,000 requests; above that the admin narrows the filters.
- An admin has at most one export being built at a time.
- Each admin sees a list of their own exports from the last 7 days (state, row count, with or without identity
  data); the list holds no subscriber data, and no admin sees another admin's exports.
- The ZIP has no password; protection comes from who may export, the opt-in, the audit and the short keeping time.
- Sheet dates are Baghdad time; money as whole numbers in IQD; the location as a map link from the stored pin.
- Drafts, OTP codes, card reader readings and the audit log are never exported; legacy and SAS subscribers are not
  exported in this feature.
- Export files are not in backups; the data they copy already is.
- `docs/system.md` 1.25 records the answers.
