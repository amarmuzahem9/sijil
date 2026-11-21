# Feature Specification: Accounts & Permissions

**Feature Branch**: `002-accounts-permissions`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "الفيزة 002: إدارة الحسابات والصلاحيات. ارجع لـ docs/system.md القسم 3 والقسم 10
(صفحتا المسوّقين والأدمنية). المطلوب: الأدمن الرئيسي يضيف أدمن: الاسم، الهاتف، كلمة سر مؤقتة، ويختار صلاحياته
من: review, link, settings, marketers, reports, commissions (مفاتيح تشغيل/إطفاء بأسماء عربية). الأدمن الرئيسي
يعدّل صلاحيات أي أدمن أو يوقفه. من له صلاحية marketers يضيف مسوّقاً (الاسم، الهاتف، كلمة سر مؤقتة)، يعدّله،
يوقفه، ويصفّر كلمة سره (تُجبر المسوّق على تغييرها). صفحة «حسابي» لكل مستخدم: الاسم، الهاتف، تغيير كلمة السر.
كل عملية تُسجل في سجل العمليات. الحساب الموقوف لا يستطيع الدخول وتنتهي جلساته فوراً. لا يمكن إيقاف الأدمن
الرئيسي أو حذف صلاحياته. معيار القبول: الأدمن الرئيسي يضيف أدمناً بصلاحية marketers فقط، وهذا الأدمن يضيف
مسوّقاً، ولا يرى صفحة الإعدادات."

**System document references** (system.md v1.1): §3 (roles & permissions), §3.2 (main admin), §3.4 (passwords), §3.5 («حسابي»),
§10 pages 5 «المسوّقون» and 7 «الأدمنية والصلاحيات», §10 page 11 (audit log), §13 (security).

**Builds on**: feature 001 (accounts, roles, sessions, forced password change, audit log).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Main admin adds an admin with chosen permissions (Priority: P1)

The main admin opens «الأدمنية والصلاحيات», taps «إضافة أدمن», enters a name, a phone number and a
temporary password, and turns on the permissions this admin should have using six on/off switches
labelled in Arabic. The new admin signs in, is forced to set a new password, and then sees only the
admin pages that match the permissions they were given.

**Why this priority**: This is the first half of the acceptance criterion; the company cannot
delegate any work until admins can be created with limited permissions.

**Independent Test**: As main admin, create an admin with only «إدارة المسوّقين» on; sign in as that
admin, change the password, and confirm the menu shows «المسوّقون» but not «الإعدادات», and that
opening the settings page directly by address is refused by the server.

**Acceptance Scenarios**:

1. **Given** the main admin on «الأدمنية والصلاحيات», **When** they add an admin with a valid name,
   phone, temporary password and the `marketers` switch on only, **Then** the account is created
   with role «أدمن», that single permission, and "must change password" set.
2. **Given** the new admin signs in with the temporary password, **Then** they must set a new
   password before reaching any page.
3. **Given** an admin with only `marketers`, **When** the admin panel opens, **Then** the menu shows
   «الرئيسية» and «المسوّقون» and hides «الإعدادات», «الأدمنية والصلاحيات», and every other page
   whose permission is off.
4. **Given** an admin with only `marketers`, **When** they open the settings page or call any
   settings action directly, **Then** the server refuses with «ليست لديك صلاحية» and nothing changes.
5. **Given** the add-admin form, **When** the phone already belongs to any account (admin or
   marketer), **Then** creation is refused with «رقم الهاتف مستخدم لحساب آخر».
6. **Given** any account other than the main admin, **When** they try to open «الأدمنية والصلاحيات»
   or create/edit an admin, **Then** the server refuses.

---

### User Story 2 - Admin with `marketers` permission manages marketers (Priority: P1)

An admin who holds the `marketers` permission opens «المسوّقون», sees the list of marketer accounts
with their state, adds a marketer (name, phone, temporary password), edits a marketer's name or
phone, deactivates or reactivates a marketer, and resets a marketer's password to a new temporary
one that the marketer must change at next sign-in.

**Why this priority**: Second half of the acceptance criterion; marketers cannot work until someone
can create their accounts, and §3.4 makes admin reset the only password-recovery path.

**Independent Test**: As the `marketers`-only admin from Story 1, add a synthetic marketer; sign in
as that marketer and see the forced password change; back as admin, reset the password and confirm
the marketer's open session ends and the new temporary password forces another change.

**Acceptance Scenarios**:

1. **Given** an admin with `marketers`, **When** they add a marketer with valid name, phone and
   temporary password, **Then** the marketer account is created active with "must change password"
   set, and appears in the list.
2. **Given** a marketer in the list, **When** the admin edits the name or phone, **Then** the change
   is saved (phone normalized per §8.1 and still unique) and recorded in the audit log with before
   and after values.
3. **Given** an active marketer signed in on a phone, **When** the admin deactivates the account,
   **Then** the marketer's very next action is refused, they are signed out with «الحساب موقوف،
   راجع الإدارة», and they cannot sign in again.
4. **Given** a deactivated marketer, **When** the admin reactivates it, **Then** the marketer can
   sign in again with their existing password.
5. **Given** a marketer, **When** the admin resets the password with a new temporary password,
   **Then** all of the marketer's sessions end, "must change password" is set, and the marketer must
   choose a new password at the next sign-in.
6. **Given** an admin without `marketers`, **When** they open «المسوّقون» or call any marketer
   action directly, **Then** the server refuses and the page is not in their menu.
7. **Given** the main admin, **Then** they can do everything in this story (main admin holds all
   permissions).

---

### User Story 3 - Main admin edits an admin's permissions or deactivates them (Priority: P2)

The main admin opens an existing admin, changes their name or phone, flips permission switches on
or off, resets their password, or deactivates/reactivates them. Changes take effect on the admin's
next action without needing to sign out.

**Why this priority**: Needed to correct mistakes and to remove access when a staff member leaves,
but the system is usable with initial permissions alone.

**Independent Test**: Turn `settings` on for the `marketers`-only admin while they are signed in;
their next page load shows «الإعدادات». Turn it off again; the page disappears and direct access is
refused. Deactivate the admin; their next action signs them out.

**Acceptance Scenarios**:

1. **Given** a signed-in admin, **When** the main admin turns a permission on or off, **Then** the
   admin's next request is evaluated with the new permissions (menu and server checks both).
2. **Given** an admin, **When** the main admin saves the permissions, **Then** the audit log records
   the permission list before and after.
3. **Given** a signed-in admin, **When** the main admin deactivates them, **Then** all of their
   sessions end immediately and they cannot sign in until reactivated.
4. **Given** an admin, **When** the main admin resets their password, **Then** all of their
   sessions end and they must change the password at next sign-in.
5. **Given** the main admin's own account, **When** anyone (including the main admin) tries to
   deactivate it, change its role, or remove any of its permissions, **Then** the action is refused
   and the main admin row shows no deactivate button and no permission switches (shown as «كل
   الصلاحيات»).

---

### User Story 4 - «حسابي» page for every user (Priority: P2)

Every signed-in user (main admin, admin, marketer) opens «حسابي» and sees their name, phone and role,
changes their password by entering the current one and the new one twice, and can sign out.

**Why this priority**: Gives every user a place to change their own password; most of it already
exists from feature 001 and only needs to be completed and made consistent.

**Independent Test**: As each of the three roles, open «حسابي», confirm name, phone and role are
shown, change the password, sign out and sign in with the new password.

**Acceptance Scenarios**:

1. **Given** any signed-in user, **When** they open «حسابي», **Then** they see their name, phone,
   and role in Arabic, plus «تغيير كلمة السر» and «تسجيل الخروج».
2. **Given** «تغيير كلمة السر», **When** the current password is wrong, the new password is shorter
   than 8 characters or equals the current one, or the confirmation differs, **Then** the change is
   refused with a clear Arabic message.
3. **Given** a valid change, **Then** the new password works, the user's other devices are signed
   out, and the change is recorded in the audit log (without the password).
4. **Given** «حسابي» for a marketer or admin, **Then** the name and phone are shown read-only, with
   no way to edit them; the phone is the sign-in identifier and cannot be changed by its owner. Name
   or phone corrections are made by an admin (marketers) or the main admin (admins).
5. **Given** «حسابي» for the main admin, **When** they edit their name (2–100 characters) and save,
   **Then** the new name is shown everywhere and the change is recorded in the audit log with before
   and after; the phone stays read-only.

---

### User Story 5 - Every account action is recorded (Priority: P2)

Every account action in this feature is written permanently to the audit log: who did it, when,
what, and the values before and after — never passwords.

**Why this priority**: Principle III; disputes about who created, stopped or reset an account must
be answerable.

**Independent Test**: Perform each action in Stories 1–4 and confirm one audit entry per action,
with the right actor, target, time in Baghdad time, and no password data.

**Acceptance Scenarios**:

1. **Given** any of: admin created, marketer created, account edited (name/phone), permissions
   changed, account deactivated, account reactivated, password reset, own password changed, **When**
   it succeeds, **Then** exactly one audit entry is written with actor, target account, action,
   time, and before/after of the changed fields.
2. **Given** a refused action (no permission, duplicate phone, protected main admin), **Then** no
   account data changes.
3. **Given** any audit entry, **Then** it never contains a password, temporary password, hash, or
   session token.
4. **Given** the main admin opens «سجل العمليات», **Then** they see a read-only list of entries,
   newest first, each showing who, when (Baghdad time), the action in Arabic, the target account,
   and the values before and after.
5. **Given** the list, **When** the main admin filters by a date range and/or by the person who
   performed the action, **Then** only matching entries are shown, still newest first.
6. **Given** any account other than the main admin, **When** they open «سجل العمليات» or request
   audit entries directly, **Then** the server refuses and the page is not in their menu.
7. **Given** the «سجل العمليات» page, **Then** there is no way to add, edit, or delete an entry.

### Edge Cases

- Phone entered in any §8.1 format (spaces, `+964`, Arabic digits, direction marks) is normalized
  before the uniqueness check; an invalid phone shows «رقم غير صالح».
- Editing an account's phone to one already used by another account (any role, active or inactive)
  is refused; keeping the same phone is allowed.
- Changing a marketer's phone does not end their sessions; their next sign-in uses the new phone.
- Temporary password shorter than 8 characters is refused when creating or resetting.
- Name empty or only spaces, or longer than 100 characters, is refused; leading/trailing spaces are
  trimmed.
- Adding an admin with all switches off is allowed: they can sign in and see only «الرئيسية» and
  «حسابي».
- An admin with `marketers` cannot view, edit, deactivate, or reset any admin or the main admin —
  only marketers.
- An admin cannot change their own permissions, and cannot deactivate themselves.
- An admin whose `marketers` permission is removed while they have the marketers page open gets
  «ليست لديك صلاحية» on their next action and the page leaves their menu.
- Deactivating an already deactivated account (or reactivating an active one) changes nothing and
  writes no audit entry.
- Two admins editing the same marketer at once: the last save wins, and both saves are in the audit
  log.
- A deactivated account with the correct password is refused at sign-in with «الحساب موقوف، راجع
  الإدارة», while wrong passwords still count towards the 15-minute lock (feature 001 rules).
- Accounts are never deleted; there is no delete button anywhere.

## Requirements *(mandatory)*

### Functional Requirements

**Permissions**

- **FR-001**: Admin accounts MUST hold any subset of the six permissions of §3.3, each shown as an
  on/off switch with an Arabic label: `review` «مراجعة الطلبات (قبول/رفض)», `link` «تم الربط
  والتراجع عنه», `settings` «الإعدادات والأسعار والشرائح», `marketers` «إدارة المسوّقين وتصفير كلمات
  السر», `reports` «التقارير والتصدير والاستيراد», `commissions` «العمولات وزر تم الدفع».
- **FR-002**: The main admin MUST always hold every permission implicitly; their permissions cannot
  be viewed as switches, removed, or changed. Marketers hold no admin permissions.
- **FR-003**: Every admin-panel page and server action MUST be checked on the server against the
  caller's role and permissions at the time of each request; a refusal returns «ليست لديك صلاحية»
  and changes nothing. Permission changes MUST take effect on the next request without signing out.
- **FR-004**: The admin menu MUST show only the pages the caller may open, using this mapping:
  «الرئيسية» all admins; «طلبات بالانتظار» `review`; «بانتظار الربط» `link`; «المسوّقون»
  `marketers`; «الإعدادات» `settings`; «الأدمنية والصلاحيات» main admin only; «التقارير والتصدير»
  and «الاستيراد» `reports`; «المشتركون» any of `review`, `link`, or `reports`; «النسخ الاحتياطي»
  and «سجل العمليات» main admin only (system.md §10, v1.1). Pages whose
  features are not built yet stay placeholders but follow the same visibility rule.

**Admin management (main admin only)**

- **FR-005**: The main admin MUST be able to create an admin with name, phone, temporary password,
  and the chosen permission switches. The account is created active with "must change password" set.
- **FR-006**: The main admin MUST be able to list all admins (name, phone, permissions, state), and
  edit an admin's name, phone, and permissions.
- **FR-007**: The main admin MUST be able to deactivate and reactivate any admin, and reset an
  admin's password to a new temporary password. Only the main admin MAY reset an admin's password;
  the `marketers` permission does not extend to admin accounts.
- **FR-008**: Only the main admin MAY create, view, or change admin accounts. No one MAY deactivate
  the main admin, change its role, or reduce its permissions; at least one active main admin MUST
  always exist.

**Marketer management (`marketers` permission or main admin)**

- **FR-009**: Users with `marketers` (and the main admin) MUST be able to list marketers (name,
  phone, active state), create a marketer with name, phone and temporary password (created active,
  "must change password" set), and edit a marketer's name and phone.
- **FR-010**: They MUST be able to deactivate and reactivate a marketer.
- **FR-011**: They MUST be able to reset a marketer's password to a new temporary password; this
  sets "must change password" and ends all of the marketer's sessions (§3.4).
- **FR-012**: Users with `marketers` MUST NOT be able to see or change admin or main-admin accounts
  through the marketer pages.

**Common account rules**

- **FR-013**: Phone numbers MUST be normalized per §8.1 of `docs/system.md` before any check, and a
  phone already used by another account (any role, active or inactive) MUST be refused with «رقم
  الهاتف مستخدم لحساب آخر». Names MUST be 2–100 characters after trimming. Temporary passwords MUST be at least 8
  characters.
- **FR-014**: An account's role MUST NOT change after creation. Accounts MUST NOT be deleted: the
  only lifecycle actions are deactivate and reactivate (Principle III), and no delete action exists
  in any screen or server action.
- **FR-015**: Deactivating an account MUST end all of its sessions immediately: its next request on
  any device is refused and the user is signed out with «الحساب موقوف، راجع الإدارة». A deactivated
  account MUST NOT be able to sign in. Reactivation restores sign-in with the existing password.
- **FR-016**: Password reset MUST end all sessions of the target account and force a password change
  at next sign-in (feature 001 forced-change flow).
- **FR-017**: The person who sets a temporary password sees it only while typing it; the system MUST
  never display, send, or store it in readable form afterwards.

**«حسابي»**

- **FR-018**: Every signed-in user MUST have a «حسابي» page showing their name, phone, and role
  **read-only** (no self-edit; the phone is the sign-in identifier), with «تغيير كلمة السر» and
  «تسجيل الخروج». Single exception: the main admin MAY edit their own name (not phone) there. Changing the password MUST require the current password, plus the new password and
  its confirmation (rules of feature 001 FR-012). In the admin panel it is reachable from the top bar / menu; in the marketer
  app it is the «حسابي» tab.

**Audit**

- **FR-019**: The audit log MUST record, permanently and with actor, target, action, time (UTC,
  shown in Baghdad time) and before/after values: admin created, marketer created, account edited
  (name/phone), permissions changed, account deactivated, account reactivated, password reset by an
  admin, password changed by the user, and the main admin's own name change. Passwords, hashes, and
  tokens MUST never be recorded.
- **FR-019a**: The main admin (only) MUST have a read-only «سجل العمليات» page listing audit
  entries newest first, showing actor, time in Baghdad time, Arabic action label, target, and
  before/after values, filterable by date range (Baghdad days) and by actor. The page MUST be
  paginated so long histories stay usable on a phone. It covers all audit entries, including those
  from feature 001.
- **FR-020**: Refused actions (permission denied, validation failure, protected main admin) MUST NOT
  change any account data.

**Interface**

- **FR-021**: All screens of this feature MUST be in Arabic, right-to-left, and usable on a phone
  screen as well as a computer. Lists show the account state with a clear label («فعّال» /
  «موقوف»). Deactivation and password reset ask for confirmation before acting.

### Key Entities

- **User account** (from feature 001): name, normalized phone (unique), role, active state, "must
  change password" flag, admin permissions. This feature adds the ability to create and change these
  values; no new account attributes are expected.
- **Permission**: one of six fixed keys (`review`, `link`, `settings`, `marketers`, `reports`,
  `commissions`) with a fixed Arabic label; held only by admin accounts; the main admin holds all
  implicitly.
- **Session** (from feature 001): ended on deactivation and on admin password reset.
- **Audit entry** (from feature 001): new action types for account creation, edit, permission
  change, deactivation, reactivation, and password reset.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Acceptance path: the main admin creates an admin with only «إدارة المسوّقين», that
  admin signs in and creates a marketer, and that admin's menu does not contain «الإعدادات» — all
  completed in under 5 minutes.
- **SC-002**: 100% of admin-panel pages and actions are refused by the server for a caller lacking
  the mapped permission, when attempted directly by address.
- **SC-003**: After a deactivation or password reset, the affected user's next action on every
  signed-in device is refused in 100% of tests.
- **SC-004**: 0 ways exist to deactivate the main admin or remove its permissions (all attempts
  refused in tests).
- **SC-005**: Every successful account action in this feature produces exactly one audit entry, and
  0 audit entries contain password data.
- **SC-006**: An admin can add a new marketer in under 1 minute from a phone.
- **SC-007**: A permission change made by the main admin is reflected in the affected admin's menu
  and access on their next page load, with no sign-out needed.
- **SC-008**: The main admin can find a given account action in «سجل العمليات» by date and actor
  in under 30 seconds; 100% of non-main-admin attempts to read the log are refused.

## Assumptions

- The main admin edits admins' name and phone (owner-confirmed: only the main admin resets admin
  passwords).
- The main admin's phone comes from the bootstrap of feature 001 and no screen changes it; the main
  admin can change only their own name and password in «حسابي» (owner decision). There is no screen to create a second main admin.
- Role is fixed at creation: an admin cannot become a marketer or vice versa; a new account is
  created instead (phone must then be freed by editing the old account's phone).
- The marketers list in this feature shows name, phone and state only; the «عدد الشهر» and
  «العمولة» columns from §10 arrive with features 011 and 015.
- An admin with `marketers` can deactivate and reset marketers only, never other admins.
- Temporary passwords are typed by the admin (not generated by the system) and handed to the person
  outside the system; there is no SMS or WhatsApp delivery (§3.4).
- Deactivation takes effect on the target's next request to the server (the app checks the account
  on every request), which is what "sessions end immediately" means in practice.
- Tests and examples use synthetic names and phones only, never real people.
