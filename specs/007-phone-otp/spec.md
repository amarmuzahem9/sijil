# Feature Specification: Subscriber Phone Verification by WhatsApp OTP

**Feature Branch**: `007-phone-otp`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "الفيزة 007: التحقق من هاتف المشترك برمز OTP عبر الواتساب. ارجع لـ docs/system.md
الأقسام 5.4 و8.1 و8.3، وللقسم 007 بـ features.md. المطلوب: زر «تحقّق» بجانب الهاتف: يوحّد الرقم، وإذا الرقم غير
صالح يعرض خطأ. (فحص «الهاتف مستخدم» يُضاف في 008؛ اترك نقطة الربط جاهزة.) إرسال رمز 6 أرقام عبر مزوّد الواتساب،
الرسالة فيها الرمز فقط. خانة إدخال الرمز، مع عداد «إعادة الإرسال بعد 60 ثانية». صلاحية الرمز حسب الإعدادات
(افتراضي 60 دقيقة). 3 محاولات خطأ تلغي الرمز. حد 5 رموز للهاتف في الساعة. بعد النجاح: علامة ✓ «تم التحقق» بجانب
الرقم. أي تغيير في الهاتف أو البرج أو الفئة بعد التحقق يلغي التحقق ويظهر «يحتاج تحقق جديد». لا يظهر الرمز في أي
مكان غير رسالة الواتساب. معيار القبول: رمز حقيقي يصل لهاتف تجريبي، والتحقق ينجح، وتغيير الفئة يلغيه. مزوّد
الواتساب: OTPIQ (شركة عراقية)، توثيقه: https://docs.otpiq.com/api-reference/introduction. تأكد: هل يرسل رمزاً
نولّده نحن أم يولّد الرمز ويتحقق منه بنفسه؟ المصادقة والأسعار؟ عدّل التصميم حسبه، والمفتاح في .env فقط."

**System document references**: `docs/system.md` §5.4 (phone and verification section), §5.5 (submit
enabled only after verification), §8.1 (phone normalization), §8.3 (OTP rules), §13 (no OTP codes in
logs), §14 (OTP through a swappable WhatsApp provider layer); constitution Principles I (change to
phone, tower, category or price invalidates verification), II (OTP stored as hash only, never in any
message, log or export), IV (verification is a separate fact with its own timestamp), VII (adapter
with a fake implementation; config from `.env`). `features.md` does not exist in the repository; this
spec relies on `docs/system.md`.

**Out of scope (later features)**: the «الهاتف مستخدم» check and the whole decision table (008; this
feature leaves a pre-send check point that always passes for now); actual submission and enabling the
«إرسال» button (008); SMS or Telegram fallback; delivery-status webhooks; admin screens for provider
credit or message reports.

**Builds on**: feature 004 (OTP validity setting in minutes, default 60), feature 005 (draft form,
subscriber phone field normalized per §8.1, autosave, multi-device draft, snapshot of tower, category
and both prices on the draft).

## Provider Findings (OTPIQ)

Read from the OTPIQ documentation on 2026-11-23 (API reference, OpenAPI spec, dev-key article, site):

- **Who generates the code: we do.** OTPIQ only delivers. A "verification" message carries a code
  that the caller supplies (1–20 characters). OTPIQ has no verify endpoint, so Sijil generates the
  6-digit code, stores only its hash, and checks the entered code itself. This matches §8.3.
- **Message text**: for the verification type the wording is OTPIQ's fixed template, and the caller
  passes only the code. No subscriber data, name or request detail can be added. This satisfies
  «الرسالة تحمل الرمز فقط».
- **Channel**: the provider can be forced to WhatsApp only, or set to WhatsApp with SMS/Telegram
  fallback. This feature uses WhatsApp only (§8.3).
- **Authentication**: one project API key sent as a bearer token. Live keys start `sk_live_`, dev
  keys `sk_dev_`. The key lives in `.env` only; `.env.example` lists the variable with no value.
- **Phone format**: international digits without `+` (e.g. `9647801234567`), so the normalized
  `07XXXXXXXXX` is converted to `9647XXXXXXXXX` only when sending.
- **Dev/trial mode**: a dev key sends every message to the one development phone set in the OTPIQ
  dashboard, whatever number is requested. A trial account can only send to its owner's phone.
  This is how the acceptance test reaches a test phone without messaging a real subscriber.
- **Provider limits and errors**: the provider has its own per-phone rate limit (its example: 10
  requests per phone in 10 minutes, looser than our 5 per hour), and returns errors for
  insufficient credit, spending threshold exceeded, trial-mode restriction, invalid number and bad key.
- **Pricing**: prepaid credit in IQD, pay as you go, no monthly fee. Each successful send returns its
  cost and the remaining credit. The public site lists SMS with sender ID at 80 IQD (first 250 a
  month), then 100 IQD (Asiacell, Korek) and 250 IQD (Zain), and "Smart OTP fallback" at 25 IQD per
  message. A WhatsApp-only price is not published, but the owner confirmed it: **25 IQD per WhatsApp
  message**, with a current balance of **10,000 IQD** (about 400 sends). Our cap of 5 codes per phone
  per hour limits the cost to at most 125 IQD per phone per hour.

## Clarifications

### Session 2026-11-23

- Q: Does the provider generate and verify the code? → A: No. Sijil generates, hashes and verifies;
  the provider only delivers (see Provider Findings).
- Q: §5.4 lists price as well as phone, tower and category; the request lists only phone, tower and
  category. → A: Price is included, as in §5.4 and constitution Principle I. The two prices come from
  the chosen category, so they normally change only with the category or when the admin changes the
  prices of the category while the draft is open.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Send a code and verify the phone (Priority: P1)

In the phone section of the draft, the marketer types the subscriber's phone and taps «تحقّق» next to
it. The system normalizes the number (§8.1). If it is valid, a 6-digit code is sent to that number by
WhatsApp, a code box appears under the phone, and the message «أُرسل رمز التحقق عبر الواتساب إلى
07XXXXXXXXX» is shown. The subscriber reads the code to the marketer, who types it. If it is correct,
the code box disappears and a green ✓ «تم التحقق» shows next to the number.

**Why this priority**: Verification proves the phone is real and belongs to the subscriber. Without
it a request cannot be submitted (§5.5). This is the core of the feature.

**Independent Test**: With a dev provider key, open a draft, enter the test phone, tap «تحقّق», read
the code from WhatsApp on the test phone, type it, and see ✓ «تم التحقق». Reload the draft on another
device and see the ✓ still there.

**Acceptance Scenarios**:

1. **Given** a draft with phone «٠٧٨٠ ١٢٣ ٤٥٦٧», **When** the marketer taps «تحقّق», **Then** the number
   is shown as 07801234567, one WhatsApp message carrying a 6-digit code is sent to it, and a code box
   appears.
2. **Given** a code was sent, **When** the marketer types the correct 6 digits, **Then** the phone is
   marked verified, ✓ «تم التحقق» appears next to it, and the verification time is recorded.
3. **Given** the phone «0780123» (invalid), **When** the marketer taps «تحقّق», **Then** «رقم غير صالح»
   appears under the field and no code is sent.
4. **Given** an empty phone field, **Then** «تحقّق» is disabled.
5. **Given** a verified phone, **When** the draft is opened on another device, **Then** it shows
   ✓ «تم التحقق».

---

### User Story 2 - Change after verification cancels it (Priority: P1)

After the phone is verified, if the marketer changes the phone, the tower, the category, or the
draft's prices change, the ✓ disappears and «يحتاج تحقق جديد» shows next to the number with the
«تحقّق» button available again.

**Why this priority**: This is an anti-fraud rule (constitution Principle I): a verification belongs to
one phone on one subscription offer, and must not carry over to another.

**Independent Test**: Verify a phone, change the category, see «يحتاج تحقق جديد»; verify again and see
✓ return.

**Acceptance Scenarios**:

1. **Given** a verified phone, **When** the category is changed, **Then** the verification is cancelled
   and «يحتاج تحقق جديد» is shown.
2. **Given** a verified phone, **When** the tower is changed (including through a region change), **Then**
   the verification is cancelled.
3. **Given** a verified phone, **When** the phone is edited to a different normalized number, **Then** the
   verification is cancelled. Edits that keep the same normalized number (adding spaces, writing it with
   Arabic digits) do not cancel it.
4. **Given** a verified phone, **When** the draft's trial or second-month price changes (for example the
   admin changed the category prices and the draft refreshed its copy), **Then** the verification is
   cancelled.
5. **Given** a cancelled verification, **When** the marketer puts the old values back, **Then** the
   verification stays cancelled; a new code is needed.
6. **Given** a pending (unverified) code, **When** the phone is changed, **Then** the code box closes and
   the pending code is cancelled.

---

### User Story 3 - Resend, wrong attempts, expiry and hourly limit (Priority: P2)

Under the code box a counter shows «إعادة الإرسال بعد 60 ثانية» counting down; at zero it becomes the
button «إعادة الإرسال». A wrong code shows «الرمز غير صحيح، بقيت محاولتان» then «بقيت محاولة واحدة»;
the third wrong entry cancels the code with «أُلغي الرمز بعد 3 محاولات خاطئة، اطلب رمزاً جديداً». An
expired code gives «انتهت صلاحية الرمز، اطلب رمزاً جديداً». The sixth code for the same phone within an
hour is refused with «وصلت الحد الأقصى (5 رموز في الساعة) لهذا الرقم، حاول بعد X دقيقة».

**Why this priority**: These limits stop guessing and protect the provider credit, but the main flow
works without the polished messages.

**Independent Test**: Using the fake provider in tests, send a code, enter three wrong codes, see the
code cancelled; send five codes within an hour and see the sixth refused with the waiting minutes.

**Acceptance Scenarios**:

1. **Given** a code was just sent, **Then** resend is unavailable for 60 seconds, shown as a countdown,
   and the server refuses an early resend even if the screen is bypassed.
2. **Given** a resend, **Then** the new code replaces the old one; the old code no longer works.
3. **Given** three wrong entries for the same code, **Then** the code is cancelled and even the right code
   no longer works.
4. **Given** the OTP validity setting is 60 minutes, **When** the correct code is entered after 61
   minutes, **Then** it is refused as expired.
5. **Given** five codes were sent to 07801234567 in the last 60 minutes (by any marketer, from any
   draft), **When** a sixth is requested, **Then** it is refused and no message is sent, with the minutes
   until the oldest of the five leaves the 60-minute window.

---

### User Story 4 - Provider failure is clear (Priority: P3)

If the message cannot be sent (no provider key configured, no credit, provider down, provider
refused the number), the marketer sees a clear Arabic message, no code box opens, and the attempt does
not count toward the hourly limit or start the 60-second wait.

**Why this priority**: Rare, but without it the marketer waits for a code that will never arrive.

**Independent Test**: With the fake provider set to fail, tap «تحقّق» and see «تعذّر إرسال الرمز، حاول
مرة أخرى أو أبلغ الإدارة».

**Acceptance Scenarios**:

1. **Given** the provider reports insufficient credit or a spending limit, **Then** the marketer sees
   «تعذّر إرسال الرمز، أبلغ الإدارة» and the server log records the reason without the code or the full
   phone.
2. **Given** no provider key is configured, **Then** «تحقّق» shows «خدمة التحقق غير مهيّأة» and the
   rest of the form still works.
3. **Given** the provider's own rate limit is hit, **Then** the marketer sees «حاول بعد X دقيقة» with the
   provider's waiting time.

---

### Edge Cases

- The same phone verified in two drafts: each draft holds its own verification; the hourly limit is
  shared because it counts per phone. Whether the phone may be used at all is decided in 008.
- Two devices on one draft: the code can be entered from either device; the verified state follows the
  draft. If device A sends a code and device B changes the phone, the code is cancelled.
- The admin changes the OTP validity setting: a code keeps the expiry it got when it was sent.
- The marketer types more or fewer than 6 digits, or Arabic-Indic digits: Arabic-Indic digits are
  converted; anything but exactly 6 digits is refused before checking and does not count as a wrong
  attempt.
- A draft is deleted while a code is pending: the code is gone with it; its sends still count toward the
  hourly limit for that phone.
- Weak network: a send request retried by the browser must not send two messages; a send already in
  progress for the draft blocks a second one.
- A submitted request (008) keeps the verification time and verified phone as recorded values; the
  draft's live state no longer matters.
- Dev key in use: every message goes to the OTPIQ development phone whatever number was typed; the
  staging environment must say this in its manual test notes.

## Requirements *(mandatory)*

### Functional Requirements

**Sending**

- **FR-001**: The phone section MUST show a «تحقّق» button next to the subscriber phone, enabled only
  when the field is not empty and the phone is not already verified.
- **FR-002**: On «تحقّق» the server MUST normalize the phone per §8.1 and refuse an invalid number with
  «رقم غير صالح» without sending anything.
- **FR-003**: Before sending, the server MUST run a pre-send phone check step. In this feature the step
  always allows sending; feature 008 adds the «الهاتف مستخدم» rule there, and a refusal from that step
  MUST stop the send and show its message.
- **FR-004**: The server MUST generate a random 6-digit code (000000–999999, uniformly random), send it to
  the phone by WhatsApp only through the provider's verification message, and add nothing else to the
  message.
- **FR-005**: Only one code per draft MUST be active at a time. A new code MUST cancel the previous one.
- **FR-006**: The server MUST refuse a new code for the same draft within 60 seconds of the last
  successful send. The screen MUST show the countdown «إعادة الإرسال بعد N ثانية» and then «إعادة
  الإرسال».
- **FR-007**: The server MUST refuse a sixth successful send to the same normalized phone within any
  60-minute window, counting across all drafts and marketers, and tell the marketer how many minutes
  remain.
- **FR-008**: A send that the provider did not accept MUST NOT count toward FR-006 or FR-007, and MUST
  show a clear Arabic error (User Story 4).

**Checking**

- **FR-009**: A code MUST expire after the OTP validity minutes from the settings (feature 004) in force
  when it was sent.
- **FR-010**: A wrong entry MUST reduce the remaining attempts and show how many remain. The third wrong
  entry MUST cancel the code.
- **FR-011**: A correct entry of an active, unexpired code MUST mark the draft's phone verified and record
  the verification time and a fingerprint of the values it was given for: normalized phone, tower, category, trial price
  and second-month price.
- **FR-012**: The server MUST decide whether a code is right; the screen never knows the code.

**Invalidation**

- **FR-013**: Any change after verification to the normalized phone, tower, category, trial price or
  second-month price on the draft MUST cancel the verification, on the server, whichever device made the
  change. The screen MUST then show «يحتاج تحقق جديد» next to the number.
- **FR-014**: A change to the phone while a code is pending MUST cancel that code.
- **FR-015**: The verified state MUST be checked against the draft's current values whenever it is read,
  so that 008 can rely on it at submission.

**Secrecy**

- **FR-016**: The code MUST be stored only as a keyed hash. It MUST NOT appear in any server response,
  screen, application log, error message, audit entry, notification, export or backup in plain form;
  the only place it appears is the WhatsApp message.
- **FR-017**: Logs about sending MAY record the draft, the outcome, the provider message id and the
  provider cost, but MUST NOT record the code, and MUST mask the phone (e.g. 0780****567).
- **FR-018**: The provider key MUST come from `.env` only. `.env.example` MUST list the variable empty.
- **FR-019**: The provider MUST sit behind a swappable adapter with a fake implementation for automated
  tests. The fake MUST NOT write the code to any log; tests read it from the fake directly.

**Access and UI**

- **FR-020**: Only the draft's owner MAY send or check codes for it; the server MUST enforce this.
- **FR-021**: The code box MUST accept Arabic-Indic digits, open the numeric keypad on phones, and allow
  pasting the code from WhatsApp.
- **FR-022**: All texts MUST be Arabic, right-to-left, and usable on a phone screen.

### Key Entities

- **Phone verification code (challenge)**: one per successful send; belongs to one draft and one
  normalized phone; holds the code hash, a fingerprint of the values it was sent for (phone, tower,
  category, both prices), expiry time, wrong attempts, verification time and send time. Its state
  (active, verified, cancelled, expired) follows from these. Never holds the plain code. The same rows
  serve the 5-per-hour limit across all drafts, so they are kept when the draft is deleted. The provider
  message id and cost go to the server log only.
- **Draft verification state**: on the draft, the verification time and the fingerprint of the values
  verified; both emptied when a change cancels the verification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On staging with a real provider key, a code reaches the test phone by WhatsApp and the
  marketer completes verification in under 2 minutes from tapping «تحقّق».
- **SC-002**: After verifying, changing the category shows «يحتاج تحقق جديد» within one autosave cycle,
  and the server reports the draft unverified.
- **SC-003**: In tests, 100% of the rules hold: 6-digit code, 60-second resend, 5 per phone per hour,
  3 wrong attempts, expiry per setting, cancellation on each of the five fields.
- **SC-004**: A search of server responses, logs, audit entries and the database for a sent code finds it
  nowhere in plain form.
- **SC-005**: An invalid phone gets «رقم غير صالح» and no message is sent or charged.

## Assumptions

- The provider's fixed verification template (wording chosen by OTPIQ) counts as "a message with the
  code only", because it carries no subscriber or request data.
- WhatsApp only, with no SMS fallback, as §8.3 says. A fallback would cost more and change §8.3, so it
  needs the owner's approval first.
- The 60-second resend wait is per draft; the 5-per-hour limit is per normalized phone in a rolling
  60-minute window.
- Code checks have no separate hourly limit beyond 3 attempts per code and 5 codes per hour, which gives
  at most 15 guesses per phone per hour.
- Automated tests and local development without a key use the fake provider; manual tests on staging use
  an OTPIQ dev key tied to the test phone, then a live key in production.
- The provider credit balance is managed in the OTPIQ dashboard; Sijil does not show it in this feature.
