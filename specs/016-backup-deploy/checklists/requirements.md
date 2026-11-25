# Specification Quality Checklist: Deployment and Backups

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-25
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The 3 questions were answered on 2026-11-25 (encrypted backups, passphrase kept off the server; external drive
  plugged in by hand with a weekly command; drive location in the server configuration). `docs/system.md` §15 updated
  (version 1.21). A follow-on change: the restore drill runs inside the weekly command because it needs the passphrase.
- Names of existing files (`.env`, `deploy/staging.md`) and of Nginx Proxy Manager appear only as references to the
  current deployment, not as design choices.
