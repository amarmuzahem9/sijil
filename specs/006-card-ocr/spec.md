# Feature Specification: Automatic National Card Reading (OCR)

**Feature Branch**: `006-card-ocr`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "الفيزة 006: قراءة البطاقة الوطنية آلياً (OCR) في استمارة إضافة مشترك جديد. ارجع
لـ docs/system.md القسم 5.1 (البنود 3–5) والقسم 14. القرارات المعتمدة من المالك: (1) نعتمد المشروع المفتوح
ID_Iraqi_Project (AGPL-3.0 على الكود والأوزان) داخل المستودع بمجلد ocr/ كخدمة docker مستقلة اسمها ocr، لا تُخلط
بكود api؛ كود خدمة ocr مع تعديلاتنا يُتاح لمستخدميها حسب AGPL، وكود سجل يبقى خاصاً. (2) api تكلمها عبر الشبكة
الداخلية فقط، والحاوية بلا إنترنت، والنماذج تُحمَّل وقت البناء وتُتحقق بـ SHA256 وتبقى بالذاكرة؛ حدودها معالجان و2 GB.
(3) القراءة الخام لكل وجه فقط (حقول الوجه، الرقم العائلي من الظهر، MRZ مع أرقام التحقق)، بلا منطق المطابقة والرفض
في البرنامج؛ تُملأ ثمانية حقول: الاسم الأول، الأب، الجد، اللقب، اسم الأم الأول، اسم الأم الثاني (جد الأم)، الرقم
الوطني، الرقم العائلي. (4) «أعد التصوير» فقط إذا الاكتشاف الثاني ثقته عالية أو فيه حقول مقروءة؛ اكتشافان بنفس
رقم الوثيقة أو متداخلان بشدة = بطاقة واحدة؛ وجه أو ظهر غير مكتشف = «أعد التصوير» مع نصائح والمتابعة اليدوية ممكنة.
(5) الرقم الوطني من الوجه يطابق MRZ لما تصح أرقام التحقق (ومنها المركّب)، وإذا اختلفا يتأكد المسوّق؛ MRZ غير
المتحقق منه لا يُستعمل. (6) الرقم العائلي: O تصير صفراً في الخانات الرقمية وفحص الشكل، وإذا لم يُقرأ يبقى فارغاً.
تجربة المسوّق: القراءة تبدأ تلقائياً بعد رفع الوجهين مع «جارٍ قراءة البطاقة»، لا تكتب فوق حقل عدّله المسوّق،
الحقول المملوءة آلياً تُميَّز حتى يراجعها، وتغيير صورة يعيد القراءة. اختبارات بصور تركيبية فقط. معيار القبول:
بطاقة واضحة تملأ الحقول الثمانية خلال ثوانٍ، تعديل حقل يُبقي القراءة الأصلية محفوظة، وصورة غير واضحة تعطي
«أعد التصوير» مع المتابعة اليدوية."

**System document references**: `docs/system.md` v1.7 §5.1 items 3, 4, 5 (card reading,
«أعد التصوير», manual correction with the original reading always kept) and item 6 (unified card
only), the §5.1 name-field table, §6.4 (the reviewer later sees the card image, the original
reading and the marketer's correction), §13 (no card data in logs; private images), §14 (local
OCR on the server, «يُحدَّد في الفيزة 006»); constitution Principles II, V, VII, VIII, IX.

**Out of scope (later features)**: OTP verification (007); the duplicate check, the decision
table and submission (008), including copying the reading onto the submitted request; admin
review screens that display the original reading and let the reviewer fix numbers (010);
reading other documents (residence card, old ID, passport); reading the card on the phone.

**Builds on**: feature 005 (draft form, card image slots with on-device compression, autosave,
multi-device change notice, name-field rules, private image storage).

## Clarifications

### Session 2026-11-23 (owner decisions given in the request)

- The reader is the open-source project ID_Iraqi_Project (AGPL-3.0, code and trained models),
  kept in this repository as its own service, separate from the app's server code. The app's
  server talks to it over the internal network only; the reader has no internet access; its
  models are part of the build and checked against published checksums; they stay loaded.
  The reader gets at most 2 processors and 2 GB of memory (the server has 4 processors,
  6.7 GB free memory, 14 GB free disk).
- Only the raw reading of each side is used: front fields, the family number from the back,
  and the machine-readable zone (MRZ) with its check digits. The project's own front/back
  matching and rejection rules are not used.
- «أعد التصوير» because of a second document only when the second detection is high-confidence
  or has readable fields; two detections with the same MRZ document number, or that overlap
  heavily, are one card.
- The front national ID must match the MRZ national ID when the MRZ is verified by its check
  digits; when they differ, the marketer is asked to confirm. An unverified MRZ is never used
  for the comparison.
- Family number: the letter O becomes zero in digit positions, the shape is checked, and an
  unread number stays empty for manual entry.
- Owner's sample (11 real cards, never in the repository): the front was found in 10 of 11
  photos; 59 of 60 name fields and every national ID were read correctly; the family number was
  right in 9 of 11 (one more after O→0, one unread); two MRZ birth-date misreads were caught by
  the check digits; one back was detected twice in one photo; one phantom "front" appeared
  inside a back photo. Reading took 2–6 seconds per photo on 2 processors.

### Session 2026-11-23 (owner answers to the spec questions)

- Q: The card's surname line is often empty (5 of 11 sample cards), but §5.1 makes the surname
  required. → A: The surname stays required; the marketer may instead choose «لا يوجد لقب على
  البطاقة», which satisfies the requirement and tells the reviewer the absence is deliberate.
  When a reading finds the surname line empty, the form suggests that choice (FR-017).
- Q: How are users offered the reader's AGPL source? → A: A public copy of the reader (a public
  fork of the project holding the repository's `ocr/` folder with all our changes), linked from
  inside the app in «حسابي» under «رخص البرمجيات المفتوحة», and kept in step with every change
  to the reader (FR-022).
- The owner approved updating constitution Principle VII (runtime services include the
  separate `ocr` reader) and docs/system.md v1.7 (§5.1 reading rules, the «لا يوجد لقب» choice,
  §14 reader choice) before planning.

### Session 2026-11-23 (owner change: every field on the back of the card)

- The back's other fields are added: date of birth, place of birth, issue date, expiry date and
  issuing authority, next to the family number. Same «من البطاقة» / «عُدِّل يدوياً» rules and
  the original reading is kept.
- Q: How are the printed values read, since the reader's back model only locates the MRZ, the
  place of birth and the family number? → A: Spike first. Result on the 11 private cards: rows
  cut by their position from the place-of-birth and family-number boxes (the layout is fixed),
  read by the Arabic recogniser and Tesseract, and accepted only when cross-checked: expiry
  11/11, birth 11/11, issuing authority 11/11, issue date 9/11 (2 left empty), 0 wrong values.
- Q: Which are required? → A: All five.
- Q: An expired card? → A: Saving the draft is allowed; sending is blocked (008) and «البطاقة
  منتهية الصلاحية» is a missing item.
- Q: Which MRZ check digits must hold for a date? → A: The field's own check digit (birth or
  expiry). The national-ID cross-check still needs all four.
- docs/system.md v1.8 §5.1 «حقول ظهر البطاقة» records the rules.
- Follow-up answers: the five fields are required; the national ID's first four digits are
  the birth year (confirmed by the owner). When the birth year (typed or read) differs from
  them, the form warns «سنة الميلاد لا تطابق الرقم الوطني، تأكد منهما» but does not block
  saving or sending (FR-032). Tests include a female card and births after 2000.

### Session 2026-11-23 (owner notes after the staging test)

- Every field takes the full width of the screen, one per row.
- The «من البطاقة» / «عُدِّل يدوياً» mark sits with the label on the field's frame, never inside
  the box over the value.
- Dates are typed or picked from the calendar, shown right-aligned as YYYY-MM-DD (e.g. 1999-01-10), so read from the right they are day, month, year; the server still stores dates.
- An empty field never carries a mark.
- The place of birth is filled only when the reading has at least six letters and contains a known
  governorate or main city (spelling-insensitive); a short or unknown reading such as «يدع ي»
  stays empty, with its raw reading kept.
- An empty issue date is expected when no printed reading equals expiry − 10 years + 1 day
  (1 of 15 sample cards); it is typed by the marketer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A clear card fills the form by itself (Priority: P1)

The marketer photographs the front and then the back of the subscriber's unified national card
in the two existing slots. As soon as both images are uploaded, the form shows «جارٍ قراءة
البطاقة» in the card section, and within seconds the card-data fields fill in: first name,
father, grandfather, surname, mother's first name, mother's second name (the mother's father on
the card), national ID and family number. Each filled field carries a small «من البطاقة» mark so
the marketer knows to check it. The fourth name, the mother's third name and the mother's
surname are never on the card and stay for the marketer to type.

**Why this priority**: This is the feature's purpose: typing nine names and two long numbers on
a phone is slow and error-prone; reading them removes most of the typing.

**Independent Test**: Upload a synthetic clear front and back to a new draft; the eight fields
fill with the expected values and are marked «من البطاقة»; the draft is saved with them.

**Acceptance Scenarios**:

1. **Given** a draft with no card images, **When** the marketer uploads the front only,
   **Then** no reading starts and the section says the back is still needed.
2. **Given** the front is uploaded, **When** the back finishes uploading, **Then** «جارٍ قراءة
   البطاقة» appears, and when the reading ends the eight fields are filled, marked «من
   البطاقة», and saved to the draft.
3. **Given** a card whose surname line is empty, **When** it is read, **Then** the surname
   field stays empty, the form suggests «لا يوجد لقب على البطاقة», and the other fields fill
   normally (FR-017).
4. **Given** a name read from the card that breaks the name rule (e.g. contains a digit or a
   Latin letter), **When** the reading ends, **Then** that field is left empty for the marketer,
   and the raw reading is still kept.
5. **Given** the reading filled the fields, **When** the marketer opens the same draft on
   another phone, **Then** the filled values and their «من البطاقة» marks are there.

---

### User Story 2 - Correct a field; the original reading is kept (Priority: P1)

The marketer checks the filled fields against the card and fixes any mistake by typing. The
corrected value becomes the field's value, and the original reading stays stored beside it so a
reviewer can later compare the card image, what was read and what the marketer typed. A field
the marketer has typed or corrected is never overwritten by a later reading.

**Why this priority**: §5.1 item 5 makes keeping the original reading mandatory; it is the
anti-fraud trail behind every number the marketer changes.

**Independent Test**: After a reading fills the fields, change the grandfather's name and save;
the draft holds the typed value as the final value and the read value as the original reading.

**Acceptance Scenarios**:

1. **Given** a field filled from the card, **When** the marketer changes it, **Then** the new
   value is saved as the final value, the «من البطاقة» mark is replaced by «عُدِّل يدوياً», and
   the original reading is kept unchanged.
2. **Given** the marketer typed the national ID before the reading finished, **When** the
   reading ends, **Then** the typed national ID is not replaced; the reading is still stored as
   the original reading.
3. **Given** a field filled from the card, **When** the marketer clears it, **Then** it stays
   empty (it counts as edited) and the original reading is kept.

---

### User Story 3 - Unclear or wrong photo: «أعد التصوير», or continue by hand (Priority: P2)

When a side cannot be read, the slot of that side says what is wrong and offers «أعد التصوير»
with short tips: no glare, the card flat, filling the frame, the right side in the right slot.
The marketer can retake the photo, which replaces it and reads again, or carry on typing the
fields by hand. A card detected twice in the same photo, or a faint phantom shape, does not
trigger «أعد التصوير».

**Why this priority**: In the owner's sample one front in eleven was not found at all; a clear
next step avoids a stuck marketer at the subscriber's door.

**Independent Test**: Upload a synthetic photo with no card in the front slot; the front slot
shows «أعد التصوير» with tips, nothing is filled, and the fields stay editable.

**Acceptance Scenarios**:

1. **Given** a front photo in which no card is found, **When** the reading ends, **Then** the
   front slot shows «لم نتمكن من قراءة وجه البطاقة» with «أعد التصوير» and the tips, and the
   fields remain open for typing.
2. **Given** a back photo was put in the front slot (or the reverse), **When** the reading ends,
   **Then** the slot says which side the photo shows and offers «أعد التصوير»; nothing is filled
   from that photo.
3. **Given** a photo with two different cards (two distinct document numbers or two readable
   card fronts), **When** the reading ends, **Then** the slot shows «يظهر أكثر من مستمسك في
   الصورة» with «أعد التصوير», and nothing is filled from that photo.
4. **Given** the same card is detected twice in one photo (same document number, or heavily
   overlapping), **When** the reading ends, **Then** it counts as one card and is read normally.
5. **Given** a weak second detection with no readable fields beside a good card, **When** the
   reading ends, **Then** it is ignored and the good card is read normally.
6. **Given** a photo of another document (e.g. a driving licence), **When** the reading ends,
   **Then** the slot shows «البطاقة الوطنية الموحدة فقط» with «أعد التصوير».
7. **Given** «أعد التصوير» is shown, **When** the marketer types all fields by hand instead,
   **Then** the form accepts them as usual and the message does not block anything.

---

### User Story 4 - National ID cross-check with the machine-readable zone (Priority: P2)

The back of the card repeats the national ID inside the machine-readable zone, protected by
check digits. When that zone is read and all its check digits are right, the national ID read
from the front must equal it. If they differ, the form shows both numbers and asks the marketer
to look at the card and confirm the right one.

**Why this priority**: The national ID is the key of the duplicate check (§6); a wrong digit
could let a duplicate through or block a real subscriber.

**Independent Test**: Use a synthetic card whose front number differs by one digit from its
verified MRZ; the form shows «تأكد من الرقم الوطني» with both numbers and requires a choice.

**Acceptance Scenarios**:

1. **Given** a verified MRZ and a front national ID equal to it, **When** the reading ends,
   **Then** the national ID is filled with no warning.
2. **Given** a verified MRZ and a different front national ID, **When** the reading ends,
   **Then** the field shows «تأكد من الرقم الوطني» with both numbers; the marketer picks one or
   types the number from the card, and the confirmation is saved with the draft.
3. **Given** an MRZ that is not verified (any check digit wrong), **When** the reading ends,
   **Then** no comparison is made and no warning is shown because of the MRZ.
4. **Given** the front national ID was not read but the MRZ is verified, **When** the reading
   ends, **Then** the national ID is filled from the MRZ and marked «من البطاقة».
5. **Given** a confirmed national ID, **When** the marketer later edits it, **Then** the
   confirmation no longer applies and the comparison runs again on the new value.

---

### User Story 5 - Reading is unavailable: the form keeps working (Priority: P3)

If the reader is down, busy for too long, or fails, the card section says «تعذّرت القراءة
الآلية، أكمل يدوياً» with «أعد المحاولة». The images stay uploaded, nothing already in the
draft is lost, and the marketer can type everything by hand.

**Why this priority**: The form must never depend on the reader; this protects the main flow
built in 005.

**Independent Test**: Stop the reader, upload both sides; the message and «أعد المحاولة» appear,
the images stay, and all fields can be typed and saved.

**Acceptance Scenarios**:

1. **Given** the reader is unavailable, **When** both sides are uploaded, **Then** the section
   shows «تعذّرت القراءة الآلية، أكمل يدوياً» with «أعد المحاولة» after at most the waiting
   limit (FR-014), and the fields remain editable.
2. **Given** that message, **When** the reader is back and the marketer taps «أعد المحاولة»,
   **Then** the reading runs and fills only fields the marketer has not typed.
3. **Given** several marketers upload at the same moment, **When** the reader is busy, **Then**
   each waits with «جارٍ قراءة البطاقة» and gets a result or the failure message within the
   waiting limit.

---

### User Story 6 - Replacing an image reads again (Priority: P3)

When the marketer replaces the front or back image (for example after «أعد التصوير»), the
card is read again. Fields that were filled from the card and not edited take the new reading;
fields the marketer typed or corrected stay as they are.

**Why this priority**: A retake is the normal answer to a bad reading; it must update the fields
without undoing the marketer's work.

**Independent Test**: Read a card, edit one field, replace the front with another synthetic
card; the unedited fields change to the new reading and the edited field does not.

**Acceptance Scenarios**:

1. **Given** fields filled from the card, one of them edited, **When** the front image is
   replaced, **Then** «جارٍ قراءة البطاقة» appears and afterwards the unedited fields hold the
   new reading while the edited field is unchanged.
2. **Given** a new reading of the same side, **When** it is stored, **Then** the original
   reading of each field is the one that belongs to the current images.
3. **Given** a reading is running, **When** the image is replaced again, **Then** only the
   reading of the latest images is applied.

---

### User Story 7 - The back fills its dates, place of birth and issuing authority (Priority: P2)

From the back of the card, the reading also fills the date of birth, the place of birth, the
issue date, the expiry date and the issuing authority, with the same marks and the same
never-overwrite rule. A date that cannot be confirmed by its check digit or by the other dates
stays empty for the marketer, who picks it with a date picker. An expired card is shown as
«البطاقة منتهية الصلاحية» and blocks sending.

**Why this priority**: The ministry registration needs these fields; typing four dates on a
phone is slow and error-prone.

**Independent Test**: Upload a synthetic clear front and back; the five back fields fill and are
marked «من البطاقة». A synthetic back with an expired date lists «البطاقة منتهية الصلاحية»
among the missing items.

**Acceptance Scenarios**:

1. **Given** a clear back whose MRZ birth and expiry check digits are right, **When** it is
   read, **Then** the birth and expiry dates come from the MRZ, the issue date from the printed
   text (it equals expiry − 10 years + 1 day), and the place of birth and authority from the
   printed text.
2. **Given** a back whose MRZ birth check digit is wrong, **When** it is read, **Then** the
   birth date comes from the printed text only if two readings agree and its year equals the
   first four digits of the national ID; otherwise it stays empty.
3. **Given** a printed issue date that does not match the expiry date, **When** it is read,
   **Then** the issue date stays empty and its raw reading is kept.
4. **Given** an expiry date before today (Baghdad time), **When** it is filled or typed,
   **Then** «البطاقة منتهية الصلاحية» shows and is a missing item; the draft still saves.
5. **Given** the marketer corrects a date, **When** the card is read again, **Then** the
   corrected date stays (FR-007).

---

### Edge Cases

- Both images uploaded from two different devices at about the same time: one reading of the
  latest pair is applied; the other device sees the result through the usual change notice.
- The marketer types into a field while the reading is running: the typed value wins.
- The card's surname line is empty (5 of 11 cards in the owner's sample): the marketer types
  the surname the subscriber gives or chooses «لا يوجد لقب على البطاقة» (FR-017).
- The marketer chose «لا يوجد لقب على البطاقة» and a later reading finds a surname: the choice
  counts as the marketer's edit and is not overwritten.
- A name on the card has two words (e.g. «محمد توفيق»): it is kept as one field value.
- The family number has the letter O where a zero belongs: it is corrected; a number that still
  does not match the shape is left empty and the raw reading kept.
- The MRZ birth date is misread: it does not matter for this feature (the form has no birth
  date field); only the MRZ national ID and the check digits are used.
- The photo is rotated by 90 or 180 degrees: it is read in any orientation.
- A screenshot of a card with a black frame around it: handled like any other photo.
- A draft is deleted while its reading is running: the result is dropped.
- The reader returns very low confidence for a field: the field is still filled and marked
  «من البطاقة» for review [assumption: the marketer's review is the safeguard; see Assumptions].
- The reading of the front succeeds and the back fails (or the reverse): the readable side's
  fields are filled, and only the failed side shows «أعد التصوير».

## Requirements *(mandatory)*

### Functional Requirements

**Starting and showing the reading**

- **FR-001**: The system MUST start reading the card automatically once both the front and the
  back images of a draft are uploaded, and again whenever either image is replaced. It MUST NOT
  read with only one side uploaded.
- **FR-002**: While a reading runs, the card section MUST show «جارٍ قراءة البطاقة»; the rest of
  the form MUST stay usable and autosave MUST keep working.
- **FR-003**: The reading result MUST be saved on the server with the draft, so it survives a
  page reload and appears on any device that opens the draft (005 multi-device behaviour).

**Filling the fields**

- **FR-004**: From the front, the system MUST fill: first name, father's name (second name),
  grandfather's name (third name), surname, mother's first name, mother's second name (the
  mother's father on the card) and national ID. From the back it MUST fill the family number.
  It MUST NOT fill the fourth name, the mother's third name or the mother's surname.
- **FR-005**: A value read from the card MUST pass the same rules as a typed value (§5.1 name
  rule; national ID of 12 digits; family number shape). A value that fails is left empty for
  the marketer, and its raw reading is kept.
- **FR-006**: Family number: the letter O in a digit position MUST become zero before the shape
  check. The accepted shape is 4 digits, one Latin letter, then 13 Latin letters or digits (18
  characters; all 11 sample cards match it). An unread or non-matching number stays empty.
- **FR-007**: The reading MUST NOT overwrite a field the marketer has typed, corrected or
  cleared. It MAY fill an empty field and MAY replace a value that came from an earlier reading
  and was not edited.
- **FR-008**: Each field filled from the card MUST show «من البطاقة»; once the marketer edits
  it, it MUST show «عُدِّل يدوياً» instead. The marks MUST be the same on every device.

**Original reading**

- **FR-009**: For every field the reading produced, the system MUST keep the original reading
  (the value as read, after the O→0 and spacing normalizations, and its confidence) beside the
  field's final value, whether or not the marketer changed it (§5.1 item 5). It MUST also keep,
  per side, the full raw result: every front field, the family number, the MRZ fields with the
  result of each check digit (document number, birth date, expiry, composite), and which side
  and how many documents were detected.
- **FR-010**: The original reading MUST belong to the current images: when an image is
  replaced, that side's original reading is replaced by the new one. It MUST be removed with
  the draft when the draft is deleted, and it MUST be available to the submission step (008)
  and to the reviewer (§6.4, feature 010).

**National ID cross-check**

- **FR-011**: The machine-readable zone counts as verified only when the document-number,
  birth-date, expiry and composite check digits are all correct. Only a verified zone MAY be
  used for comparison or filling.
- **FR-012**: With a verified zone, if the front national ID differs from the zone's national
  ID, the national-ID field MUST show «تأكد من الرقم الوطني» with both numbers. The marketer
  MUST resolve it by choosing one of them or typing the number; the choice is saved with the
  draft. Until it is resolved, the national ID counts as missing in the missing-items summary.
- **FR-013**: With a verified zone and no usable front national ID, the system MUST fill the
  national ID from the zone and mark it «من البطاقة».

**Re-shoot and failures**

- **FR-014**: A reading MUST end within 60 seconds of starting (waiting included). Past that,
  or if the reader fails or is unreachable, the card section MUST show «تعذّرت القراءة الآلية،
  أكمل يدوياً» with «أعد المحاولة»; images and draft data MUST stay as they are.
- **FR-015**: A side MUST show «أعد التصوير» with its reason and the tips (no glare; the card
  flat and filling the frame; the right side in the right slot) when: no card of that side is
  found; the photo shows the other side; the photo shows a document that is not the unified
  national card; or the photo shows more than one document. A second detection counts as a
  second document only if it is high-confidence or has readable fields, and two detections with
  the same MRZ document number or that overlap heavily count as one card.
- **FR-016**: «أعد التصوير» and the failure message MUST NOT block anything: the marketer can
  always type the fields by hand. Retaking a photo replaces the image (005 upload behaviour) and
  triggers a new reading (FR-001).

**Surname**

- **FR-017**: The surname stays required (§5.1 v1.7). Beside the surname field the marketer
  MUST be able to choose «لا يوجد لقب على البطاقة» instead of typing; the choice satisfies the
  requirement, empties the surname, is saved with the draft (and later the request), and is
  shown to the reviewer. It is available whether or not the card was read. When a reading finds
  the surname line empty, the form MUST point the marketer to this choice (the reading itself
  does not select it). Typing a surname clears the choice. The full name (§5.1) skips the
  absent surname.

**Reader service, privacy and licence**

- **FR-018**: Card reading MUST run on the company server only. Card images and readings MUST
  NOT be sent to any outside service, and the reader MUST have no internet access; only the
  app's server can reach it.
- **FR-019**: The reader MUST keep no copy of an image or a result after answering, and card
  data (images, names, numbers, the MRZ) MUST NOT appear in any log or error message of the
  reader or the app (§13, Principle II).
- **FR-020**: Reading MUST sit behind a replaceable reader interface with a fake reader that
  returns fixed synthetic results, used in development and in all automated tests (Principle
  VII). No test, fixture or example may use a real card image or real data.
- **FR-021**: Only the owner of a draft can trigger its reading and see its reading; nobody
  else's draft can be read through this feature (Principle IX).
- **FR-022**: The reader's source code, including any changes the project makes to it, MUST be
  available to the app's users as its AGPL-3.0 licence requires, while the rest of the app's
  code stays private: a public copy of the reader (a public fork holding the repository's
  `ocr/` folder) MUST be linked from «حسابي» under «رخص البرمجيات المفتوحة», with the reader's
  name, its licence and the link. Every change to the reader MUST be published to that copy
  before it is deployed.
- **FR-023**: The reader MUST be able to run on the production server within 2 processors and
  2 GB of memory alongside the existing services, and MUST be ready to read again without
  reloading its models between readings.

**Back of the card (owner change, US7; system.md v1.8)**

- **FR-025**: From the back, the system MUST also fill the date of birth, the place of birth,
  the issue date, the expiry date and the issuing authority, with the provenance, marks and
  never-overwrite rules of FR-007–FR-010.
- **FR-026**: Birth and expiry dates MUST come from the machine-readable zone when that field's
  own check digit is right. The birth century comes from the first two digits of the national
  ID (else: a two-digit year later than this year means 19xx); the expiry is 20xx.
- **FR-027**: When the zone cannot give them, the printed dates MAY be used only when confirmed:
  the printed expiry and issue dates must satisfy expiry = issue + 10 years − 1 day; the printed
  birth date needs two agreeing readings and a year equal to the national ID's first four
  digits. The issue date (not in the zone) is accepted only when it matches the expiry date by
  the same rule. Anything unconfirmed stays empty, with its raw reading kept.
- **FR-028**: The place of birth MUST be Arabic letters, spaces, «-» and «/», at most 100
  characters. The issuing authority MUST be snapped to the known text «مديرية الجنسية والمعلومات
  المدنية» when the reading is similar enough (≥ 0.70); otherwise it stays empty. The place of
  birth is filled as read after restoring lost separators (owner decision, option 1): a lone
  «ا» between two words becomes «/», and a known governorate or main city glued to the
  previous letter gets a «-». It stays marked «من البطاقة» for the marketer to check.
- **FR-029**: The five fields are required (missing items). Dates are entered with a date picker
  and stored as dates; a typed date must be a real date.
- **FR-030**: An expiry date before today in Baghdad time MUST show «البطاقة منتهية الصلاحية»
  and add the missing item `card_expired`; the draft still saves, and sending (008) is blocked.
- **FR-031**: The printed rows are located from the positions of the place-of-birth and
  family-number boxes on the straightened back (the card layout is fixed). This geometry and the
  extra recognition live in the reader's wrapper; the acceptance rules above live in the app.

- **FR-032**: When both a birth date and a 12-digit national ID are present and the birth
  year differs from the ID's first four digits, the form MUST show «سنة الميلاد لا تطابق
  الرقم الوطني، تأكد منهما». It is a warning only: not a missing item, and it never blocks
  saving or sending.

**Unchanged from 005**

- **FR-024**: The send button stays disabled (007 and 008); the missing-items summary,
  autosave, drafts list, deletion and image privacy rules of 005 apply unchanged.

### Key Entities

- **Card reading (per draft, per side)**: the latest reading of the front or the back image of
  a draft. Holds which image it belongs to, its state (running, done, needs re-shoot with a
  reason, failed), when it ran, the detected side and number of documents, and the raw result:
  for the front, each field's text and confidence; for the back, the family number and the MRZ
  fields with each check-digit result.
- **Field provenance (per draft, per card field)**: for each of the eight fields, where the
  current value came from (card or typed), the original reading and its confidence, and whether
  the marketer edited it.
- **Back fields (per draft)**: date of birth, place of birth, issue date, expiry date, issuing
  authority, each with its provenance like the other card fields.
- **No-surname choice (per draft)**: whether the marketer chose «لا يوجد لقب على البطاقة».
- **National ID confirmation (per draft)**: when the front and verified MRZ numbers differ, the
  two numbers and the marketer's choice; cleared when the national ID is edited.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a clear card, the fields fill within 15 seconds after the back finishes
  uploading in at least 9 of 10 attempts on the production server with one marketer reading.
- **SC-002**: On the owner's private sample of real cards (checked outside the repository), at
  least 95% of the name fields and 100% of the national IDs read from detected fronts are
  correct, and the family number is correct or left empty (never wrong) in 100% of cards.
- **SC-003**: A field the marketer typed or corrected is overwritten by a reading in 0 cases.
- **SC-004**: 100% of fields filled from the card keep their original reading after the
  marketer edits them.
- **SC-005**: A photo with no readable card shows «أعد التصوير» or the failure message within
  60 seconds in 100% of cases, and in 100% of cases the marketer can still finish the card
  fields by hand.
- **SC-006**: The same card detected twice in one photo never causes «أعد التصوير».
- **SC-007**: Card data appears in 0 lines of the app's and the reader's logs during the test
  runs.
- **SC-009**: On the owner's private sample, the back fields are filled correctly or left
  empty, never wrong: at least 90% of birth and expiry dates and 80% of issue dates filled
  (spike: 11/11, 11/11, 9/11).
- **SC-008**: The marketer types at most the three names that are not on the card (plus any
  field the reading could not fill) for a clear card, instead of all eleven card fields.

## Assumptions

- The reader is ID_Iraqi_Project as evaluated in step 0 (owner's decision); its trained models
  come from the project's published release and are verified by checksum.
- The production server (4 processors, 6.7 GB free memory, 14 GB free disk) can host the reader
  within its limits; measured use was about 1.4 GB of memory.
- Reading starts on the server after the second upload; no reading is done on the phone.
- A low-confidence reading is still filled and marked «من البطاقة»; the marketer's review and
  the reviewer's later comparison (§6.4) are the safeguard. Confidence is stored for the
  reviewer.
- When the reader finds the wrong side in a slot, it does not swap the images by itself; the
  marketer retakes or moves the photo.
- Only the latest reading per side is kept; earlier readings disappear with the images they
  belong to.
- The birth date, place of birth, sex, document number and expiry are read but not shown as form
  fields in this feature; they are kept only inside the raw reading.
- docs/system.md v1.7 (§5.1 and §14) and constitution 1.2.0 (Principle VII, runtime services)
  record the reader service and the rules above, as approved by the owner on 2026-11-23.
- The public fork of the reader is created and owned by the company's account; the owner
  creates it (or authorizes it) before the first deployment of this feature.
