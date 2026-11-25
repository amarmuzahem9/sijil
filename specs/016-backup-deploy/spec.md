# Feature Specification: Deployment and Backups

**Feature Branch**: `016-backup-deploy`

**Created**: 2026-11-25

**Status**: Clarified

**Input**: User description: "الفيزة 016: النشر والنسخ الاحتياطي. ارجع لـ docs/system.md (جدول الفيزات §16 والأقسام
المتعلقة) ولـ docs/features.md، ولسكربتات النشر الموجودة (scripts/deploy-staging.sh وملفات docker-compose). انتبه إن
النسخ تشمل قاعدة البيانات والمخزن الخاص للصور (ومنها صور القدامى من 014)، وإن الاسترجاع لازم يتجرّب فعلاً، وإن الأسرار
وملف .env ما تدخل النسخ بشكل مكشوف. بعد المواصفة لخّصلي بالعربي شنو ينحفظ ووين وكل شگد، وشنو يتغيّر بطريقة النشر، وشنو
الأسئلة اللي تحتاج قراري."

**System document references**: `docs/system.md` §7.4 (data erased by «حذف مشترك» stays in the backups until they
expire), §10 item 10 (page «النسخ الاحتياطي», main admin only: last backup, its status, a manual-backup button),
§13 (card images in private storage, every access audited, no card data in logs), §14 (Docker Compose on the company
Linux server, images in a private volume, the `ocr` service), §15 (domain; nightly database + images kept 30 days on
the server; weekly copy to the external drive, path set in the settings; a tested restore script; erased data kept
in backups 30 days nightly and without limit on the external drive), §16 (feature 016, phase ج, before the field
trial); constitution «Additional Constraints» (backups: nightly, 30 days, weekly external copy, tested restore;
secrets only in `.env`, never in git), Principles II (identity documents protected), III (audit; nothing physically
deleted by the system), IX (server-side authorization), X (UTC storage, Baghdad display). `docs/features.md` holds no
pending idea for this feature.

**Builds on**: 001 (deployment skeleton, main admin, audit log), 005 (private card-image storage, the `uploads`
volume), 006 (the `ocr` service, stateless), 011 (erasure of a deleted request), 014 (legacy card images fetched from
Drive, stored in the same private storage), 015 (SAS subscribers in the database). Existing deployment:
`scripts/deploy-staging.sh`, `docker-compose.yml` + `docker-compose.staging.yml` behind Nginx Proxy Manager,
`deploy/staging.md` (manual backup commands in «نسخ صور البطاقات احتياطياً», and step 9 «قبل الإطلاق الفعلي» which
defers the production script to this feature).

## Clarifications

### Session 2026-11-25

- Q: Encrypt backups, and where is the key kept? → A: All backups are encrypted. The encryption passphrase is never
  stored on the server nor inside any backup; the owner keeps it written down in a safe place. Losing it means the
  backups cannot be opened.
- Q: Is the external drive always connected? → A: No. The operator plugs it into the server and runs the weekly copy
  command; a warning shows while the copy is overdue.
- Q: Where is the external drive's location set? → A: In the server configuration (`.env`), not in the app; the backup
  page only shows it. `docs/system.md` §15 updated accordingly (version 1.21).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nightly automatic backup kept 30 days (Priority: P1)

Every night, without anyone signed in, the server takes one complete backup of Sijil: the whole database (requests,
drafts, accounts, settings, audit log, legacy and SAS subscribers, pins, notifications) and every file in the private
image storage (marketers' card photos and the legacy images fetched in 014), captured together so that they match each
other. Backups older than 30 days are removed automatically. The server's secrets file is never part of a backup.

**Why this priority**: Without it, one disk failure or one wrong command loses every request and every ID card
photo. Everything else in this feature depends on backups existing.

**Independent Test**: On a stack with synthetic data, let the nightly time pass (or trigger the nightly job), confirm a
new backup exists with a status «ناجحة», its size and its counts (requests, images); age synthetic backups past 30 days
and confirm only those are removed.

**Acceptance Scenarios**:

1. **Given** the app is running with synthetic requests, legacy subscribers with images and SAS subscribers, **When**
   the nightly time comes, **Then** one backup is created containing the database and all stored images, and it is
   recorded with its time (Baghdad), duration, size, number of image files and status.
2. **Given** a marketer uploads a card photo while the backup runs, **When** the backup finishes, **Then** the app kept
   working normally during the backup and the backup is internally consistent: every image the backed-up database
   refers to is in the backup.
3. **Given** nightly backups older than 30 days exist, **When** a new nightly backup succeeds, **Then** the ones older
   than 30 days are removed from the server, and the newest successful backup is never removed regardless of age.
4. **Given** the server was restarted during the day, **When** the nightly time comes, **Then** the backup still runs
   (the schedule survives restarts and deploys).
5. **Given** any backup, **When** its contents are listed, **Then** the secrets file (`.env`) and any password, key or
   token from it are not in it.

---

### User Story 2 - Restore that is actually tested (Priority: P1)

The person operating the server can restore Sijil from any kept backup with one documented command: database and
images return together to the moment of that backup. Separately, a restore drill, run with the weekly copy (when the operator is present with the passphrase), restores the latest
backup into a throwaway, isolated copy (no network, not reachable by users, the live system untouched), checks that it
starts and that its counts and images match what the backup recorded, records the result, and deletes the copy.

**Why this priority**: A backup that was never restored is a guess. The constitution requires «a tested restore
script», and the owner asked that the restore is really tried.

**Independent Test**: Take a backup of a synthetic stack, change data (add a request, erase one, delete an image file),
restore the backup, and confirm the stack matches the backup exactly; run the drill and confirm it reports success,
then corrupt a backup file and confirm the drill reports failure.

**Acceptance Scenarios**:

1. **Given** a backup from yesterday and changes made today, **When** the operator restores yesterday's backup, **Then**
   the database and the image storage are both exactly as they were at that backup (requests, statuses, audit log,
   legacy and SAS subscribers, and every image opens in the app), and today's changes are gone.
2. **Given** a restore is requested, **When** it starts, **Then** it first shows which backup it will restore (date,
   counts) and what will be lost, requires an explicit confirmation, and takes a fresh safety backup of the current
   state before replacing anything.
3. **Given** the app is running, **When** a restore runs, **Then** users cannot write during the restore (the app is
   stopped or shows it is unavailable), and afterwards the app starts and passes its health check.
4. **Given** the restore drill runs, **When** it finishes, **Then** its result (passed / failed, which backup, when,
   counts compared) is recorded and visible on the backup page; the throwaway copy and its data are deleted, and the
   live system was not affected at any point.
5. **Given** a backup file is damaged or incomplete, **When** the drill or a restore uses it, **Then** it fails with a
   clear reason and the live system is left unchanged.
6. **Given** a restore from a backup taken before a «حذف مشترك», **When** it completes, **Then** the erased personal
   data is back (as §7.4/§15 allow) and the operator was warned beforehand that erasures done after that backup are
   undone.

---

### User Story 3 - Main admin sees backup status and takes a manual backup (Priority: P2)

The main admin opens «النسخ الاحتياطي» in the admin panel: the last backup (time, status, size, counts), the list of
kept backups, the last weekly copy to the external drive, and the last restore drill result. A button «نسخة يدوية
الآن» starts a backup immediately. When something is wrong (last nightly failed, no successful backup in the last
36 hours, external copy overdue, last drill failed, server disk almost full), a warning appears on that page and on the
main admin's home page.

**Why this priority**: A failed backup that nobody notices is the same as no backup. The page is required by §10 item 10.

**Independent Test**: Sign in as the main admin with synthetic backups of each status; confirm the page shows them and
the warnings; press the manual button and see a new backup appear; sign in as an added admin with every permission and
confirm the page and its actions are refused.

**Acceptance Scenarios**:

1. **Given** the main admin, **When** they open «النسخ الاحتياطي», **Then** they see the last backup's time (Baghdad),
   status, size and counts, the kept backups, the last external copy and the last drill result, with no subscriber
   data shown.
2. **Given** the main admin presses «نسخة يدوية الآن», **When** no backup is running, **Then** a backup starts, the
   page shows it in progress and then its result; the action is written to the audit log.
3. **Given** a backup is already running, **When** the button is pressed, **Then** no second backup starts and the page
   says «يوجد نسخ جارٍ الآن».
4. **Given** the last nightly backup failed, **When** the main admin opens the home page, **Then** a warning «فشل آخر
   نسخ احتياطي» appears with a link to the backup page.
5. **Given** an added admin (any permissions) or a marketer, **When** they try to open the page or call its actions
   directly, **Then** the server refuses.
6. **Given** a manual backup, **When** retention runs, **Then** it follows the same 30-day rule as nightly backups.

---

### User Story 4 - Weekly copy to the external drive (Priority: P2)

Once a week the operator plugs the company's external drive into the server and runs the weekly copy command: the
latest successful backup is copied to the drive, which is then unplugged. Copies on the external drive are never
removed by Sijil (per §15). The copy is verified after writing. Its result appears on the backup page, and a warning
shows when the weekly copy is overdue.

**Why this priority**: The server's own disk is a single point of failure; the external drive is the only copy that
survives losing the server.

**Independent Test**: Point the external location at a test folder, trigger the weekly copy, confirm the copy exists,
verifies, and can be used by the restore drill; make the location unavailable and confirm the failure is reported
without affecting the nightly backups.

**Acceptance Scenarios**:

1. **Given** the operator has plugged in the external drive, **When** they run the weekly copy command, **Then** the
   latest successful backup is copied, verified against the original, and recorded (time, size, status), and the
   command says when the drive can be unplugged.
2. **Given** the drive is not connected, not at the configured location, or not writable, **When** the operator runs
   the command, **Then** it fails with a clear reason and the nightly backups are unaffected.
3. **Given** no successful weekly copy in the last 8 days, **When** the main admin opens the home or backup page,
   **Then** the warning «النسخة الأسبوعية متأخرة» shows until a copy succeeds.
4. **Given** older weekly copies on the drive, **When** a new copy is written, **Then** none of the older copies is
   removed or changed.
5. **Given** the external drive is almost full, **When** the copy would not fit, **Then** it fails before writing
   and names the cause.
6. **Given** a copy on the external drive, **When** the drive is read on another computer without the passphrase,
   **Then** no card image or personal data can be read.

---

### User Story 5 - One safe deploy path for staging and production (Priority: P2)

The operator updates Sijil on the server with one script that works for staging and for production. Before changing
anything it checks the server's configuration, then takes a backup, then updates and starts the app, checks health
inside and through the public address, and only in staging creates the synthetic demo accounts. If the update fails,
the operator has the pre-deploy backup and clear instructions to go back.

**Why this priority**: Step 9 of `deploy/staging.md` says the production script comes with backups. The field trial
(§16, right after this feature) uses real subscribers, so deploys must never risk the data.

**Independent Test**: Run the deploy on a test server/stack in staging and in production mode with synthetic data;
confirm a pre-deploy backup is created, demo accounts are created only in staging, a misconfigured `.env` stops the
deploy before anything changes, and a failed health check is reported with the rollback steps.

**Acceptance Scenarios**:

1. **Given** a correctly configured server, **When** the operator runs the deploy, **Then** it checks the
   configuration, takes a backup labelled «قبل النشر», updates, starts, and reports success only after both health
   checks pass.
2. **Given** production mode, **When** the deploy runs, **Then** no demo account is created and no development-only
   setting can be active (fake OTP, fake card reader, fake Drive, development mode).
3. **Given** the pre-deploy backup fails, **When** the deploy runs, **Then** it stops before changing the running app.
4. **Given** the new version fails its health check, **When** the deploy ends, **Then** it exits with a failure, names
   the pre-deploy backup, and prints the steps to return to the previous version and data.
5. **Given** the deploy runs, **When** it finishes, **Then** the backup schedule is still active and no host port is
   published (same rule as today: 80/443 belong to Nginx Proxy Manager, the database is never exposed).
6. **Given** a deploy, **When** it finishes, **Then** a line «نشر» (version, mode, who/where if known, result) is kept
   in the backup/deploy history shown on the backup page.

---

### Edge Cases

- **Backup during heavy writes**: a submission, image upload, OCR read or import confirmation during a backup must not
  fail or slow beyond normal; the backup reflects one consistent moment.
- **Image files without a database row (orphans) or rows without a file**: the backup takes the storage as it is; the
  drill reports the count of referenced images missing from the backup (must be 0 for a pass).
- **Erased request (§7.4)**: its images were removed from storage; older backups still hold them until they expire
  (30 days on the server, never on the external drive) — this is documented, not hidden.
- **Restore then orphan clean-up**: restoring must restore database and images from the same backup; the existing
  orphan clean-up must not remove restored images that the restored database references.
- **Server disk almost full**: a backup that would leave less than a safe margin of free space does not start; it fails
  with «المساحة غير كافية» and the warning shows. A failed or partial backup never replaces or deletes a good one.
- **Two backups at once** (nightly + manual, or deploy + nightly): only one runs; the other waits or is refused with a
  clear message.
- **Clock / time zone**: backup names and display use Baghdad time; stored times are UTC; the nightly run happens once
  per Baghdad day.
- **Restoring to a new server** (old server lost): possible with only the external-drive copy, a fresh `.env` written
  by hand from `.env.example`, and the backup key (FR-010). Passwords of user accounts are in the database and come
  back; signing sessions may end and users sign in again.
- **Restore across versions**: restoring a backup taken by an older app version onto a newer version must bring the
  database to the current structure, or refuse with a clear reason; never start with a mismatched structure.
- **The `ocr` service**: holds no data and is not backed up; restoring does not depend on it.
- **Demo accounts in a staging backup restored into production**: they come back as they were; the production deploy
  does not reactivate them.
- **Failed nightly backup on the 30th day**: retention never removes the newest successful backup, even if older than
  30 days.

## Requirements *(mandatory)*

### Functional Requirements

**What is backed up**

- **FR-001**: Each backup MUST contain the complete database and every file in the private image storage (marketers'
  card images and legacy images from 014), taken so that both reflect the same moment.
- **FR-002**: Backups MUST NOT contain the secrets file (`.env`) or any value from it (database password, signing key,
  OTP provider key, Maps key, admin bootstrap password). The OCR service, the app code and build caches are not
  backed up.
- **FR-003**: Each backup MUST record: kind (nightly / manual / pre-deploy / pre-restore), start and end time, status
  (running / succeeded / failed with reason), total size, number of image files, and summary counts (requests, legacy
  subscribers, SAS subscribers, accounts), and a fingerprint that lets a later check detect damage. The record MUST NOT
  contain any personal data.
- **FR-004**: Image files are written once and never changed; a backup MUST NOT need to store an unchanged image again
  for each night, so that 30 nightly backups do not cost 30 times the image storage, while each nightly backup stays
  restorable on its own to its own moment.

**Schedule and retention**

- **FR-005**: A nightly backup MUST run automatically once per Baghdad day at a quiet hour (default 03:00 Baghdad),
  independent of any signed-in user, and keep running after server restarts and deploys.
- **FR-006**: Backups on the server older than 30 days MUST be removed automatically after a newer backup succeeds; the
  newest successful backup MUST never be removed. A failed or partial backup MUST never cause a good one to be removed.
- **FR-007**: The weekly copy MUST be a command the operator runs after plugging the external drive into the server. It
  MUST check that the drive is present at the configured location and has room, copy the latest successful backup,
  verify it after writing, and record the result. Copies on the external drive MUST never be removed or changed by
  Sijil.
- **FR-008**: Only one backup or restore operation may run at a time.
- **FR-009**: A backup MUST NOT start when it would leave the server's disk below a safe free-space margin; it fails
  with a clear reason.

**Protection of the backups**

- **FR-010**: Every backup (on the server and on the external drive) MUST be encrypted with a passphrase that is never
  stored on the server, in `.env`, in git or inside any backup; the operator supplies it when a backup is taken and
  when one is restored or drilled, and the owner keeps it written down in a safe place. Without it no card image or
  personal data can be read from a backup. The documentation MUST state that losing the passphrase makes the backups
  unusable. Backup files on the server MUST also be readable only by the server's administrator account, never by the
  app's web container.
- **FR-010a**: Because the passphrase is not on the server, the unattended nightly backup MUST be able to encrypt
  without being able to decrypt (only the holder of the passphrase can open a backup). Taking a backup MUST never
  require the passphrase to be stored on the server.
- **FR-011**: Backup records, the backup page, deploy output and logs MUST NOT show any subscriber data, card data, OTP
  code, password or key.

**Restore**

- **FR-012**: A restore command MUST restore the database and the image storage together from one chosen backup (from
  the server or from the external drive). Before replacing anything it MUST show the backup's time and counts, warn
  that everything after it (including erasures by «حذف مشترك») is lost, require explicit confirmation, and take a
  pre-restore backup of the current state.
- **FR-013**: During a restore, users MUST NOT be able to write; after it, the app MUST start and pass its health
  check, and the restore MUST be recorded (which backup, when, result) in the backup history and, once the app is up,
  in the audit log.
- **FR-014**: A restore MUST verify the backup's fingerprint first and refuse a damaged backup, leaving the live system
  unchanged.
- **FR-015**: A restore drill MUST restore a backup into an isolated throwaway copy with no network access and not
  reachable by users, start it, compare its counts and image files with what the backup recorded (referenced images
  missing must be 0), record passed/failed, and delete the copy and its data. Because it needs the passphrase
  (FR-010), it runs as part of the weekly copy command, on the copy just written to the external drive, and on demand
  by the operator. It MUST NOT modify the live system or send any message (no OTP, no notification).
- **FR-015a**: Without the passphrase, every nightly backup MUST still be checked automatically after it is written
  (complete, fingerprint matches), and a failed check marks the backup failed.

**Backup page (main admin)**

- **FR-016**: The page «النسخ الاحتياطي» (main admin only, enforced on the server) MUST show the last backup, the kept
  backups (time, kind, status, size, counts), the last external copy, the last drill result, the last deploys, the
  server's free disk space, and a button «نسخة يدوية الآن». Starting a manual backup MUST be audited. Restore is NOT
  started from the page; it is a server operation (FR-012).
- **FR-017**: A warning MUST show on the backup page and on the main admin's home page when: the last backup failed; no
  successful backup in the last 36 hours; no successful external copy in the last 8 days; the last drill failed or none
  in the last 8 days; or the server's free space is below the margin.
- **FR-018**: The external drive's location MUST be set only in the server configuration (`.env`) by the operator; the
  app MUST NOT let anyone enter or change a path. The backup page shows the configured location read-only.

**Deployment**

- **FR-019**: One deploy script MUST serve staging and production, chosen by the mode in the server's `.env`. It MUST
  keep all of today's pre-flight checks (secrets not left at «change-me», database password consistent, network of
  Nginx Proxy Manager present, no published host port) and add: in production, refuse any development or fake mode
  (fake OTP, fake card reader, fake Drive) and any demo-account seeding.
- **FR-020**: The deploy MUST take a «قبل النشر» backup and stop if it fails, before changing the running app; then
  update, start, check health inside the stack and through the public address, and on failure print the pre-deploy
  backup and the steps to go back to the previous version and data.
- **FR-021**: The deploy MUST leave the backup schedule active and record each deploy (version, mode, result, time) in
  the history shown on the backup page.
- **FR-022**: Demo accounts MUST be created only in staging. The switch from staging to production (deactivating the
  demo accounts, changing the mode) MUST be a documented step, run once by the operator, and audited.
- **FR-023**: The operator documentation (Arabic) MUST cover: first install, update, switch to production, backup
  locations, manual backup, restore from the server and from the external drive, restore on a new server, the drill,
  where the key and the `.env` values must be kept outside the server, and what to do for each warning.

### Key Entities

- **Backup**: one restorable snapshot of database + images at one moment. Kind, times, status, failure reason, size,
  image count, summary counts, fingerprint, location (server / external). No personal data.
- **External copy**: a weekly copy of one backup on the external drive; time, size, verification result. Never removed
  by Sijil.
- **Restore drill result**: which backup, when, passed/failed, counts compared, reason on failure.
- **Restore record**: which backup was restored, when, by which operation, result; also written to the audit log.
- **Deploy record**: version, mode (staging / production), time, result, the «قبل النشر» backup it took.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 7 consecutive days on staging, a nightly backup succeeds every night with no action from anyone.
- **SC-002**: A restore of any kept backup returns 100% of the requests, legacy and SAS subscribers and audit entries,
  and 100% of the referenced images open in the app; verified by the drill on every run.
- **SC-003**: A full restore on the staging server (data at field-trial size) completes in under 30 minutes from the
  operator's command to a healthy app.
- **SC-004**: Users notice no failure during a nightly backup: submissions and photo uploads keep succeeding while it
  runs.
- **SC-005**: A failed backup, overdue external copy or failed drill is visible to the main admin on the home page within
  one hour of being detected.
- **SC-006**: 30 nightly backups with field-trial data fit on the server's disk with the safe margin left; image storage
  is not multiplied by the number of nightly backups.
- **SC-007**: A scan of every backup and of the backup page finds no secret from `.env`; a copy of a backup without the
  key reveals no card image or personal data.
- **SC-008**: Every deploy creates a pre-deploy backup; a deploy with a misconfigured `.env` changes nothing.

## Assumptions

- The operator is the person with shell access to the server (today the owner); the main admin in the app is not
  necessarily the same person. Restore is a server operation only, never a button in the app.
- Data size at the field trial: roughly a few hundred to a few thousand requests (2 photos each, compressed on the
  phone to ≤ 1600 px, about 0.3–0.5 MB per photo), 109 legacy subscribers with up to 2 images each, about 20 000 SAS
  rows; the database itself is in the tens of MB. The staging server has about 14 GB free (shared with the 4.3 GB
  card-reader image).
- Nightly default time 03:00 Baghdad, adjustable by the operator. The weekly copy and drill happen when the operator runs the weekly command (suggested: every Friday).
- No off-site / cloud copy in this feature: §15 names only the server and the external drive, and backups hold real ID
  cards; sending them to an outside service is out of scope.
- The `.env` file is not backed up; the operator keeps its values (or how to regenerate them) outside the server.
  OTPIQ and Google Maps keys can be re-issued from their dashboards; the database password and signing key can be new
  on a new server.
- Nginx Proxy Manager, its certificates and its configuration are outside Sijil and are not backed up by this feature;
  the documentation lists the Proxy Host settings to recreate them.
- Notifications to the main admin are inside the app (page + home warning); no SMS, WhatsApp or e-mail alert in this
  feature.
- The restore drill handles real card images only inside an isolated copy with no network, and keeps no results beyond
  the pass/fail counts (project rule for real images).
- Existing manual backup commands in `deploy/staging.md` are replaced by the new commands.
