# Feature Specification: New Subscriber Form (single page)

**Feature Branch**: `005-subscriber-form`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "الفيزة 005: استمارة «إضافة مشترك جديد» في صفحة واحدة. ارجع لـ docs/system.md القسم 5
(عدا القراءة الآلية والتحقق، تأتيان في 006 و007). صفحة واحدة تنزل بالترتيب: البطاقة الوطنية (وجه ثم ظهر، تصوير
أو رفع)، الاسم والرقم الوطني والرقم العائلي (يدوي حالياً)، موقع البيت (موقعي الحالي أو خريطة Google بصور القمر
الصناعي مع دبوس قابل للسحب، العنوان، أقرب نقطة دالّة)، الاشتراك (المنطقة ثم البرج التابع ثم الفئة، مع عرض
السعرين)، هاتف المشترك. القوائم من /api/catalog (الفعّالة فقط)، وعند الحفظ يُنسخ على الطلب اسم المنطقة ورمز البرج
واسم الفئة وسعراها (FR-006 من 004). مفتاح الخريطة من متغير بيئة فقط ومقيّد بالدومين. ضغط الصور على الهاتف (1600px،
JPEG ~0.8) مع شريط تقدّم وإعادة المحاولة. حفظ تلقائي كمسودة على السيرفر وفتحها من جهاز آخر؛ قائمة «المسودات» في
صفحة الطلبات؛ آخر حفظ هو المعتمد مع تنبيه في الجهاز الآخر. المسوّق يحذف مسودته غير المُرسلة ويُسجَّل الحذف. الرقم
الوطني 12 رقماً، الهاتف حسب 8.1، كل الحقول إلزامية. زر الإرسال غير مفعّل (ينتظر 007 و008) مع ملخص النواقص. الصور في
مخزن خاص دائم يدخل في النسخ الاحتياطي، لا رابط عام، يراها صاحب الطلب والأدمن فقط. معيار القبول: مسوّق يملأ نصف
الاستمارة على هاتف، يفتحها من هاتف آخر ويجد كل شيء محفوظاً بما فيه الصور."

**System document references**: `docs/system.md` v1.4 §4.3 (requests page, «مسودات» tab), §5
(intro, §5.1 items 1, 2, 5 (manual part) and 6, §5.2, §5.3, §5.4 item 1, §5.5), §7.2 (`draft`
status and its grey color), §8.1 (phone normalization), §13 (private image storage, access
logging), §15 (images are part of the backup); constitution Principles II, III, IV, V, IX.

**Out of scope (later features)**: card reading / OCR and «أعد التصوير» (006); the «تحقّق»
button and OTP (007); the duplicate check, decision and actual submission (008); request number
assignment (008); admin screens for requests (010).

**Builds on**: feature 001 (sign-in, marketer layout), 002 (roles, `review` permission, audit
log), 004 (catalog of active regions, towers and categories; FR-006 copy rule).

## Clarifications

### Session 2026-11-22 (owner decisions given in the request)

- A draft is not yet a request, so the constitution's no-delete rule does not cover it. The
  marketer may delete their own unsubmitted draft; the deletion is audited (system.md §5 v1.4).
- Two devices editing the same draft: the last save wins, and the other device is told the
  draft changed.
- The send button stays disabled in this feature; a summary of missing items is shown instead.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fill the form and have it saved automatically (Priority: P1)

A marketer taps «إضافة مشترك جديد» on the dashboard. One page opens with the sections in order:
national card, card data, house location, subscription, subscriber phone. Every change is saved
to the server as a draft shortly after it is made, and a small status line shows «جارٍ الحفظ…»,
«محفوظ» or «لم يُحفظ — إعادة المحاولة».

**Why this priority**: The form is the base of every request in the system; autosave is what
makes it usable in the field on weak networks.

**Independent Test**: Sign in as a marketer, start a new subscriber, type the name and the
address, close the browser, reopen the draft from «الطلبات ← مسودات», and find both values.

**Acceptance Scenarios**:

1. **Given** a signed-in marketer on the dashboard, **When** they tap «إضافة مشترك جديد»,
   **Then** a new draft is opened on one page with the five sections in the order of §5.
2. **Given** an open draft, **When** the marketer changes any field and stops typing for about
   1 second (or leaves the field), **Then** the change is saved on the server and the status
   shows «محفوظ».
3. **Given** the network is down, **When** a save fails, **Then** the status shows «لم يُحفظ»
   with «إعادة المحاولة», the typed values stay on screen, and saving is retried automatically
   when the connection returns.
4. **Given** a marketer starts a new subscriber but enters nothing, **Then** no empty draft is
   left in the drafts list (a draft is created on the first real change).
5. **Given** an admin, **Then** they cannot create drafts; the form is for marketers only (§3.1).

---

### User Story 2 - Card images: capture, compress, upload with progress (Priority: P1)

In the card section the marketer fills «وجه البطاقة» then «ظهر البطاقة». Each slot has two
buttons, «تصوير» (camera) and «من المعرض» (gallery). The image is compressed on the phone before upload, a
progress bar shows the upload, and a failed upload can be retried without picking the image
again. After upload the slot shows a thumbnail with «تغيير».

**Why this priority**: Card images are the core evidence of every request and part of the
acceptance criterion; they are also the heaviest data on weak networks.

**Independent Test**: Upload a large synthetic card image (e.g. 4000×3000), see the progress
bar, cut the network mid-upload, press «إعادة المحاولة», and confirm the stored image is at most
1600px on its longest edge and is a JPEG.

**Acceptance Scenarios**:

1. **Given** either slot, **Then** it shows two separate buttons, «تصوير» (opens the camera) and
   «من المعرض» (opens the gallery). The gallery button never opens the camera directly on
   Android or iPhone.
2. **Given** the front slot, **When** the marketer takes or picks a photo, **Then** it is
   compressed on the device (longest edge at most 1600px, JPEG quality about 0.8) before upload.
3. **Given** an upload in progress, **Then** a progress bar shows the percentage, and the rest of
   the form stays usable.
4. **Given** an upload fails, **Then** the slot shows «فشل الرفع» with «إعادة المحاولة», which
   retries with the same compressed image.
5. **Given** an uploaded image, **When** the marketer taps «تغيير» and uploads another,
   **Then** the new image replaces the old one in the draft.
6. **Given** a file that is not an image, or an image larger than the size limit after
   compression, **Then** it is refused with a clear Arabic message.
7. **Given** the back slot, **Then** it can be filled before the front; both are required.

---

### User Story 3 - Open the same draft from another device (Priority: P1)

The marketer fills half the form on phone A, then signs in on phone B with the same account,
opens «الطلبات ← مسودات», and finds the draft with every value and both card images. If phone A
is still open and phone B saves a change, phone A shows «تغيّرت المسودة من جهاز آخر» with
«تحميل الأحدث».

**Why this priority**: This is the feature's acceptance criterion.

**Independent Test**: On phone A fill card images, name, location and region/tower; on phone B
open the draft and verify everything including both images; change the address on B and see the
notice on A.

**Acceptance Scenarios**:

1. **Given** a draft saved on device A, **When** the same marketer opens it on device B,
   **Then** all saved fields, the location pin and both card images appear.
2. **Given** the draft is open on both devices, **When** device B saves, **Then** B's save is the
   current version, and device A shows «تغيّرت المسودة من جهاز آخر» within about 30 seconds, or
   at its next save attempt at the latest.
3. **Given** device A shows that notice, **Then** A stops autosaving until the marketer chooses
   «تحميل الأحدث» (loads B's version) or «الإبقاء على نسختي» (saves A's version, which then
   becomes the current one and B gets the notice).
4. **Given** another marketer, **Then** they never see this draft in their list and the server
   refuses to open it or its images.

---

### User Story 4 - Drafts list and deleting a draft (Priority: P2)

On «الطلبات» the «مسودات» tab lists the marketer's drafts, newest change first, each showing the
subscriber name (or «بدون اسم»), the tower if chosen, the last save time in Baghdad time, and how
many items are still missing. Tapping one opens it. «حذف» removes an unsubmitted draft after a
confirmation, and the deletion is written to «سجل العمليات».

**Why this priority**: Needed to reach drafts from another device and to clean up abandoned
ones; the form works without it from the dashboard flow.

**Independent Test**: Create two drafts, see both in «مسودات» with the right order and grey
status color, delete one after confirming, and see the audit entry.

**Acceptance Scenarios**:

1. **Given** a marketer with drafts, **When** they open «الطلبات ← مسودات», **Then** only their
   own drafts are listed, newest change first, with the grey «مسودة» color (§7.2).
2. **Given** the tab's search box, **When** the marketer types part of a name or phone, **Then**
   the list is filtered.
3. **Given** a draft, **When** the marketer taps «حذف» and confirms «حذف المسودة نهائياً؟»,
   **Then** the draft and its images are removed and one audit entry records who deleted it,
   when, and which draft (no card data, national ID or images in the entry).
4. **Given** a draft that has been submitted (from feature 008 on), **Then** «حذف» is not shown
   and the server refuses the deletion.
5. **Given** a draft deleted on device A while open on device B, **Then** B shows «حُذفت هذه
   المسودة» and stops saving.

---

### User Story 5 - Field validation and missing-items summary (Priority: P2)

Every field is required. Fields are checked as the marketer goes, with the Arabic reason under
the field. At the bottom of the page a «النواقص» summary lists what is still missing or invalid,
each item a link that scrolls to its field. The «إرسال» button is shown disabled with the note
«الإرسال يتفعّل بعد إضافة التحقق من الهاتف».

**Why this priority**: Prepares a complete request for features 007/008; drafts can be saved
while incomplete, so it does not block US1–US4.

**Independent Test**: Enter an 11-digit national ID and the phone «+964 780 123 4567», see the
ID error, see the phone stored as 07801234567, and check that the summary lists every empty
field and the send button stays disabled.

**Acceptance Scenarios**:

1. **Given** a national ID that is not exactly 12 digits after converting Arabic-Indic digits
   and removing spaces, **Then** it shows «الرقم الوطني 12 رقماً».
2. **Given** a phone such as «٠٧٨٠ ١٢٣ ٤٥٦٧», «+9647801234567» or «7801234567», **Then** it is
   normalized per §8.1 to 07801234567; anything that does not end as `^07\d{9}$` shows «رقم غير
   صالح».
3. **Given** the family number, **Then** it is required and stored exactly as typed (letters and
   digits, §2).
4. **Given** any empty or invalid item (either card image, name, national ID, family number,
   location pin, address, nearest landmark, region, tower, category, phone), **Then** it appears
   in «النواقص».
5. **Given** a complete and valid form, **Then** «النواقص» shows «كل الحقول مكتملة» and the send
   button is still disabled in this feature.
6. **Given** an invalid value, **Then** it is still saved in the draft (drafts may be incomplete
   or invalid), and the server repeats the same checks when it reports the missing items.

---

### User Story 6 - House location on the satellite map (Priority: P2)

In the location section the marketer taps «استخدم موقعي الحالي» to drop the pin at the phone's
position, or «حدّد البيت على الخريطة» to open a satellite map and drag the pin onto the house.
Below are the «العنوان» and «أقرب نقطة دالّة» text fields.

**Why this priority**: Required for every request, but the rest of the form works without it.

**Independent Test**: Allow location, tap «استخدم موقعي الحالي», drag the pin to another roof,
reload the draft on another device, and see the pin in the dragged position.

**Acceptance Scenarios**:

1. **Given** location permission is granted, **When** the marketer taps «استخدم موقعي الحالي»,
   **Then** the pin is placed at the current position and the map opens in satellite view there.
2. **Given** the map, **When** the marketer drags the pin or taps a spot, **Then** the pin's new
   position is saved in the draft.
3. **Given** location permission is refused or the position cannot be read, **Then** an Arabic
   message explains it and the marketer can still place the pin on the map by hand.
4. **Given** the map cannot load (no key configured or no network), **Then** the section says
   «الخريطة غير متوفرة حالياً» and «استخدم موقعي الحالي» still works.
5. **Given** the map key, **Then** it comes only from server configuration, never from source
   code, and is restricted to the app's domain in the provider's console.

---

### User Story 7 - Subscription choice with prices (Priority: P2)

The marketer picks a region, then a tower from that region only, then a category. Both prices of
the chosen category are shown («الشهر التجريبي: 20,000 د.ع — الشهر الثاني: 35,000 د.ع»). The
draft keeps a copy of the region name, tower code, category name and both prices.

**Why this priority**: Required for every request; depends only on feature 004's catalog.

**Independent Test**: With «العلم», ALM01 and PLUS (20,000 / 35,000) set up, pick them, see both
prices, change the region, and see the tower choice cleared.

**Acceptance Scenarios**:

1. **Given** the catalog, **Then** only active regions, active towers of active regions, and
   active categories are offered (004 FR-014).
2. **Given** a chosen region, **Then** the tower list shows only that region's towers; changing
   the region clears the chosen tower.
3. **Given** a chosen category, **Then** both prices show with thousands separators and «د.ع».
4. **Given** a save with a subscription choice, **Then** the draft stores the region name, tower
   code, category name, trial-month price and second-month price as copies taken at that save.
5. **Given** a draft whose chosen region, tower or category was deactivated, or whose prices were
   changed by the admin since it was saved, **When** the draft is opened, **Then** a deactivated
   choice is cleared with the note «لم يعد متاحاً، اختر من جديد», and changed prices are refreshed
   to the current ones with the note «تغيّر السعر». Final copies are fixed at submission (008).

### Edge Cases

- The marketer's session expires mid-form: a sign-in dialog opens over the form, values stay on
  screen, saving resumes after signing in again as the same account, and nothing typed is lost
  on that device.
- Two tabs of the same draft on one phone behave like two devices: the outdated tab shows the
  change notice.
- Slow upload and autosave at the same time: text fields keep saving independently of image
  uploads.
- Leaving the page during an upload: the app warns «يوجد رفع غير مكتمل»; if the marketer leaves
  anyway, the slot is empty on return and can be filled again.
- Very old or broken image files, rotated phone photos: the orientation is corrected before
  compression so the stored image is upright.
- Arabic-Indic digits are accepted in the national ID and phone fields.
- Leading/trailing spaces are trimmed in all text fields; empty after trimming counts as missing.
- The catalog has no active towers in a region: the region is still shown but the tower list says
  «لا توجد أبراج فعّالة».
- An archived or deactivated marketer: cannot sign in, so their drafts are unreachable but kept;
  an admin cannot open them from this feature's screens.
- A marketer with many drafts: the list shows them all, newest first (no automatic expiry in this
  feature).

## Requirements *(mandatory)*

### Functional Requirements

**Access**

- **FR-001**: Only marketers MAY create, edit and delete drafts, and only their own. The server
  MUST check ownership on every draft and image action (Principle IX).
- **FR-002**: Card images MUST be readable only by the owning marketer, the main admin, and
  admins holding `review`; every image access MUST be written to the access log with who, when
  and which image (§13, Principle II).

**Form**

- **FR-003**: The form MUST be one page with the sections in this order: national card (front,
  then back), card data (name, national ID, family number), house location (pin, address,
  nearest landmark), subscription (region, tower, category with both prices), subscriber phone.
- **FR-004**: Card data fields MUST be entered by hand in this feature.

**Images**

- **FR-005**: Each card side MUST offer two separate buttons, «تصوير» (camera) and «من المعرض»
  (gallery); the gallery button MUST open the gallery on Android and iPhone. The device MUST
  correct orientation and compress the image to at most 1600px on the longest edge, JPEG quality
  about 0.8, before upload.
- **FR-006**: Uploads MUST show progress and MUST allow retry of a failed upload without picking
  the image again. The server MUST accept only images and MUST refuse files over 5 MB.
- **FR-007**: Card images MUST be stored in private, persistent server storage outside the web
  root that is included in the backups (§15; the nightly job itself is feature 015, and until then
  the volume is backed up by the documented manual command), and MUST NOT be reachable by any public or
  guessable link.

**Location**

- **FR-008**: The location section MUST offer «استخدم موقعي الحالي» and a satellite map with a
  draggable pin; the saved pin position MUST be restored when the draft is reopened.
- **FR-009**: The map key MUST come only from environment configuration (documented in
  `.env.example`), never from source code; the owner restricts it to the app domain in the
  provider's console. If the key is missing, the form MUST still work without the map.

**Subscription**

- **FR-010**: Region, tower and category choices MUST come from the catalog of feature 004
  (active items only), with towers filtered by the chosen region.
- **FR-011**: Each draft save MUST store copies of the region name, tower code, category name,
  trial-month price and second-month price as they are at that save; when a draft is reopened,
  deactivated choices are cleared and changed prices refreshed (US7 scenario 5). The copies become
  final at submission (feature 008; 004 FR-006; Principle IV).

**Validation**

- **FR-012**: All fields of FR-003 and both card images MUST be required. The national ID MUST be
  exactly 12 digits after converting Arabic-Indic digits and removing spaces. The phone MUST be
  normalized and validated per §8.1. The family number is stored as typed. Text fields are trimmed
  and limited to reasonable lengths (name 100, address 300, landmark 200 characters).
- **FR-013**: The page MUST show a «النواقص» summary listing every missing or invalid item, each
  linking to its field. The server MUST compute the same list for a draft.
- **FR-014**: The «إرسال» button MUST be shown but disabled in this feature (it waits for 007 and
  008), with a short note explaining why.

**Drafts**

- **FR-015**: Every change MUST be saved to the server as a draft after a short pause (about 1
  second) or when the field loses focus, with a visible save status and automatic retry. A draft
  is created on the first real change only.
- **FR-016**: A draft MUST be openable from any device signed in to the same account, with every
  saved value and both images.
- **FR-017**: Concurrent edits: the last save MUST win. A device whose version is outdated MUST
  show «تغيّرت المسودة من جهاز آخر» within about 30 seconds or at its next save, pause autosave,
  and offer «تحميل الأحدث» or «الإبقاء على نسختي».
- **FR-018**: The «مسودات» tab of «الطلبات» MUST list the marketer's own drafts, newest change
  first, with name (or «بدون اسم»), tower, last save time in Baghdad time, number of missing
  items, the grey draft color, and search by name or phone. Other tabs of §4.3 MAY show an empty
  state until their features arrive.
- **FR-019**: The marketer MUST be able to delete an unsubmitted draft after a confirmation. The
  draft and its images are removed permanently, and one audit entry records who, when and the
  draft reference, without card data or images (system.md §5 v1.4; Principles II, III).
- **FR-020**: A draft has status `draft` (§7.2) and has no request number; numbers are given at
  submission (feature 008).

**General**

- **FR-021**: All screens MUST be Arabic, right-to-left, phone-first, and work on iPhone and
  Android browsers (Principle V).
- **FR-022**: Card data, national IDs and images MUST NOT appear in application logs or error
  messages (Principle II).

### Key Entities

- **Draft request**: owner marketer, status `draft`, subscriber name, national ID, family number,
  location (latitude, longitude), address, nearest landmark, chosen region/tower/category with
  copies of region name, tower code, category name and both prices, subscriber phone (normalized),
  a version that changes on every save, created and last-saved times (UTC).
- **Card image**: belongs to one draft, side (front or back), stored privately, size and
  dimensions, upload time. One current image per side.
- **Image access record**: who opened which image and when.
- **Audit entry** (existing): draft deletion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Acceptance: a marketer fills half the form (both card images, card data, location)
  on one phone, opens the draft on a second phone, and finds 100% of the entered values and both
  images.
- **SC-002**: A typed change is saved on the server within 5 seconds on a normal mobile
  connection, and no typed value is lost when the network drops briefly.
- **SC-003**: A typical phone photo uploads as an image of at most 1600px longest edge and under
  about 600 KB, so one card side uploads in under 10 seconds on a slow 3G-class connection.
- **SC-004**: When the same draft is edited on two devices, the outdated device shows the change
  notice within 30 seconds in 100% of trials.
- **SC-005**: 100% of attempts by another marketer, an unauthenticated user, or an admin without
  `review` to open a draft or a card image are refused, and 100% of image accesses are logged.
- **SC-006**: 100% of invalid national IDs and phones are flagged with an Arabic reason and listed
  in «النواقص».
- **SC-007**: 100% of draft deletions produce one audit entry.

## Assumptions

- The map provider is the one named in system.md §14 (satellite imagery). Its default view, when
  no pin and no device position exist, is a fixed center configured on the server.
- The location pin stores coordinates only; the address and landmark are typed by the marketer
  (no automatic address lookup).
- Image access is granted to the main admin and admins holding `review` (the admins who review
  requests); admin screens that show these images arrive in feature 010.
- Replaced and deleted draft images are removed from storage; submitted requests' images are never
  removed (from feature 008).
- Drafts never expire automatically in this feature.
- Autosave and the change notice need a connection; this feature does not add full offline mode
  beyond keeping unsaved values on screen and retrying.
- Tests use synthetic card images and made-up subscriber data only (CLAUDE.md).
