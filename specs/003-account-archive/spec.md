# Feature Specification: Account Archive

**Feature Branch**: `003-account-archive`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "فيزة صغيرة: أرشيف الحسابات. أريد زر «حذف» للحسابات ينقل الحساب إلى الأرشيف، لا
حذف فعلي: الزر يظهر للأدمن الرئيسي فقط، مع رسالة تأكيد. الحساب المؤرشف يختفي من قوائم الأدمنية والمسوّقين، ولا
يستطيع الدخول، وتنتهي جلساته. صفحة جديدة «أرشيف الحسابات» للأدمن الرئيسي فقط: فيها الحسابات المؤرشفة مع تاريخ
الأرشفة ومن أرشفها، وزر «استرجاع». الاسترجاع يعيد الحساب موقوفًا، والأدمن يفعّله بنفسه بعدها. طلباته وسجله تبقى
محفوظة باسمه دائمًا. رقم هاتفه يبقى محجوزًا ما دام في الأرشيف. الأدمن الرئيسي نفسه لا يُؤرشف. الأرشفة والاسترجاع
يُسجَّلان في سجل العمليات. حدّث docs/system.md والدستور بهذه القاعدة أولًا، ثم المواصفة والمهام، ثم نفّذ واختبر."

**System document references**: `docs/system.md` v1.2 §3.6 (account archive), §10 page 12
«أرشيف الحسابات»; constitution 1.1.0 Principle III.

**Builds on**: feature 002 (account management, audit log and its viewer, page permission map).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Main admin archives an account (Priority: P1)

The main admin presses «حذف» on an admin or a marketer, reads a confirmation that the account will
move to the archive and can be restored, and confirms. The account disappears from its list, its
open sessions end at once, and it can no longer sign in.

**Why this priority**: This is the core of the feature: removing a departed staff member from the
day-to-day lists without losing any history.

**Independent Test**: Archive a signed-in synthetic marketer and check that it leaves the marketers
list, its next action ends the session, and sign-in is refused.

**Acceptance Scenarios**:

1. **Given** the main admin on «المسوّقون» or «الأدمنية والصلاحيات», **Then** each account row has
   a «حذف» button; **Given** an admin holding `marketers`, **Then** no «حذف» button appears on any
   row and the server refuses the action.
2. **Given** the main admin presses «حذف», **Then** a confirmation names the account and says it
   moves to «أرشيف الحسابات», will be signed out, and can be restored. Cancelling changes nothing.
3. **Given** the confirmation is accepted, **Then** the account disappears from its list, its
   sessions on every device end, and its next action shows «الحساب موقوف، راجع الإدارة».
4. **Given** an archived account, **When** it tries to sign in with its correct password, **Then**
   it is refused with «الحساب موقوف، راجع الإدارة».
5. **Given** an active or a deactivated account, **Then** either can be archived.
6. **Given** the main admin's own account, **Then** it has no «حذف» button and the server refuses
   any attempt to archive it.

---

### User Story 2 - «أرشيف الحسابات» page and restore (Priority: P1)

The main admin opens «أرشيف الحسابات» and sees every archived account with its name, phone, role,
the archive date (Baghdad time) and who archived it. Pressing «استرجاع» brings the account back to
its list as **deactivated**; the main admin then reactivates it separately when appropriate.

**Why this priority**: Without restore, archiving becomes a one-way delete, which the owner ruled
out.

**Independent Test**: Archive a synthetic account, open the archive page, restore it, and check it
returns to its list as «موقوف» and can sign in only after «إعادة تفعيل».

**Acceptance Scenarios**:

1. **Given** archived accounts, **When** the main admin opens «أرشيف الحسابات», **Then** each one
   shows name, phone, role, archive time in Baghdad time and the archiving person's name, most
   recently archived first.
2. **Given** no archived accounts, **Then** the page shows «لا توجد حسابات مؤرشفة».
3. **Given** an archived account, **When** «استرجاع» is pressed, **Then** it leaves the archive,
   reappears in its list with state «موقوف», and still cannot sign in.
4. **Given** a restored account, **When** the main admin presses «إعادة تفعيل», **Then** it signs in
   with its existing password.
5. **Given** any account other than the main admin, **Then** «أرشيف الحسابات» is not in the menu,
   opening it by address returns to the home page with «ليست لديك صلاحية», and the server refuses
   the archive list and restore.

---

### User Story 3 - History and phone stay with the archived account (Priority: P2)

Everything the account did stays recorded under its name, and its phone number cannot be given to
another account while it is archived.

**Why this priority**: Protects commission and fraud disputes (Principle III) and prevents a
reused phone from being confused with the archived person.

**Independent Test**: Archive a synthetic account that has audit entries, check the audit log
still shows its name as actor and target, and check that creating another account with its phone
is refused.

**Acceptance Scenarios**:

1. **Given** an archived account, **When** the main admin opens «سجل العمليات», **Then** its past
   entries still show its name (as actor and as target), and it is still selectable in the
   «المنفّذ» filter.
2. **Given** an archived account's phone, **When** anyone creates or edits another account to use
   that phone, **Then** it is refused with «رقم الهاتف مستخدم لحساب آخر».
3. **Given** archive and restore actions, **Then** each writes exactly one audit entry with who,
   when, the target, and before/after values.

### Edge Cases

- Archiving an account that is already archived, or restoring one that is not archived, changes
  nothing and writes no audit entry.
- An archived account cannot be edited, deactivated, reactivated, or password-reset from the admins
  or marketers pages; it must be restored first.
- An admin holding `marketers` cannot see archived marketers anywhere and cannot restore them.
- Restoring keeps the account's other attributes (name, phone, permissions, "must change password")
  exactly as they were when archived.
- An archived admin's permissions are kept; they take effect again only after restore and
  reactivation.
- Requests (from later features) made by an archived marketer keep showing the marketer's name.
- Accounts are never physically deleted; there is no way to empty the archive.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main admin MUST be able to archive any admin or marketer account, active or
  deactivated, after a confirmation. Nobody else MAY archive, and the «حذف» button MUST appear for
  the main admin only.
- **FR-002**: The main admin account MUST NOT be archivable by any means.
- **FR-003**: Archiving MUST, in one step: mark the account archived with the time and the person
  who archived it, make it unable to sign in, and end all of its sessions immediately.
- **FR-004**: Archived accounts MUST NOT appear in the admins or marketers lists and MUST NOT be
  editable, deactivatable, reactivatable, or resettable until restored.
- **FR-005**: A sign-in attempt or any request by an archived account MUST be refused with
  «الحساب موقوف، راجع الإدارة».
- **FR-006**: The main admin (only) MUST have a «أرشيف الحسابات» page listing archived accounts with
  name, phone, role, archive time (Baghdad time) and the archiving person's name, newest archive
  first, each with «استرجاع».
- **FR-007**: Restoring MUST clear the archive mark and return the account to its list as
  deactivated; every other attribute stays unchanged. Reactivation is a separate action.
- **FR-008**: An archived account's phone MUST stay reserved: no other account may be created with
  or changed to it.
- **FR-009**: Records about an archived account (audit entries now; requests and other records in
  later features) MUST be kept and MUST keep showing its name.
- **FR-010**: Archive and restore MUST each write one audit entry (actor, target, time,
  before/after); no-op attempts write none. The audit viewer MUST show them with Arabic labels
  «أرشفة حساب» and «استرجاع حساب من الأرشيف».
- **FR-011**: The «أرشيف الحسابات» page MUST follow the page-permission rules of feature 002:
  absent from the menu and refused by the server for anyone but the main admin.
- **FR-012**: All screens MUST be Arabic, right-to-left, and usable on a phone.

### Key Entities

- **User account** (from features 001/002): gains an archive mark: when it was archived and by
  whom (empty when not archived). An archived account is also deactivated.
- **Session** (from feature 001): ended with reason "archived" when its account is archived.
- **Audit entry** (from feature 001): new actions "account archived" and "account restored".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The main admin can archive an account in under 15 seconds (button, confirmation).
- **SC-002**: After archiving, the account's next action on every signed-in device is refused in
  100% of tests, and 100% of sign-in attempts are refused.
- **SC-003**: 0 archived accounts appear in the admins or marketers lists.
- **SC-004**: 100% of attempts by non-main-admin users to archive, list the archive, or restore are
  refused by the server.
- **SC-005**: 0 ways exist to archive the main admin.
- **SC-006**: A restored account is deactivated in 100% of cases and signs in only after
  reactivation.
- **SC-007**: 100% of attempts to reuse an archived account's phone are refused.

## Assumptions

- The button is labelled «حذف» as the owner asked; its confirmation text makes clear it moves the
  account to the archive and can be restored.
- Archived accounts get the existing «الحساب موقوف، راجع الإدارة» message; the system does not tell
  the person that the account was archived.
- Restoring needs no confirmation (it does not grant access by itself).
- The archive page lists all archived accounts on one page (the expected count is small); no search.
- Requests do not exist yet; FR-009 is a binding rule for features that add them (system.md §3.6).
- Tests use synthetic names and phones only.
