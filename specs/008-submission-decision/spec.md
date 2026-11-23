# Feature Specification: Request Check and Decision at Submission

**Feature Branch**: `008-submission-decision`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "008: فحص الطلب والقرار. ارجع لـ docs/system.md وللقسم 008 بـ features.md، وكمّل من نقطة
الربط precheck_for_otp اللي تركناها بـ 007 لفحص «الهاتف مستخدم». بعد ما تكتب المواصفة لخّصلي بالعربي شنو الفحوصات
والقرارات، وشنو الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §5.4 item 2 (phone checked before a code is sent),
§5.5 (submit only when complete and verified), §6 (check on all sources, early and at submission),
§6.1 (decision table and its notes), §6.2 (value comparison), §7.1–7.3 (request types, statuses,
allowed transitions, request number), §8.1 (phone normalization), §8.2 (username), §13 (no card data
in logs); constitution Principles I (server decides, table order, all reasons recorded, canonical
comparisons), II (no sensitive data in messages or logs), III (audit, requests never deleted),
IV (values fixed at submission; verification, approval and link are separate facts), IX (server-side
authorization), X (Baghdad time). `features.md` does not exist in the repository; this spec relies on
`docs/system.md`.

**Builds on**: feature 005 (draft form, missing-items summary, autosave, snapshot of area, tower,
category and prices), feature 006 (card reading, provenance «من البطاقة» / «عُدِّل يدوياً», original
reading kept, national-ID/MRZ check, expired card blocks sending), feature 007 (OTP verification with
its context fingerprint, and the pre-send check point `precheck_for_otp`, which always passes today).

**Out of scope (later features)**: the «إضافة اشتراك لمشترك موجود» search and the «إعادة للخدمة» path
(009); admin review screens, accept/reject, pinning corrected numbers (010); link message, copy/share
of the link message, request tabs with colors and search, notifications (011); «تم الربط» and the
monthly counter (012); importing legacy and SAS subscribers (013, 014). This feature checks against
every source that exists; legacy and SAS records join the same checks when 013/014 import them.

## Clarifications

### Session 2026-11-23

- Q: Do rejected requests count as "existing" for the phone, national ID and family checks? → A: No.
  Only pending review, approved and linked requests count.
- Q: A national ID match that first appears at submission? → A: Refuse the submission and keep the
  draft; no request, no number; the attempt is audited.
- Q: A national ID or family number the card did not read and the marketer typed by hand? → A: It
  counts as an edit: pending review with reason «تعديل الأرقام».

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a clean new request and get instant approval (Priority: P1)

A marketer has filled the whole form, the card was read, nothing was edited in the numbers, and the
phone is verified. They press «إرسال». The server repeats every check, finds no match, gives the request
its number, and approves it at once. The marketer sees «تمت الموافقة», the request number and the
username (e.g. `ALM03-07801234567`).

**Why this priority**: This is the end of the main journey that features 005–007 prepared. Without it
nothing can be submitted.

**Independent Test**: With an empty database except the catalog, fill a draft with a sample card, verify
the phone with the fake OTP, press «إرسال», and confirm the result screen, the request number
`#T3C-1001`, the username and the status «مقبول».

**Acceptance Scenarios**:

1. **Given** a complete draft with a verified phone and no matches, **When** the marketer presses
   «إرسال», **Then** a request is created with status approved, type new, the next request number, the
   username `{tower code}-{phone}`, and the screen shows «تمت الموافقة» with the number and username.
2. **Given** a draft with any missing item (including an expired card or an unconfirmed national ID),
   **When** the form is shown, **Then** «إرسال» is disabled and the missing items are listed; a direct
   server call is refused the same way.
3. **Given** a verified draft whose phone, tower, category or price changed after verification,
   **When** the marketer presses «إرسال», **Then** it is refused with «يحتاج تحقق جديد» and nothing is
   created.
4. **Given** a submitted request, **When** the marketer opens their drafts, **Then** it is no longer a
   draft: it cannot be edited or deleted, and it appears in their submitted requests with its result.
5. **Given** the marketer presses «إرسال» twice quickly or the network retries, **Then** exactly one
   request and one request number exist.

---

### User Story 2 - A used phone is stopped before any code is sent (Priority: P1)

The marketer types the subscriber's phone and presses «تحقّق». The phone already belongs to another
subscriber. No WhatsApp code is sent. The marketer sees «المشترك موجود سابقاً، هل يود العودة للخدمة؟»
and must either change the phone or take the return path.

**Why this priority**: §6.1 row 1 is the first rule and it also saves message cost (25 IQD per send).
It fills the check point left in 007.

**Independent Test**: Create a submitted request with phone `07801234567`; in a new draft enter the same
phone in another written form (`+964 780 123 4567`), press «تحقّق», and confirm the message appears,
no code is sent, and the send does not count toward the 007 limits.

**Acceptance Scenarios**:

1. **Given** a phone that matches an existing subscriber after normalization, **When** «تحقّق» is
   pressed, **Then** no code is sent, the send is not counted toward the per-phone or per-draft limits,
   and the message «المشترك موجود سابقاً، هل يود العودة للخدمة؟» is shown.
2. **Given** a phone that is free, **When** «تحقّق» is pressed, **Then** the 007 flow continues unchanged.
3. **Given** a phone that was free at verification but became used before submission (another request
   took it), **When** «إرسال» is pressed, **Then** submission is refused with the same message, nothing
   is created, and the draft is kept so the marketer can change the phone.
4. **Given** the phone is used and the family is also eligible for an additional subscription, **Then**
   the phone is still refused (§6.1 note 1).

---

### User Story 3 - Same person already subscribed is blocked as new (Priority: P1)

The national ID on the form belongs to an existing subscriber. The marketer sees «المشترك لديه اشتراك
سابق» as soon as the number is entered, and cannot send it as a new request.

**Why this priority**: §6.1 row 2, the core anti-fraud rule against registering the same person twice.

**Independent Test**: Create a submitted request with a sample national ID; in a new draft type the same
number with Arabic digits; confirm the warning appears and «إرسال» stays disabled, and that a forced
server call does not approve it.

**Acceptance Scenarios**:

1. **Given** the national ID matches an existing subscriber (digits compared after converting Arabic and
   Indic digits), **When** the number is entered or read from the card, **Then** the form shows «المشترك
   لديه اشتراك سابق» and «إرسال» is disabled.
2. **Given** the match first appears at submission (another request took it meanwhile), **When**
   «إرسال» is pressed, **Then** the submission is refused with «المشترك لديه اشتراك سابق», no request
   and no request number are created, the draft stays unchanged, and the refused attempt is written to
   the audit log (who, when, which draft, reason) without card data.

---

### User Story 4 - Family already subscribed goes to admin approval (Priority: P2)

The national ID is new, but the family number matches an existing subscriber: another person from the
same house. The marketer sees «لهذه العائلة اشتراك سابق» with «طلب اشتراك إضافي». After confirming and
verifying a new, unused phone, the request is submitted as an additional subscription and waits for
the admin: «بانتظار موافقة المسؤول».

**Why this priority**: §6.1 row 3. It lets a real second subscription through while keeping control.

**Independent Test**: Create a submitted request with family number `1234A5678901234567`; in a new draft
use a different national ID and the family number written `1234a 567890123456 7` with a letter O in a
digit place; confirm the warning, confirm «طلب اشتراك إضافي», verify a new phone, submit, and check the
request is pending with reason «عائلة موجودة», type additional, and is linked to the matching
subscription.

**Acceptance Scenarios**:

1. **Given** the family number's comparison key matches an existing subscriber and the national ID does
   not, **When** the number is entered or read, **Then** the form shows «لهذه العائلة اشتراك سابق» and a
   «طلب اشتراك إضافي» choice.
2. **Given** the marketer has not chosen «طلب اشتراك إضافي», **Then** «إرسال» stays disabled with a
   missing item asking for that choice.
3. **Given** the marketer chose it and the phone is verified and unused, **When** «إرسال» is pressed,
   **Then** the request is created with type additional, status pending review, reason «عائلة موجودة»,
   and a reference to the matched subscription; the screen shows «بانتظار موافقة المسؤول».
4. **Given** the family match disappears (the family number is changed), **Then** the choice is
   cleared and the request goes back to the normal flow.

---

### User Story 5 - Edited numbers go to review (Priority: P2)

The marketer changed the national ID or the family number from what the card reading gave. The request
is submitted but waits for review with reason «تعديل الأرقام». The screen shows «طلبك بانتظار التدقيق».

**Why this priority**: §6.1 row 4. Edited numbers are a common way to slip past the duplicate check.

**Independent Test**: Read a sample card, change one digit of the family number, verify, submit, and
check the status is pending with reason «تعديل الأرقام»; repeat with only a name edited and check it is
approved.

**Acceptance Scenarios**:

1. **Given** the final national ID or family number differs from its original card reading (compared
   with the §6.2 rules, so changing a digit back to the read value is not an edit), **When** «إرسال» is
   pressed and no earlier row applies, **Then** the request is pending review with reason «تعديل
   الأرقام» and the screen shows «طلبك بانتظار التدقيق».
2. **Given** only names were edited, **Then** this does not cause review (§6.1 note 2); the original
   reading stays stored for the admin.
3. **Given** a family match and edited numbers together, **Then** both reasons are recorded and the
   request is pending (§6.1 note 3).
4. **Given** a national ID or family number that the card did not read at all and the marketer typed by
   hand, **Then** it counts as an edit: the request is pending review with reason «تعديل الأرقام».

---

### User Story 6 - Early warnings while filling the form (Priority: P3)

While the marketer fills the form, the phone, national ID and family number are checked as soon as
each is saved, so problems show up before the marketer spends time on the rest. The warnings never
reveal who the other subscriber is.

**Why this priority**: §6 asks for an early check; the decision itself is still made at submission.

**Independent Test**: Enter a used national ID, see the warning without any name, username or tower of the
other subscriber; clear it, see the warning go away.

**Acceptance Scenarios**:

1. **Given** a phone, national ID or family number is saved on the draft, **Then** the matching
   warning (if any) appears within a few seconds next to that field and in the missing-items summary.
2. **Given** any warning, **Then** it shows only the message and the action button from §6.1, never
   the other subscriber's name, username, tower, phone or card data (§3.1).
3. **Given** the early check is unavailable, **Then** the form still works and submission still runs
   the full check.

---

### Edge Cases

- **Two drafts, same phone, same moment**: two marketers verify the same new phone and press «إرسال»
  together. Exactly one is accepted; the other is refused with the used-phone message.
- **Same national ID or family number in two simultaneous submissions**: same rule, checks and creation
  happen as one step, the second sees the first.
- **Other marketers' drafts**: a draft is not a subscriber. A phone, national ID or family number that is
  only in someone's draft does not block anyone; the first to submit wins.
- **Own earlier request**: the marketer's own submitted request counts like anyone else's.
- **Which existing requests count**: pending review, approved and linked requests count. Rejected
  requests do not: a person rejected by mistake can apply again, and the admin still sees the history.
  A request undone from «تم الربط» is approved again, so it counts.
- **Legacy subscribers with no national ID** (from 013): checked by family number and phone only
  (§6.1 note 4). SAS rows without a phone do not take part in the phone check (§12.2).
- **Family number with odd characters**: compared by its key (uppercase, no spaces or symbols, `O` as
  `0`); the value is stored as written.
- **Verification expired or invalidated**: «إرسال» is refused with «يحتاج تحقق جديد».
- **Card expired between filling and sending**: checked again at submission with Baghdad's date.
- **Archived or stopped marketer**: cannot submit (their session is already ended by 003).
- **Category or tower stopped after the draft was filled**: submission is refused with the existing
  «لم يعد متاحاً» notice from 005; the marketer picks again and verifies again.
- **Request number gaps**: a number, once given, is never reused, even if the request is later rejected.

## Requirements *(mandatory)*

### Functional Requirements

**Check engine**

- **FR-001**: The system MUST check phone, national ID and family number against every existing
  subscriber record: submitted Sijil requests, and imported legacy and SAS subscribers once those
  imports exist, across all areas and towers.
- **FR-002**: Comparisons MUST follow §6.2: phone after §8.1 normalization; national ID as digits only
  after converting Arabic and Indic digits; family number by its comparison key (uppercase, spaces and
  symbols removed, `O` as `0`), while the stored value stays as written.
- **FR-003**: The rows of §6.1 MUST be evaluated in order. Row 1 (phone used) and row 2 (national ID
  exists) stop the request as new. Rows 3 (family exists) and 4 (numbers edited) both apply when both
  match, and every applicable reason MUST be recorded. Row 5 applies only when no other row does.
- **FR-004**: The same engine MUST serve the early checks and the submission check, so their results
  never differ for the same data. The submission check is authoritative.
- **FR-005**: Drafts (including the marketer's own) and rejected requests MUST NOT count as existing
  subscribers. Pending review, approved and linked requests MUST count.
- **FR-005a**: A national ID or family number MUST count as edited (row 4) when its final value differs
  from the card reading under §6.2 comparison, or when the card gave no reading for it and it was typed
  by hand. A value equal to the front reading or to a verified MRZ is not an edit.

**Phone check before a code (the 007 check point)**

- **FR-006**: Pressing «تحقّق» MUST run the phone check after normalization and before any limit or send.
  A used phone MUST refuse the send with «المشترك موجود سابقاً، هل يود العودة للخدمة؟», send nothing, and
  not count toward the 007 send limits.
- **FR-007**: The refusal MUST NOT reveal anything about the existing subscriber.

**Early warnings**

- **FR-008**: After a phone, national ID or family number is saved, the draft MUST show the matching
  §6.1 message: row 1 «المشترك موجود سابقاً، هل يود العودة للخدمة؟», row 2 «المشترك لديه اشتراك سابق»,
  row 3 «لهذه العائلة اشتراك سابق» with the «طلب اشتراك إضافي» choice. Rows 1 and 2 and an unconfirmed
  row 3 MUST appear as missing items so «إرسال» stays disabled.
- **FR-009**: The «إعادة مشترك للخدمة» button belongs to 009; until then the row 1 and row 2 messages
  appear without it.
- **FR-010**: Confirming «طلب اشتراك إضافي» MUST be stored on the draft and cleared when the family match
  no longer exists.

**Submission**

- **FR-011**: «إرسال» MUST be enabled only when the missing-items list is empty and the phone is verified
  for the current phone, tower, category and prices (§5.5). The server MUST re-check all of this and
  refuse otherwise.
- **FR-012**: Submission MUST run the full check and create the request in one step, so two submissions
  with the same phone, national ID or family number cannot both pass.
- **FR-013**: Submission MUST be safe to repeat: a repeated press or retry returns the same result and
  never creates a second request or number.
- **FR-014**: On success the draft MUST become a request with: the next request number (`#T3C-1001` and
  upward, never reused), type (new, or additional for a confirmed family match), status (approved, or
  pending review), the pending reasons, a reference to each matched subscription, and the username
  `{tower code}-{phone}`.
- **FR-015**: At submission the request MUST keep fixed copies of: area name, tower code, category name,
  both prices, all form fields, the card provenance and original readings, the phone verification time
  and verified phone, and the automatic decision (result, reasons, time). Later settings changes MUST
  NOT alter them.
- **FR-016**: Status changes MUST follow §7.2 only. This feature uses draft → approved and draft →
  pending review. It never creates an automatically rejected request: a row 1 or row 2 match at
  submission refuses the submission and keeps the draft (User Stories 2 and 3).
- **FR-017**: A submitted request MUST NOT be edited or deleted by the marketer; it leaves the drafts
  list.
- **FR-018**: The result screen MUST show: approved → «تمت الموافقة», the request number and username
  with a button to copy the username; pending for review only → «طلبك بانتظار التدقيق»; pending with a
  family reason → «بانتظار موافقة المسؤول»; both with the request number.
- **FR-019**: The marketer MUST be able to reopen their submitted requests (number, name, date, status,
  and the same result details). Tabs, colors and search are 011.
- **FR-020**: Each submission and its automatic decision MUST be written to the audit log (who, when,
  request number, result, reasons) without national ID, family number, card images or OTP code.
  Refused submissions MUST NOT appear in logs with card data.
- **FR-021**: Only the draft's owner (an active marketer) MUST be able to submit it.

### Key Entities

- **Request**: a submitted draft. Request number, type (new / additional / return), status, marketer,
  submission time, username, fixed copies of all form and price data, card provenance and readings,
  phone verification time and phone, automatic decision (result, time, reasons). Never deleted.
- **Pending reason**: one per applicable §6.1 row: family exists, numbers edited (later: return). Each
  with the matched subscription where relevant.
- **Subscriber record (checked source)**: anything that can match: a submitted request, a legacy
  subscriber, a SAS subscriber. Carries its comparable phone, national ID and family key, and may lack
  any of them.
- **Draft check state**: the current early-check findings and the «طلب اشتراك إضافي» confirmation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A marketer with a complete, verified, clean draft goes from «إرسال» to «تمت الموافقة» with
  the username in under 5 seconds.
- **SC-002**: In tests covering every §6.1 row and combination, 100% of submissions get the documented
  result and reasons, including different written forms of the same phone, national ID and family
  number.
- **SC-003**: Zero WhatsApp codes are sent for a phone that is already used.
- **SC-004**: Under 20 simultaneous submissions sharing one phone (or national ID), exactly one passes.
- **SC-005**: Early warnings appear within 3 seconds of the field being saved.
- **SC-006**: No warning, refusal, result screen or log line contains another subscriber's name, phone,
  username, national ID or family number, or the submitting subscriber's national ID or family number.

## Assumptions

- Today the only existing subscribers are submitted Sijil requests; legacy (013) and SAS (014) records
  will be checked by the same engine once imported, with no change to the rules.
- Row 1 and row 2 actions («إعادة مشترك للخدمة») and the dashboard «إضافة اشتراك لمشترك موجود» are 009.
  Row 3 is handled fully here because it starts from the new-subscriber form.
- The username is stored at submission for every request but shown to the marketer only when approved.
- Copy and share of the link message (§8.4) are 011; this feature offers copying the username only.
- Admins have no screen for pending requests until 010; the reasons and matched subscriptions are
  stored so 010 can show them.
- "Edited" for row 4 is decided by value (FR-005a), not by whether the field was touched.
- No extra rate limit is added to the early checks beyond the existing login and session rules.
