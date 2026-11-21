# Feature Specification: Project Skeleton & Sign-In

**Feature Branch**: `001-project-skeleton-auth`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "الفيزة 001: هيكل المشروع وتسجيل الدخول لتطبيق سِجلّ. ارجع لـ docs/system.md
الأقسام 3 و4.1 و13 و14. المطلوب: دخول برقم الهاتف (موحَّد حسب 8.1) وكلمة السر، ثلاثة أدوار (أدمن رئيسي،
أدمن، مسوّق)؛ إنشاء أدمن رئيسي من متغيرات البيئة عند أول تشغيل؛ توجيه المسوّق لداشبورد هيكلي (زرّان غير
مفعّلين + عدّاد «تم الربط هذا الشهر: 0») والأدمن للوحة هيكلية بقائمة صفحات القسم 10 فارغة؛ واجهة عربية RTL
(شريط سفلي على الهاتف، بار جانبي يمين على الشاشة الكبيرة مع اسم المستخدم ودوره بالأعلى)؛ تسجيل خروج وجلسة
دائمة حتى الخروج أو إيقاف الحساب؛ قفل مؤقت بعد 5 محاولات خاطئة؛ إجبار تغيير كلمة السر بعد التصفير؛ PWA
بأيقونة واسم «سِجلّ». معيار القبول: الأدمن الرئيسي يدخل من الكمبيوتر، ومسوّق تجريبي يدخل من الهاتف ويرى
داشبورده."

**System document references**: `docs/system.md` §3 (roles & permissions), §3.4 (passwords),
§4.1 (layout), §8.1 (phone normalization), §10 (admin pages), §13 (security), §14 (technology).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Main admin signs in for the first time (Priority: P1)

On the very first start of the system, a main admin account exists automatically, created from the
server's configuration. The company owner opens Sijil on a computer, signs in with that phone
number and password, is asked to set a new password, and lands on the admin panel showing the list
of admin pages (all empty for now).

**Why this priority**: Without a first account nobody can enter the system; every later feature
(creating marketers, settings) depends on it.

**Independent Test**: Start the system on an empty database with the main-admin configuration
set, sign in from a desktop browser, change the password, and see the admin panel.

**Acceptance Scenarios**:

1. **Given** an empty system with main-admin phone and password configured, **When** the system
   starts, **Then** exactly one main admin account exists with that phone (normalized).
2. **Given** the main admin already exists, **When** the system restarts (even with different
   configured values), **Then** no second main admin is created and the existing account is not
   modified.
3. **Given** the bootstrap main admin, **When** they sign in for the first time, **Then** they
   must set a new password before reaching any page.
4. **Given** a signed-in main admin on a large screen, **When** the panel opens, **Then** a right
   sidebar lists all §10 pages, and the top bar shows the user's name and role «أدمن رئيسي».
5. **Given** the main admin types the phone as `+964 780 123 4567` or with Arabic digits,
   **When** they sign in with the correct password, **Then** sign-in succeeds (phone normalized to
   `07801234567`).

---

### User Story 2 - Marketer signs in from a phone and sees the dashboard (Priority: P1)

A test marketer opens Sijil on their phone, signs in with their phone number and password, and
sees the marketer dashboard: a large «إضافة مشترك جديد» button, a «إضافة اشتراك لمشترك موجود»
button (both visibly disabled for now), and the counter «تم الربط هذا الشهر: 0». A bottom tab bar
shows الرئيسية، الطلبات، الإشعارات، حسابي.

**Why this priority**: This is the acceptance criterion of the feature and the base screen for
all marketer features (004 onward).

**Independent Test**: With a synthetic test marketer account, sign in from a phone-sized screen
and verify the dashboard and bottom bar.

**Acceptance Scenarios**:

1. **Given** an active marketer account, **When** the marketer signs in, **Then** they land on the
   marketer dashboard, never on the admin panel.
2. **Given** the dashboard, **When** the marketer taps either subscriber button, **Then** nothing
   is submitted and the button is shown as not yet available.
3. **Given** the dashboard, **Then** the counter reads «تم الربط هذا الشهر: 0».
4. **Given** a phone-width screen, **Then** navigation is a bottom bar with four icons; **Given** a
   large screen, **Then** navigation is a right sidebar and the top bar shows name and role
   «مسوّق».
5. **Given** a marketer, **When** they try to open any admin page directly by address, **Then**
   access is refused by the server and they are returned to their dashboard.

---

### User Story 3 - Session stays active until sign-out or deactivation (Priority: P2)

A marketer who signed in on their phone stays signed in across app restarts and days, until they
sign out from «حسابي» or their account is deactivated.

**Why this priority**: Marketers work in the field all day; repeated sign-ins slow them down.

**Independent Test**: Sign in, close and reopen the app, confirm still signed in; sign out,
confirm the sign-in screen appears; deactivate the account and confirm the open session ends.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they close and reopen the app, **Then** they are still
   signed in.
2. **Given** a signed-in user, **When** they choose «تسجيل الخروج», **Then** the session ends on
   that device and protected pages require signing in again.
3. **Given** a signed-in user whose account becomes inactive, **When** they make their next
   action, **Then** the session ends and they see «الحساب موقوف، راجع الإدارة».
4. **Given** a user whose password is reset, **Then** all of their existing sessions end.

---

### User Story 4 - Temporary lock after failed attempts (Priority: P2)

After 5 consecutive wrong passwords for the same phone, sign-in for that account is locked
temporarily, and the user sees how long to wait.

**Why this priority**: Required by §13 to stop password guessing.

**Independent Test**: Enter a wrong password 5 times, confirm the 6th attempt (even with the
correct password) is refused with a wait message; after the lock period the correct password works.

**Acceptance Scenarios**:

1. **Given** 4 failed attempts, **When** the 5th wrong attempt happens, **Then** the account is
   locked for 15 minutes and the message states the remaining wait time in Arabic.
2. **Given** a locked account, **When** the correct password is entered, **Then** sign-in is still
   refused until the lock expires.
3. **Given** a successful sign-in, **Then** the failed-attempt count resets to zero.
4. **Given** a phone that has no account, **When** sign-in fails, **Then** the message is the same
   generic one shown for a wrong password (no hint whether the account exists).

---

### User Story 5 - Forced password change after reset (Priority: P2)

A user whose password was reset (or the bootstrap main admin) must choose a new password right
after signing in, before using anything else.

**Why this priority**: §3.4 replaces "forgot password" with admin resets; the temporary password
must not stay in use.

**Independent Test**: Flag a synthetic account as "must change password", sign in, confirm only the
change-password screen is reachable until a new password is saved.

**Acceptance Scenarios**:

1. **Given** an account flagged "must change password", **When** the user signs in, **Then** only
   the change-password screen is reachable; any other page or server action is refused.
2. **Given** the change-password screen, **When** the new password equals the current one or is
   shorter than 8 characters, or the confirmation does not match, **Then** it is rejected with a
   clear Arabic message.
3. **Given** a valid new password, **When** saved, **Then** the flag is cleared and the user goes to
   their home page (dashboard or admin panel).
4. **Given** a signed-in user, **When** they open «حسابي», **Then** they can change their password
   voluntarily (current password required).

---

### User Story 6 - Install Sijil on the phone (Priority: P3)

A marketer adds Sijil to their phone's home screen from the browser; it appears with the Sijil
icon and the name «سِجلّ» and opens full-screen like an app.

**Why this priority**: Improves daily use but sign-in works without it.

**Independent Test**: On Android (Chrome) and iPhone (Safari), use "Add to Home Screen" and check
icon, name, and full-screen launch.

**Acceptance Scenarios**:

1. **Given** a supported phone browser, **When** the user installs the app, **Then** the home-screen
   icon shows the Sijil icon with the name «سِجلّ».
2. **Given** the installed app, **When** opened, **Then** it launches without the browser address
   bar and starts on the sign-in screen or the user's home page if already signed in.

### Edge Cases

- Phone entered with spaces, dashes, `+964`/`00964` prefix, missing leading `0`, Arabic/Indic digits,
  or hidden direction marks (U+202A, U+202C, U+200F): normalized per §8.1 before lookup.
- Phone that cannot be normalized to `^07\d{9}$`: the form shows «رقم غير صالح» and no attempt is
  counted against any account.
- Bootstrap configuration missing or invalid (bad phone, empty password) on first start: the system
  refuses to complete startup with a clear error for the operator, rather than running without any
  admin. If a main admin already exists, missing configuration is ignored.
- Bootstrap password value must never be printed in logs.
- Deactivated account with correct password: refused with «الحساب موقوف، راجع الإدارة» (lock and
  generic-error rules still apply to wrong passwords).
- Lock expiry while the user is on the sign-in screen: the next attempt is evaluated normally.
- User opens a deep link to a protected page while signed out: shown sign-in, then taken to their
  own home page (a marketer is never forwarded to an admin page).
- Weak network: sign-in shows a clear Arabic message on timeout («تعذّر الاتصال، حاول مرة أخرى»)
  and does not count the attempt if the server never received it.
- Same user signed in on several devices: allowed; signing out on one device does not end others.

## Requirements *(mandatory)*

### Functional Requirements

**Accounts & roles**

- **FR-001**: The system MUST support three roles: main admin (أدمن رئيسي), admin (أدمن), and
  marketer (مسوّق). Each account has exactly one role.
- **FR-002**: Each account MUST have a unique normalized phone number, a display name, a role, an
  active/inactive state, and a "must change password" flag. Admin accounts MUST be able to hold the
  six permission switches of §3.3 (`review`, `link`, `settings`, `marketers`, `reports`,
  `commissions`); managing them is out of scope here (feature 002).
- **FR-003**: On startup, if no main admin exists, the system MUST create one from server
  configuration (phone, name, password), with "must change password" set. If a main admin exists,
  the configuration MUST NOT create or modify any account.

**Sign-in & sessions**

- **FR-004**: Users MUST sign in with phone number and password. The phone MUST be normalized per
  §8.1 before lookup; invalid phones are rejected with «رقم غير صالح».
- **FR-005**: Failed sign-ins MUST show one generic message («رقم الهاتف أو كلمة السر غير صحيحة»)
  regardless of whether the account exists.
- **FR-006**: After 5 consecutive failed attempts for an account, sign-in for that account MUST be
  locked for 15 minutes, including attempts with the correct password. The message MUST state the
  remaining wait in Arabic. A successful sign-in resets the counter.
- **FR-007**: Inactive accounts MUST NOT be able to sign in, and any existing session of an account
  that becomes inactive MUST stop working on its next request.
- **FR-008**: Sessions MUST persist across app and device restarts with no idle timeout, until the
  user signs out, the account becomes inactive, or the password is reset by an admin.
- **FR-009**: Users MUST be able to sign out; signing out ends only the current device's session.
- **FR-010**: Passwords MUST be stored only as strong one-way hashes (§13); no password, session
  secret, or bootstrap secret may appear in logs or error messages.

**Password change**

- **FR-011**: An account with "must change password" set MUST be limited to the change-password
  screen and sign-out until a new password is saved; the server MUST refuse all other actions.
- **FR-012**: New passwords MUST be at least 8 characters, differ from the current password, and be
  confirmed by re-entry. Saving clears the flag and ends the account's other sessions.
- **FR-013**: Signed-in users MUST be able to change their own password from «حسابي» by entering
  the current password.

**Navigation & access**

- **FR-014**: After sign-in, marketers MUST land on the marketer dashboard; main admins and admins
  MUST land on the admin panel.
- **FR-015**: Every server action MUST check the caller's role on the server: marketers MUST be
  refused all admin pages and actions; admins and main admins use the admin panel. The «الأدمنية
  والصلاحيات» page MUST be visible and reachable only to the main admin.
- **FR-016**: The marketer dashboard MUST show the «إضافة مشترك جديد» button (large),
  the «إضافة اشتراك لمشترك موجود» button, both visibly disabled, and the counter «تم الربط هذا
  الشهر: 0». الطلبات and الإشعارات show an empty "coming soon" state; حسابي shows the user's
  name, phone, role, change password, and sign out.
- **FR-017**: The admin panel MUST list the §10 pages in order: الرئيسية، طلبات بالانتظار، بانتظار
  الربط، المشتركون، المسوّقون، الإعدادات، الأدمنية والصلاحيات، التقارير والتصدير، الاستيراد، النسخ
  الاحتياطي، سجل العمليات. Each opens an empty placeholder page. The admin panel also provides
  account access (name, change password, sign out).

**Layout & app**

- **FR-018**: All UI text MUST be Arabic and the layout MUST be right-to-left.
- **FR-019**: On phone-width screens the marketer app MUST use a bottom icon bar (الرئيسية،
  الطلبات، الإشعارات، حسابي); the admin panel MUST use a compact menu. On large screens both MUST use a
  right sidebar, with the user's name and role at the top.
- **FR-020**: The app MUST be installable to the home screen on Android and iPhone with the name
  «سِجلّ» and the Sijil icon, launching full-screen.
- **FR-021**: Network failures MUST show a clear Arabic message and allow retry.

**Audit**

- **FR-022**: The audit log MUST record, with who/when/what: creation of the bootstrap main admin,
  account lockouts, and password changes (never the password itself). Each entry is permanent.

**Times**

- **FR-023**: All times (lock expiry, audit entries) MUST be stored in UTC and displayed in
  Baghdad time.

### Key Entities

- **User account**: A person who signs in. Attributes: display name, normalized phone (unique),
  role (main admin / admin / marketer), active flag, must-change-password flag, admin permission
  switches, failed-attempt count, lock-until time, created/updated times. Never deleted, only
  deactivated.
- **Session**: A signed-in device for one account. Ends on sign-out, deactivation, or password
  reset/change (other devices).
- **Audit entry**: Who did what, when, with before/after values where applicable (never secrets).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The main admin can sign in from a desktop browser and reach the admin panel within
  1 minute of the first system start (including the forced password change).
- **SC-002**: A test marketer can sign in from a phone and see the dashboard in under 30 seconds,
  on both Android and iPhone.
- **SC-003**: 100% of phone formats listed in Edge Cases that represent a valid Iraqi mobile number
  sign in successfully; 100% of invalid formats are rejected with «رقم غير صالح».
- **SC-004**: The 6th sign-in attempt after 5 failures is refused in 100% of tests, and sign-in
  works again after 15 minutes.
- **SC-005**: A marketer is refused 100% of admin pages and actions when attempted directly.
- **SC-006**: A signed-in marketer remains signed in after closing the app and reopening it the
  next day.
- **SC-007**: The app installs to the home screen on Android and iPhone showing the name «سِجلّ».

## Assumptions

- Lock duration is 15 minutes (not specified by the owner; a common default). Lock counting is per
  account; repeated failures for non-existent phones are handled by general rate limiting.
- Minimum password length is 8 characters; no other complexity rules, to keep field use simple.
- The bootstrap main admin is forced to change the configured password on first sign-in.
- Creating admins and marketers, resetting passwords, and editing permissions belong to feature 002.
  For acceptance testing in 001, a synthetic test marketer (fake name and phone) is created by a
  development-only seed step, never in production data.
- Hiding admin pages by individual permission switches belongs to feature 002; in 001 all admins
  see the full page list (except «الأدمنية والصلاحيات», main admin only), and all pages are empty.
- The Sijil icon is a simple placeholder icon until the company supplies a final logo.
- Push notifications, offline use beyond showing a network error, and store packaging are out of
  scope.
- The system runs on the company server reachable at `https://sijil.t3cftth.net` with HTTPS; it can
  also be started locally for development and testing in one command.
