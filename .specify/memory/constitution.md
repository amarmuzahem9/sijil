<!--
Sync Impact Report (2026-11-23, amendment 4)
- Version change: 1.2.0 → 1.2.1 (PATCH: clarification)
- Modified principles: III. Permanent Audit Trail — a change to an identity number is audited by
  reference: the audit entry points to an append-only record holding the value before and after,
  so identity numbers stay out of the audit text (Principle II) while before/after stays
  recoverable (docs/system.md §6.4 v1.14, feature 010).
- Added/removed sections: none
- Templates: not modified
- Follow-up TODOs: none
- Approved by the project owner in the feature 010 analysis review.
Previous report (2026-11-23, amendment 3)
- Version change: 1.1.1 → 1.2.0 (MINOR: Principle VII materially expanded)
- Modified principles: VII. Fixed Technology Stack — the runtime services now include `ocr`, the
  card reader (ID_Iraqi_Project, AGPL-3.0), kept separate from the app's server code, reachable
  only over the internal network, without internet access; its source is offered to users
  through a public copy (docs/system.md §14 v1.7, feature 006).
- Added/removed sections: none
- Templates: not modified
- Follow-up TODOs: none
- Approved by the project owner in the feature 006 specification review.

Previous report (2026-11-22, amendment 2)
- Version change: 1.1.0 → 1.1.1 (PATCH: clarification)
- Modified principles: III. Permanent Audit Trail — clarified that an unsubmitted draft is not a
  request; its owner may delete it, and the deletion is audited (docs/system.md §5 v1.4, feature 005).
- Added/removed sections: none
- Templates: not modified
- Follow-up TODOs: none
- Approved by the project owner in the feature 005 review.

Previous report (2026-11-22, amendment 1)
- Version change: 1.0.0 → 1.1.0 (MINOR: Principle III materially expanded)
- Modified principles: III. Permanent Audit Trail — user accounts are never physically deleted;
  «حذف» moves an account to a reversible archive (docs/system.md §3.6, feature 003); archive and
  restore are audited.
- Added/removed sections: none
- Templates: not modified
- Follow-up TODOs: none
- Approved by the project owner in the feature 003 request.

Previous report (ratification)
- Version change: (unversioned template) → 1.0.0
- Modified principles: none (initial ratification; all template placeholders replaced)
- Added principles (10, per project owner input):
  I. Anti-Fraud First (NON-NEGOTIABLE)
  II. Protection of Identity Documents (NON-NEGOTIABLE)
  III. Permanent Audit Trail
  IV. Recorded Values Are Immutable
  V. Mobile-First and Arabic
  VI. Simplicity
  VII. Fixed Technology Stack
  VIII. Tested Business Rules
  IX. Server-Side Authorization
  X. Time Handling
- Added sections: Additional Constraints & Security Requirements;
  Development Workflow & Quality Gates; Governance
- Removed sections: none
- Templates: not modified (dependent templates read this file at runtime)
- Follow-up TODOs: none
-->

# Sijil (سِجلّ) Constitution

Sijil is the subscriber-registration app used by Technology Internet (تكنولوجي للإنترنت) field
marketers to file FTTH subscription requests. The complete business rules live in
`docs/system.md`; this constitution governs how they are built.

## Core Principles

### I. Anti-Fraud First (NON-NEGOTIABLE)

- The decision to accept a request MUST be made on the server only, after checking the phone,
  national ID, and family number against all data: Sijil requests, imported legacy subscribers,
  and imported SAS subscribers, across all regions and towers.
- The UI MAY show early warnings while data is entered, but it MUST NOT decide; the server-side
  check at submission is authoritative.
- The decision table (system.md §6.1) MUST be applied in its documented order, and every
  applicable pending reason MUST be recorded on the request.
- Comparisons MUST use the canonical normalizations: phone per §8.1 (`^07\d{9}$`), national ID as
  digits only (Arabic/Indic digits converted), family number via its comparison key (uppercase,
  no spaces or symbols, `O` treated as `0`).
- Any change to phone, tower, category, or price after OTP verification MUST invalidate the
  verification. Request status MUST change only through the allowed transitions (§7.2).

**Rationale**: The primary purpose of Sijil is to stop the same house or person being registered
as new with different documents or a fake phone number.

### II. Protection of Identity Documents (NON-NEGOTIABLE)

- ID card images, national IDs, and family numbers are sensitive data.
- Card images MUST be stored in private storage outside the web root, served only through the
  API after a permission check, and every access MUST be logged.
- Sensitive data MUST NOT appear in the link message, application logs, or error messages.
- OTP codes MUST be stored as hashes only and never appear in any message, log, or export.
- Passwords MUST be hashed with argon2 or bcrypt, and login attempts MUST be rate-limited.
- The SAS `ct_password` column MUST never be read or stored.

**Rationale**: The system holds national identity documents; a leak harms real people and the
company.

### III. Permanent Audit Trail

- Every decision and sensitive change MUST be written to the audit log with who, when, what, and
  the value before and after. This covers: approve, reject, linked, undo linked, subscriber data
  edit, price change, export, and password reset.
- When the changed value is an identity number (national ID, family number), the audit entry
  MUST NOT carry the value itself. It MUST point to an append-only record that holds the value
  before and after (for example a pin row), readable only by users entitled to the data. The
  before/after values are then recoverable from the audit entry through that one link
  (docs/system.md §6.4, feature 010).
- Requests and subscribers MUST NOT be physically deleted; they may only be deactivated.
  An unsubmitted draft is not yet a request: its owner MAY delete it (with its images), and the
  deletion MUST be audited without card data (docs/system.md §5, feature 005).
- User accounts MUST NOT be physically deleted. «حذف» moves an account to the archive, which is
  reversible: the account cannot sign in, its sessions end, its phone stays reserved, and its
  requests and history keep showing its name. Archive and restore are audited. The main admin
  can never be archived (docs/system.md §3.6).

**Rationale**: Disputes over commissions and fraud can only be resolved from a complete,
tamper-evident history.

### IV. Recorded Values Are Immutable

- Prices, the original card OCR reading, the historical username, and decisions (who, when,
  reason) MUST be stored on the request at the moment they occur.
- Later changes to settings (prices, tiers, categories) MUST NOT alter values already recorded.
- Phone verification, request approval, and link completion are three separate facts, each
  stored with its own timestamp. A paid commission month is locked.

**Rationale**: Records must reflect what was true at the time, so reports and commissions stay
correct after settings change.

### V. Mobile-First and Arabic

- The UI MUST be fully Arabic with RTL layout, designed for phone screens first, and work on
  both iPhone and Android.
- The app MUST work on weak networks: compress images on the device before upload (longest edge
  about 1600px, JPEG quality about 0.8), autosave drafts to the server, and show clear Arabic
  error messages.
- Source code, comments, and identifiers MUST be in English. UI text is in Arabic.
- Request status colors MUST stay consistent with §7.2 everywhere.

**Rationale**: Field marketers work from phones, in Arabic, often on poor connections.

### VI. Simplicity

- Use the fewest fields and steps possible.
- No feature that is not in `docs/system.md` may be added without the project owner's approval.
- If a request conflicts with `docs/system.md`, work MUST stop and the question MUST be raised;
  guessing is prohibited. Rule changes go into `docs/system.md` first, then into code.

**Rationale**: A small team maintains this system, and every extra step slows marketers in the
field.

### VII. Fixed Technology Stack

- Frontend: React + TypeScript + Vite, PWA, structured to allow later Capacitor packaging, using
  a UI library with RTL support.
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic (migrations) + Pydantic.
- Database: PostgreSQL 16.
- Runtime: Docker Compose with services `web`, `api`, `db`, `proxy` and `ocr`. All
  configuration MUST come from environment variables (`.env`).
- Card reading (OCR) runs in the separate `ocr` service (ID_Iraqi_Project, AGPL-3.0). Its code
  lives in `ocr/` and MUST NOT be imported into or mixed with `api/` code; `api` reaches it only
  over the internal Docker network, and the service MUST have no internet access. Its source,
  with every change made to it, MUST be offered to the app's users through a public copy linked
  from the app; the rest of the app's code stays private.
- External services (WhatsApp OTP, OCR, maps) MUST sit behind a swappable adapter layer, each
  with a fake implementation for development and testing.

**Rationale**: A fixed stack keeps features consistent; adapters let providers change without
touching business logic.

### VIII. Tested Business Rules

- Every business rule MUST have pytest tests: the duplicate check and decision table, phone
  normalization, username format, commission tiers, permissions, and status transitions.
- Critical user flows MUST have Playwright end-to-end tests.
- A feature MUST NOT be merged while any of its tests fail.

**Rationale**: The rules are precise and will be probed at their edges; tests are the only
reliable proof they hold.

### IX. Server-Side Authorization

- Every endpoint MUST verify the caller's role and permission (`review`, `link`, `settings`,
  `marketers`, `reports`, `commissions`) on the server.
- A marketer MUST be able to access only their own requests and images. Existing-subscriber
  lookups expose only name, username, and tower.

**Rationale**: Hiding buttons in the UI is not access control.

### X. Time Handling

- All timestamps MUST be stored in UTC and displayed in Baghdad time (`Asia/Baghdad`).
- Monthly boundaries for the linked counter and commissions MUST be computed in Baghdad time.

**Rationale**: Commission months must match what marketers and admins see locally.

## Additional Constraints & Security Requirements

- All traffic MUST use HTTPS. Production runs at `https://sijil.t3cftth.net` on the company
  Linux server.
- Secrets (API keys, passwords) MUST NOT be committed to git. They live in `.env`, and a
  committed `.env.example` documents every required variable.
- Tests, fixtures, seeds, and examples MUST NOT use real ID card images or real subscriber data;
  only synthetic data is allowed.
- There is no programmatic SAS integration; SAS data enters only through import.
- Backups: nightly database and image backup kept 30 days, a weekly copy to the external drive,
  and a tested restore script.

## Development Workflow & Quality Gates

- Work uses Spec Kit, one feature at a time, each on its own branch, in the order of
  system.md §16.
- The relevant sections of `docs/system.md` MUST be read before planning or coding, and every
  spec MUST cite the sections it implements.
- Before a feature is complete:
  1. All pytest and Playwright tests pass.
  2. The application starts with `docker compose up`.
  3. Manual test steps are written in Arabic for the project owner.
- Communication with the project owner is in Arabic.
- Every plan MUST include a Constitution Check against Principles I–X.

## Governance

- This constitution supersedes other development practices. `docs/system.md` remains the
  authority for business rules.
- Amendments require a documented change to this file, approval by the project owner, an updated
  Sync Impact Report, and, where rules change, a matching update to `docs/system.md`.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR
  for adding a principle or materially expanding guidance, PATCH for clarifications and wording.
- Compliance is checked at plan time (Constitution Check) and at feature completion. Any
  violation MUST be resolved, or explicitly justified and approved, before merge.
- Runtime guidance for agents lives in `CLAUDE.md`.

**Version**: 1.2.1 | **Ratified**: 2026-11-21 | **Last Amended**: 2026-11-23
