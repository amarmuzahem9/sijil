# Feature Specification: Existing Subscriber Paths

**Feature Branch**: `009-existing-subscriber-paths`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "الفيزة 009: مسارات المشترك الموجود. ارجع لـ docs/system.md (القسم 6) ولشغل 008. قواعد
التطابق اللي أريدها بالضبط: 1. الرقم الوطني والرقم العائلي يطابقون مشترك موجود: يظهر للمسوّق زر «طلب العودة للخدمة».
2. الرقم العائلي يطابق والرقم الوطني مختلف: يظهر «إضافة اشتراك ثاني» ويروح لموافقة الأدمن (موجود من 008، تأكد إنه
يطابق هالقاعدة). 3. رقم الهاتف مرتبط بمشترك: يظهر «طلب العودة للخدمة» أو «الاتصال بالإدارة». والمسوّق ما يشوف أي
معلومة عن المشترك الآخر. إذا هالقواعد تختلف عن system.md قلّي الفرق، وحدّث system.md قبل الكود."

**System document references**: `docs/system.md` §3.1 (what the marketer may see), §4.2 (dashboard
button «إضافة اشتراك لمشترك موجود»), §6 (check on all sources, early and at submission), §6.1 (decision
table and notes), §6.2 (value comparison), §6.3 (adding a subscription for an existing subscriber),
§6.4 (admin sees the linked previous subscription), §7.1 (request type `return`), §7.2 (statuses and
transitions), §8.2 (username), §8.3 (OTP), §13 (no card data in logs); constitution Principles I
(server decides, all reasons recorded), II (identity documents protected), III (audit), IX
(server-side authorization).

**Builds on**: feature 005 (draft form and autosave), 006 (card reading and provenance), 007 (OTP and
its context fingerprint), 008 (check engine on all sources, decision table, requests, pending reasons,
result screen, the «طلب اشتراك إضافي» confirmation, refusal of a used phone or existing national ID).

**Out of scope (later features)**: admin review screens, accept/reject, the «هل تُحتسب عمولة؟»
question (010); link message, request tabs and notifications (011); «تم الربط» (012); legacy and SAS
imports (013, 014) — their records join the same matching when imported; the admin subscriber search
and file (017).

**Differences from `docs/system.md` v1.9 found while writing this spec** (to be written into
system.md before any code):

| # | system.md v1.9 | Requested rule | Effect |
|---|---|---|---|
| D1 | §6.1 row 2: the national ID alone decides "same person" | Rule 1: national ID **and** family number both match the same subscriber | A national-ID-only match needs its own rule (see FR-004) |
| D2 | §6.1 row 1: phone used → one button «إعادة مشترك للخدمة» (or change the phone) | Rule 3: two choices «طلب العودة للخدمة» or «الاتصال بالإدارة» | New «الاتصال بالإدارة» action |
| D3 | §3.1, §6.3 item 2: the marketer sees the existing subscriber's name, username and tower | The marketer sees **no** information about the other subscriber | §3.1 and §6.3 must drop that display; affects the dashboard search |
| D4 | Button labels «إعادة مشترك للخدمة» and «طلب اشتراك إضافي» | «طلب العودة للخدمة» and «إضافة اشتراك ثاني» | Labels change everywhere, including the 008 screens |
| D5 | §6.1 row 3 / 008: family match applies whenever the national ID is **not found**, including a legacy subscriber with no national ID | Rule 2: family matches **and** national ID is different | Legacy subscriber without a national ID is neither "same" nor "different" (see Assumptions) |

Rule 2 versus the 008 code: 008 already sends a family match with a new national ID to admin approval
as type `additional` with reason «عائلة موجودة». It matches rule 2 except the button label (D4) and
the legacy case (D5).

## Clarifications

### Session 2026-11-23

- Q: What does «الاتصال بالإدارة» do? → A: Opens WhatsApp to the administration's number with a ready
  message that carries no subscriber data. The number is set in the admin settings.
- Q: National ID matches a subscriber but the family number differs (or that record has no family
  number)? → A: Sending is allowed and the request goes to admin review with its own reason
  «تعارض بالأرقام».
- Q: What does the dashboard button «إضافة اشتراك لمشترك موجود» do now that the marketer sees nothing
  about the existing subscriber? → A: It opens the same subscriber form; the checks decide the path.
- Defaults confirmed by the user: card and OTP always required on a return; on a return only the
  matched subscriber's own phone is allowed; a pending return blocks another return for the same
  person; the phone rule comes before the family rule.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Same person returns to service (Priority: P1)

A marketer fills the new-subscriber form for someone who already has a subscription in the records.
The national ID and the family number on the card both match one existing subscriber. Instead of being
stuck with «المشترك لديه اشتراك سابق», the marketer sees «طلب العودة للخدمة». Pressing it turns the
draft into a return-to-service request: the card, location, tower and category already entered stay,
the phone may be the subscriber's old phone, it is verified by OTP, and the request waits for admin
approval. The marketer sees nothing about the existing record.

**Why this priority**: today this case is a dead end (008 refuses the submission); returning
subscribers are a real, frequent case and the marketer cannot complete them at all.

**Independent Test**: Create a submitted request with national ID `199000000001` and family number
`1234A5678901234567`. In a new draft enter the same two numbers, press «طلب العودة للخدمة», verify a
phone (the old one or a new one), submit; the result shows «بانتظار موافقة المسؤول», the request has
type return, status pending review, reason «إعادة للخدمة», and is linked to the existing record — and no
screen or response the marketer receives contains that record's name, username, tower, phone or images.

**Acceptance Scenarios**:

1. **Given** the national ID and the family number (by its comparison key) both match the same
   existing subscriber, **When** either number is entered or read, **Then** the form shows
   «المشترك لديه اشتراك سابق» with the button «طلب العودة للخدمة», and plain sending as new is blocked.
2. **Given** the marketer pressed «طلب العودة للخدمة», **Then** the draft is marked as a return request,
   the phone check allows a phone that belongs to the matched subscriber, and every other rule of the
   form (complete sections, OTP, expired card) still applies.
3. **Given** a return draft with a verified phone, **When** the marketer submits, **Then** a request is
   created with type return, status pending review, reason «إعادة للخدمة», linked to the matched
   subscriber, and the result screen shows «بانتظار موافقة المسؤول» with the request number.
4. **Given** a return draft, **When** the national ID or family number is changed so the match is gone,
   **Then** the return choice is cleared and the draft is checked again as a new one.
5. **Given** a return draft, **When** the marketer enters a phone that belongs to a **different**
   subscriber than the matched one, **Then** the phone is refused as used, as for any new request.

---

### User Story 2 - Phone already belongs to a subscriber (Priority: P1)

The marketer enters a phone and presses «تحقّق». The phone belongs to an existing subscriber. No code
is sent. The marketer sees «المشترك موجود سابقاً، هل يود العودة للخدمة؟» with two choices:
«طلب العودة للخدمة» and «الاتصال بالإدارة». The marketer can also just change the phone.

**Why this priority**: the phone check is the first and most frequent hit; today it only stops the
marketer.

**Independent Test**: Create a submitted request with phone `07801234567`. In a new draft enter
`+964 780 123 4567`, press «تحقّق»: no code is sent, both choices appear, and no detail of the owner is
shown. Press «طلب العودة للخدمة» and continue to a pending return request.

**Acceptance Scenarios**:

1. **Given** the phone (after normalization) belongs to an existing subscriber, **When** the marketer
   presses «تحقّق», **Then** no code is sent and the message shows the two choices.
2. **Given** the marketer presses «طلب العودة للخدمة» from the phone message, **Then** the draft becomes
   a return request linked to the phone's subscriber, the same phone may now be verified by OTP, and
   submission creates a pending return request as in Story 1.
3. **Given** the marketer presses «الاتصال بالإدارة», **Then** WhatsApp opens to the administration
   number from the settings with a ready message naming only the marketer (no subscriber phone,
   numbers or name), and the draft stays as it is and editable.
3a. **Given** no administration WhatsApp number is set in the settings, **Then** «الاتصال بالإدارة»
   is shown disabled with «رقم الإدارة غير مضبوط في الإعدادات».
4. **Given** the phone belongs to a subscriber and the national ID and family number also match that
   same subscriber, **Then** only the return choice is offered once (no duplicate messages).
5. **Given** the phone belongs to subscriber A while the card's numbers match subscriber B, **Then**
   the return request can only be made for B with a phone that is not A's; using A's phone is refused.
6. **Given** the marketer changes the phone to an unused one, **Then** the message and choices disappear
   and the draft continues as a new request.

---

### User Story 3 - Second subscription for the same family (Priority: P2)

The family number matches an existing subscriber and the national ID is different: another person
from the same house. The marketer sees «لهذه العائلة اشتراك سابق» and «إضافة اشتراك ثاني». After
confirming and verifying a new unused phone, the request goes to admin approval. This is the 008
behavior, checked against the rule and relabeled.

**Why this priority**: already works from 008; this story only aligns the label and confirms the rule.

**Independent Test**: Run the 008 family test (family number match, different national ID): the button
reads «إضافة اشتراك ثاني», the request is type additional, pending, reason «عائلة موجودة».

**Acceptance Scenarios**:

1. **Given** the family key matches and the national ID differs from the matched subscriber's, **Then**
   the form shows «لهذه العائلة اشتراك سابق» with «إضافة اشتراك ثاني».
2. **Given** the choice is confirmed and a new unused phone is verified, **When** submitted, **Then** the
   request is type additional, pending review, reason «عائلة موجودة», as in 008.
3. **Given** the family matches and the phone is used, **Then** the phone rule (Story 2) applies first.

---

### User Story 4 - Start from the dashboard (Priority: P3)

The dashboard button «إضافة اشتراك لمشترك موجود» starts a return or a second-subscription request
without first filling a new form.

**Why this priority**: the form already reaches both paths through the checks; this is a shortcut.

**Acceptance Scenarios**:

1. **Given** the marketer presses «إضافة اشتراك لمشترك موجود», **Then** a new draft of the same
   subscriber form opens, and the checks (Stories 1–3, the conflict case) offer the right path once the
   phone, national ID or family number is entered. There is no search.
2. **Given** a draft opened from this button whose numbers match nothing, **Then** it continues as a
   normal new request.

---

### Edge Cases

- **National ID matches but the family number differs** (or the matched record has no family number):
  the form shows «الرقم الوطني مسجّل سابقاً ببيانات مختلفة، سيُراجع الطلب من الإدارة» with no detail and
  no button; sending is allowed (with an unused phone and OTP) and the request goes to pending review
  with reason «تعارض بالأرقام», linked to the matched subscriber(s). If the family number also matches
  another subscriber, both reasons are recorded and the «إضافة اشتراك ثاني» confirmation still applies.
- **Legacy subscriber with no national ID and a matching family number**: treated as rule 2 (second
  subscription, admin approval), as in 008. The admin sees the record and decides (see Assumptions).
- **More than one existing subscriber matches** (e.g. two family records): the request links to all of
  them for the admin; the marketer sees one message.
- **A rejected request** is not "existing" (008 rule) — it never triggers return or second subscription.
- **The matched subscriber's own return request is already pending**: it counts as existing; a second
  return for the same person is refused like a used national ID, with the message «يوجد طلب سابق
  بالانتظار لهذا المشترك» and no detail.
- **Match disappears or appears at submission** (another request got there first): the server re-checks;
  a new match the marketer did not choose refuses the submission and keeps the draft, as in 008.
- **Probing**: the messages say only that a match exists and which path is offered; no response carries
  the other subscriber's name, phone, username, tower, numbers, images or request number. Every check
  hit stays audited (008).
- **Changing the phone, tower, category or price after OTP** voids the verification (007), also on a
  return draft.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Before any code, `docs/system.md` MUST be updated with D1–D5 and the decisions on the
  open questions (§3.1, §6.1, §6.3, labels), with a new version line.
- **FR-002**: The system MUST classify a draft's matches in this order: (1) phone belongs to a
  subscriber; (2) national ID and family number both match the same subscriber; (2b) national ID
  matches but the family number differs or is missing on that record (conflict); (3) family number
  matches and national ID differs; (4) numbers edited; (5) none. Rows 2b, 3 and 4 add up as reasons. Comparison follows §6.2 and counts
  only pending, approved and linked requests and imported subscribers.
- **FR-003**: Match (2) MUST offer «طلب العودة للخدمة» and block sending as new.
- **FR-004**: A national ID match whose family number differs from, or is missing on, the matched
  record MUST allow sending and create a pending review request with reason «تعارض بالأرقام», linked
  to the matched subscriber(s); type is new, or additional when a confirmed family match also applies.
  This replaces 008's refusal for this case. A national ID match together with a family match on the
  same subscriber stays match (2).
- **FR-005**: Match (1) MUST send no code and offer «طلب العودة للخدمة» and «الاتصال بالإدارة»; changing
  to an unused phone removes the message.
- **FR-005a**: «الاتصال بالإدارة» MUST open WhatsApp to the administration number with a ready message
  that names only the marketer; it MUST NOT include the subscriber's phone, numbers, name or images.
  The draft is unchanged.
- **FR-005b**: The settings page (permission `settings`) MUST hold one «رقم واتساب الإدارة», normalized
  by §8.1 and validated; changes are audited with old and new value. When it is empty the button is
  disabled with «رقم الإدارة غير مضبوط في الإعدادات».
- **FR-005c**: The dashboard button «إضافة اشتراك لمشترك موجود» MUST open a new draft of the same
  subscriber form; no subscriber search is offered to the marketer.
- **FR-006**: Choosing return MUST be saved on the draft with the matched subscriber, and MUST be
  cleared when the match that produced it disappears.
- **FR-007**: On a return draft the phone check MUST accept a phone that belongs to the matched
  subscriber only; any other used phone is refused.
- **FR-008**: A return draft MUST meet every completeness rule of a new draft, including a front and
  back card image and OTP on the subscription phone.
- **FR-009**: Submitting a return draft MUST create a request of type return, status pending review,
  reason «إعادة للخدمة», linked to the matched subscriber(s); the result screen shows
  «بانتظار موافقة المسؤول». Edited numbers add their own reason as in 008.
- **FR-010**: The server MUST re-check at submission; a return is valid only if the chosen match still
  exists. A pending return for the same subscriber blocks another return.
- **FR-011**: Match (3) MUST keep the 008 behavior with the label «إضافة اشتراك ثاني».
- **FR-012**: No marketer-facing message, screen or response MUST include any information about the
  matched subscriber (name, phone, username, tower, numbers, dates, images, request number).
- **FR-013**: The admin (with `review`) MUST see, on the request, which subscriber(s) it is linked to
  and why (phone, national ID + family, family); the review screen itself is 010.
- **FR-014**: Choosing return, cancelling it, opening «الاتصال بالإدارة», and submitting MUST be written to the
  audit log (who, when, which draft/request, which path) without card data.
- **FR-015**: The username of an approved return keeps the historical username if the matched record
  has one, else follows §8.2; this is stored on the request for use at approval (010/011).
- **FR-016**: All new texts are Arabic: «طلب العودة للخدمة»، «الاتصال بالإدارة»، «إضافة اشتراك ثاني»،
  «إعادة للخدمة» and «تعارض بالأرقام» (reasons), «رقم واتساب الإدارة» (setting), and the 008 labels
  are renamed accordingly.

### Key Entities

- **Return choice (on the draft)**: the path the marketer chose (return), the matched subscriber
  reference(s) and which match produced it (phone, national ID + family).
- **Request**: gains use of type `return` and the pending reason «إعادة للخدمة», with links to the
  matched subscriber(s) and the kind of each match.
- **Administration WhatsApp number (setting)**: one phone number, set by an admin with `settings`.
- **Matched subscriber reference**: source (sijil request, legacy, SAS) and id; never sent to the
  marketer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A marketer can complete a return-to-service request for a subscriber whose card numbers
  match, from first entry to submission, in under 5 minutes.
- **SC-002**: 100% of the matching cases in the rule table (phone, national ID + family, family only,
  none, and each combination) produce the specified path in tests, written forms included.
- **SC-003**: In 100% of marketer-facing responses tested for every match path, none contains any field
  of the matched subscriber.
- **SC-004**: No return request can be created without the chosen match still existing at submission
  (0 in concurrent tests).
- **SC-005**: Every path choice and submission appears in the audit log with no card data.

## Assumptions

- A return request takes new location, tower and category like a new one (§6.3), and the card is
  always required (the marketer already captured it in the form), which also fills missing data for
  legacy subscribers.
- The legacy subscriber with no national ID and a matching family number follows rule 2 (second
  subscription); the admin sees the linked record and can reject if it is the same person.
- The phone rule wins over the family rule: a used phone needs a new phone or the return path, even
  when a second subscription is possible (§6.1 note).
- «الاتصال بالإدارة» is logged as "opened" only; the system cannot know whether a message was sent.
- 008's `draft_incomplete` handling for an unconfirmed family choice applies the same way to an
  unconfirmed return choice.
