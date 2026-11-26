# Feature Specification: Subscriber File and Search

**Feature Branch**: `018-subscriber-file-search`

**Created**: 2026-11-26

**Status**: Clarified

**Input**: User description: "الفيزة 018: ملف المشترك والبحث. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام المتعلقة)
ولـ docs/features.md. انتبه إن الملف يجمع الطلبات والمشتركين القدامى (014) ومشتركي SAS (015) لنفس الشخص، وإن البحث
يحترم الصلاحيات وما يكشف الرقم الوطني والعائلي والصور إلا لمن يحق له، وإن المسوّق يشوف مشتركيه بس، وإن السرعة تبقى
زينة ويا آلاف المشتركين. بعد المواصفة لخّصلي بالعربي شنو يبين بالملف، ومنو يبحث وبشنو، وشنو الأسئلة اللي تحتاج
قراري."

**System document references**: `docs/system.md` §3.1 (the marketer sees only their own requests and nothing about
another subscriber), §3.3 (permissions `review`, `link`, `reports`), §4.3 (the marketer's own search, already
built), §6.1 and §6.2 (what makes two records the same person or the same family, and how values are compared),
§6.4 (the review file and its linked records), §7.4 (deleted requests: «سجل محذوف», found by number only), §8.1
(phone normalization), §10 item 4 (page «المشتركون»: search by name, phone, national ID, family number and
username; each subscriber's file with images, requests and history; the «غير مكتمل» mark), §12.1 and §12.2
(legacy and SAS subscribers, what they hold, «حسب آخر استيراد»), §13 (images only through the server with a
permission, every open logged); constitution Principles II (identity documents), III (audit), IX (server-side
authorization).

**Builds on**: 010 (the review file and its linked records; request images and their access log, `review`
only), 011 (deletion and «سجل محذوف»), 013 (the `link` page shows no identity numbers and no images), 014
(legacy subscribers, their images, «غير مكتمل», «بيانات إضافية»), 015 (SAS subscribers, «حسب آخر استيراد»,
«غير موجود في آخر ملف»), 017 (commission data is not part of the file).

**Out of scope (later features)**: reports, filters by date and exports (019); browser Push (later); any change to
the check engine or to how records are matched at submission (008–015).

**Governance changes this feature needs** (approved by the owner on 2026-11-26): `docs/system.md` 1.24 — §10 item 4
(the file of one record with its linked records; who sees identity numbers and images and who searches by them;
the file is read-only; what the search finds and how). No constitution change.

## Clarifications

### Session 2026-11-26

- Q: What is "the subscriber's file"? → A: The file of one record, with every record linked to it listed under it
  with the reason of each link, like the review file. No merged person (FR-007).
- Q: Who sees national ID, family number, card fields and images, and who searches by them? → A: The main admin and
  `review` see and search by all. `link` and `reports` see none of them and cannot search by national ID or family
  number (FR-009).
- Q: Read-only or edits? → A: Read-only. Corrections are a later feature with their own rules (FR-010).
- The assumptions below were approved as written.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The admin finds a subscriber (Priority: P1)

An admin with `review`, `link` or `reports` (or the main admin) opens «المشتركون» and types a name, a phone, a
national ID, a family number, a username or a request number. Results come from all three sources — Sijil
requests, legacy subscribers, SAS subscribers — in one list, each row marked with its source («طلب سِجلّ»,
«مشترك قديم», «مشترك SAS»), the name, the tower, the phone and the status (request status, legacy status text, or
SAS «حسب آخر استيراد»). Opening a row opens its file.

**Why this priority**: The page has been a placeholder since 001; admins today can only open a request by its number
(011). Finding a person across all sources is the base of the file.

**Independent Test**: With synthetic data — a request, a legacy subscriber with the same family number, and a SAS
subscriber with the same phone — searching by that phone returns the request and the SAS row; searching by the
family number returns the request and the legacy row; searching by part of the name returns all rows that carry
it.

**Acceptance Scenarios**:

1. **Given** a phone written as `0780 123 4567`, `+964 780 123 4567` or in Arabic digits, **When** the admin
   searches, **Then** the match is the same as for `07801234567` (§8.1), across all three sources, including the
   phone inside a SAS username (§12.2).
2. **Given** a family number written with spaces, lower case or `O` for `0`, **When** the admin searches, **Then**
   it matches by the comparison key (§6.2).
3. **Given** a request number with or without «T3C-», or a legacy number «T3C-001», **When** the admin searches,
   **Then** the request or legacy subscriber with that number is found.
4. **Given** a deleted request, **When** the admin searches by its phone or name, **Then** it is not found; **When**
   they search by its number, **Then** it shows as «سجل محذوف» with its number only (§7.4).
5. **Given** a query shorter than the minimum (FR-004), **Then** no search runs and the page asks for more.
6. **Given** a marketer or an admin without `review`, `link` or `reports`, **When** they open the page or call it
   directly, **Then** the menu has no entry and the server refuses.

---

### User Story 2 - The admin reads the subscriber's file (Priority: P1)

The file of a record shows the person as Sijil knows them: the record itself and every record linked to it by the
same rules as the check (§6.1) — the same person (national ID and family number together, or the same phone), and
the same family (family number only). For each: source, name, phone, username, tower, registration date, status,
and its requests with their history (submitted, accepted or rejected with reason, linked, undone, deleted). The
«غير مكتمل» mark shows when a record misses documents. National ID, family number, card fields and card images
show only to admins entitled to them (FR-009).

**Why this priority**: §10 item 4 asks for the file; it answers "who is this person and what did we do with them"
in one place.

**Independent Test**: Open the file of a request whose person also has an older rejected request, a legacy row with
the same family number, and a SAS row with the same phone: the file lists the four records, each with its link
reason («نفس الشخص», «نفس الهاتف», «نفس العائلة»), and the request history in time order.

**Acceptance Scenarios**:

1. **Given** a request with a pin, an acceptance and a link, **When** the file opens, **Then** its history lists
   submitted, accepted (by whom), linked, in time order, from the stored facts.
2. **Given** a legacy subscriber without images, **When** its file opens, **Then** it shows «غير مكتمل».
3. **Given** a SAS subscriber, **When** its file opens, **Then** it shows the expiry «حسب آخر استيراد», the
   package, and «غير موجود في آخر ملف» when set (§12.2).
4. **Given** an admin with `link` only, **When** they open any file, **Then** they see no national ID, family number,
   card fields or images, whatever the source (FR-009).
5. **Given** an admin with `review`, **When** they open a card image from the file, **Then** it opens through the
   server and the open is logged (§13).

---

### User Story 3 - The marketer stays within their own requests (Priority: P1)

The marketer keeps the search and request pages they already have (§4.3). This feature gives them nothing new to
see: no access to «المشتركون», to any file, to legacy or SAS records, or to another marketer's requests.

**Why this priority**: §3.1 is a hard rule; a new cross-source search is the most likely place to break it.

**Independent Test**: As a marketer, every new route answers 403, and the existing own-request search returns
nothing from legacy, SAS or another marketer for a value that exists there.

**Acceptance Scenarios**:

1. **Given** a phone that belongs to a SAS subscriber and to another marketer's request, **When** the marketer
   searches in «الطلبات», **Then** nothing is found.

---

### Edge Cases

- **Thousands of records**: about 20,000 SAS rows, a few hundred legacy rows and a few thousand requests; a search
  answers quickly (SC-001) and returns a capped, paged list.
- **Common names**: a name search that matches hundreds of rows shows the first page and the total, newest first.
- **Arabic spelling**: «احمد» and «أحمد», «ة» and «ه», «ى» and «ي» find each other; diacritics and tatweel are
  ignored (as §5.1 strips them on input).
- **SAS username phone differs from its phone column**: both phones find it (§12.2).
- **Legacy without phone or with an invalid one**: found by name, family number or legacy number only.
- **Legacy status «ملغي» or «مرفوض»**: shown with its status; it is not counted in the check (§12.1) but it is a
  record and is found.
- **Rejected request**: found and shown with its reason; it does not count in the check (§6.1).
- **Deleted request**: never found except by its number; in a file it shows as «سجل محذوف» with its number only.
- **Archived marketer**: their requests still show under their name (§3.6).
- **A person with no national ID anywhere** (legacy only): linked by family number and phone only (§6.1 notes).
- **Searching a national ID as a `link`-only admin**: refused with the message of FR-009, whether the number exists
  or not.
- **An admin's permissions change while the file is open**: the next request follows the new permissions (the
  server checks each request, §10).

## Requirements *(mandatory)*

### Functional Requirements

**Who (§10 item 4, Principle IX)**

- **FR-001**: «المشتركون» MUST be open to the main admin and to admins with `review`, `link` or `reports`; the server
  MUST refuse every other caller, marketers included.
- **FR-002**: The marketer MUST get no new route or screen; their own-request search (§4.3) MUST keep returning only
  their own requests (§3.1).

**Search (§10 item 4, §6.2, §8.1)**

- **FR-003**: One search box MUST find across Sijil requests, legacy subscribers and SAS subscribers by: name
  (part of the full name), phone (§8.1, both SAS phones), national ID (digits, Arabic digits converted), family
  number (comparison key), username (case-insensitive) and request or legacy number.
- **FR-004**: A name search MUST need at least 3 characters; a phone, national ID or family number search MUST be
  exact after normalization; partial phone or identity-number searches MUST NOT be offered.
- **FR-005**: Results MUST be one list, each row with its source, name, tower, phone, status and registration date,
  newest first, paged (50 per page) with the total.
- **FR-006**: Deleted requests MUST be found only by their request number and shown as «سجل محذوف» with the number
  only (§7.4).

**The file (§10 item 4, §6.1, §6.4)**

- **FR-007**: A file MUST be the file of one record (a request, a legacy subscriber or a SAS subscriber). Under it
  MUST be listed every record linked to it by the §6.1 rules, each with its link reason: «نفس الشخص» (national ID
  and family number together), «نفس الهاتف» (any of its phones), «نفس العائلة» (family number only). Records MUST
  NOT be merged into one person. Opening a linked record MUST open its own file (owner, Q1).
- **FR-008**: Each record in the file MUST show its source, name, phone, username, tower, registration date, status,
  «غير مكتمل» when it misses documents, and for a request its history from the stored facts: submitted, accepted
  or rejected (who, when, reason), pins (that a number was pinned, not the number), linked and undone (who, when,
  reason), deleted (who, when, reason). Legacy records show their «بيانات إضافية» (§12.1); SAS records their
  expiry «حسب آخر استيراد», package, last online and «غير موجود في آخر ملف» (§12.2).
- **FR-009**: The main admin and admins with `review` MUST see the national ID, family number, card fields and card
  images in the file, and MUST be able to search by national ID and family number. An admin with `link` or
  `reports` and without `review` MUST receive none of these values in any search result or file, and a search by
  national ID or family number from them MUST be refused with «البحث بالرقم الوطني أو العائلي يحتاج صلاحية
  المراجعة» — so it reveals nothing about who exists. The «نفس الشخص» and «نفس العائلة» link reasons still show to
  them, without the numbers (owner, Q2).
- **FR-010**: The file MUST be read-only: no field of any record can be changed from it (owner, Q3).

**Images and audit (§13, Principles II and III)**

- **FR-011**: Card images MUST open only through the server after the permission check, and every open from the file
  MUST be logged like the review file's opens (who, when, which image, which record).
- **FR-012**: Opening a file MUST NOT write subscriber data to the application logs; logs keep the record reference
  only.

**Speed**

- **FR-013**: Search and file MUST stay fast with about 20,000 SAS rows, a few hundred legacy rows and a few thousand
  requests (SC-001, SC-002).

### Key Entities

- **Request** (existing): a Sijil request, its decision, pins, links and deletion mark.
- **Legacy subscriber** (existing, 014): imported row with legacy number, names, family number, phone, status text,
  extra data, images, «غير مكتمل».
- **SAS subscriber** (existing, 015): imported row with username, names, phones, tower, expiry, package, last online,
  «غير موجود في آخر ملف».
- **Search result row**: source, record reference, name, tower, phone, status, registration date (no identity
  numbers unless entitled).
- **File**: one record with its linked records and the reason of each link (FR-007), and each request's history.
- **Image access log entry** (existing): who opened which image of which record, when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With about 20,000 SAS rows, 500 legacy rows and 5,000 requests, 95% of searches return their first page
  in under 1 second.
- **SC-002**: A file with up to 20 linked records opens in under 1 second.
- **SC-003**: An admin finds a known subscriber by phone and opens the file in at most 3 actions (type, search,
  open).
- **SC-004**: In tests, 0 responses to an admin not entitled by FR-009 carry a national ID, family number, card
  field or image link, and 0 responses to a marketer carry any legacy, SAS or other-marketer data.
- **SC-005**: 100% of image opens from the file are in the access log with who, when and the record.

## Assumptions

- The search box guesses what was typed: 12 digits → national ID; a phone shape → phone; the family-number shape
  (4 digits, a Latin letter, 13 characters) → family number; «T3C-» or digits under 12 → request or legacy number;
  a username shape → username; otherwise a name. One query, one kind.
- Arabic name matching folds أ/إ/آ → ا, ة → ه, ى → ي, removes diacritics and tatweel, and matches any part of
  the full name.
- A request's history is built from what is already stored (decision, pins, links, deletion), not from the audit
  log text; the audit log stays for the main admin (§10 item 11).
- A SAS subscriber has no documents in Sijil, so it shows «بلا مستمسكات في سِجلّ» rather than «غير مكتمل»; a
  legacy subscriber missing an image shows «غير مكتمل» (§12.1); a request always has its two images.
- Commission data (017) is not shown in the file.
- The «بانتظار الربط» SAS hint in `docs/features.md` stays a separate idea; it is not part of this feature.
- A `link`-only or `reports`-only admin sees the phone, username and name (as on «بانتظار الربط»), but no card image,
  national ID or family number.
- `docs/system.md` 1.24 records the answers.
