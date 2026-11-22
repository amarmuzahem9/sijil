# Implementation Plan: Automatic National Card Reading (OCR)

**Branch**: `006-card-ocr` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-card-ocr/spec.md`, the owner's decisions
(spec › Clarifications), docs/system.md v1.7 §5.1/§14, and constitution 1.2.0.

## Summary

After both card images of a draft are uploaded, the server reads the card with the open-source
reader ID_Iraqi_Project. The reader runs in its own container `ocr`: no internet, internal
network only, 2 CPUs and 2 GB, models loaded once. The server then fills up to eight form fields
without touching what the marketer typed.

**Data**:
- **Original reading**: kept per field (`drafts.card_fields`) and per side (`card_readings.raw`
  and `result`).
- **National ID**: cross-checked against a verified MRZ, with every check digit including the
  composite.
- **Surname**: the new «لا يوجد لقب على البطاقة» choice satisfies the required surname.

**Behaviour**:
- **The `ocr` service**: a thin HTTP wrapper around the unchanged upstream code. It returns raw
  detections only.
- **The rules live in `api`**: side checks, merging duplicates, the second-document rule, O→0
  in the family number, and the cross-check. Tests use a fake reader.
- **Running a reading**: a background job in `api` (thread pool), polled by the page every 2 s
  while it runs.

**Web**:
- reading status and re-shoot messages in the image slots;
- «من البطاقة» / «عُدِّل يدوياً» marks;
- the national-ID confirmation;
- the no-surname checkbox;
- a «رخص البرمجيات المفتوحة» item in «حسابي».

**Owner change (back fields, system.md v1.8)**: the back also fills the date of birth, place of
birth, issue date, expiry date and issuing authority:
- **Locating and reading**: the rows are located by geometry in the reader's wrapper and read
  by the Arabic recogniser plus Tesseract.
- **Accepting a value**: only when cross-checked. The dates use the MRZ check digits, the rule
  expiry = issue + 10 years − 1 day, and the national ID's birth year. The authority is
  snapped to its known text.
- **Requirements and storage**: all five are required; an expired card blocks sending.
  Migration `0008_card_back_fields` adds them. See research R13.

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api, ocr); TypeScript + React 18 (web), unchanged

**Primary Dependencies**:
- **ocr (new, AGPL-3.0)**:
  - upstream `idcard_extractor` at commit `c12a24e`, with ultralytics 8.4.116, paddlepaddle
    3.3.1 / paddleocr 3.7.0 / paddlex 3.7.2, mrzmini 0.1.0, pytesseract, OpenCV 4.10;
  - CPU-only torch;
  - FastAPI, uvicorn and python-multipart for the wrapper;
  - the `tesseract-ocr` system package.
- **api**: `httpx` moves from the dev extras to the runtime dependencies (it was test-only); Pillow (005) is used for the
  fake reader's corner colour.
- **web**: none new.

**Storage**:
- PostgreSQL 16, migration `0007_card_reading`:
  - new table `card_readings`;
  - new columns `drafts.card_fields`, `no_surname` and `national_id_check`.
- Images stay in the 005 `uploads` volume. The reader stores nothing.

**Testing**:
- **pytest (api)**:
  - the rules on synthetic raw detections, including the 11 step-0 shapes rebuilt without real
    data;
  - applying a reading, the no-overwrite rule, the NID check, no-surname, job states, timeout and
    retry;
  - authorization and log safety.
- **pytest (ocr)**: `/health` and `/read` on a blank synthetic image.
- **Vitest**: marks, merge rules and polling.
- **Playwright** (desktop, Pixel 7, iPhone 14): with `OCR_MODE=fake`.

**Target Platform**: The company Linux server (4 CPUs, 6.7 GB free memory, 14 GB free disk);
phones (PWA).

**Project Type**: Web app: `api/`, `web/` and the new `ocr/` service.

**Performance Goals**:
- Fields filled within 15 s after the back finishes uploading for 9 of 10 clear cards
  (SC-001). Step 0 measured 2–6 s per side on 2 CPUs.
- Every reading ends (result or failure) within 60 s (FR-014).

**Constraints**:
- The reader has no internet access and is reachable only by `api` (FR-018).
- No card data in logs (FR-019).
- The reader keeps nothing. Its source is published (FR-022).
- `api` must work when `ocr` is down (US5).
- The reader's limits are `cpus: 2` and `mem_limit: 2g`. The reader image is ~4.3 GB.

**Scale/Scope**:
- A few readings per marketer per day; readings run one at a time.
- 3 new or changed API routes, 1 table, 3 columns.
- Web changes in 4 existing components plus 2 small new ones.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | The reading only pre-fills a draft; no decision is made. The national ID is cross-checked against the verified MRZ, and a mismatch must be confirmed (R7). The original reading is kept for the 008 decision and the 010 review. |
| II. Protection of Identity Documents | ✅ | Images go only to the internal reader, are never written by it, and are never exposed (R3, R11). Card text and numbers never appear in logs or errors (FR-019, check I5). Images stay in the private volume. |
| III. Permanent Audit Trail | ✅ | Reading is not a decision, so it is not audited. Draft deletion is still audited (005) and cascades to the readings. Nothing physically deleted beyond what 005 allows. |
| IV. Recorded Values Are Immutable | ✅ | The original reading is stored beside the final value and is never overwritten by edits (R8). Copying it to the request happens in 008. |
| V. Mobile-First and Arabic | ✅ | All new text is Arabic (contracts › UI strings). The page works on weak networks: the upload stays fast and polling uses a tiny body. On-device compression is unchanged. |
| VI. Simplicity | ✅ | No queue service: an in-process thread pool and DB states (R5). The rules are plain functions. Provenance is a JSONB column, not a table (R8). |
| VII. Fixed Technology Stack (1.2.0) | ✅ | `ocr` is the service added by the 1.2.0 amendment. Its code is in `ocr/`, separate from `api/`; the internal network has no internet. The source is published (R12). Reading sits behind `CardReader`, with `FakeCardReader` for development and tests (R10). |
| VIII. Tested Business Rules | ✅ | Every rule in R6–R9 has pytest cases, including the step-0 shapes rebuilt synthetically. Playwright covers the critical flows A–N with the fake reader. |
| IX. Server-Side Authorization | ✅ | The new routes reuse `get_owned`, so another marketer's draft returns 404. The reader is unreachable from outside, and the raw reading is not sent to the page. |
| X. Time Handling | ✅ | `started_at`/`finished_at` are stored in UTC; the 60 s limit is a duration. |

Gate result: **pass**, with no violation to justify.

**Post-design re-check (after Phase 1)**: still passes.
- **Data model**: it adds no deletion path, and the CASCADE follows 005's audited draft
  deletion.
- **Contracts**: they forbid client-sent provenance (`extra="forbid"`).
- **The `ocr` contract**: it has no route that stores data.

## Project Structure

### Documentation (this feature)

```text
specs/006-card-ocr/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R12
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── api.md           # app API changes, env vars, UI strings
│   └── ocr-service.md   # internal reader contract
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
ocr/                                   # NEW service (AGPL-3.0); published as the public copy (R12)
├── Dockerfile                         # CPU torch, pinned upstream requirements, weights + SHA256 at build
├── UPSTREAM.md                        # source URL, commit c12a24e, list of local changes (none planned)
├── LICENSE                            # AGPL-3.0 (from upstream)
├── upstream/                          # verbatim ID_Iraqi_Project at c12a24e
├── service/
│   ├── app.py                         # FastAPI: GET /health, POST /read; one reading at a time
│   ├── reader.py                      # per-side reading with upstream modules; composite check (R4)
│   └── evaluate.py                    # owner's offline check on private photos (prints only)
└── tests/test_service.py              # blank synthetic image → empty detections; health

api/app/
├── services/
│   ├── card_reader.py                 # CardReader, HttpCardReader, FakeCardReader (R10)
│   ├── card_reading_rules.py          # R6: candidates, merge, second document, outcome, family number
│   ├── card_reading_service.py        # queue job, run, store raw/result, apply to draft (R5, R8), retry, sweep
│   ├── draft_service.py               # + edited marks, no_surname, national_id_confirmed, NID check (R7–R9)
│   └── draft_validation.py            # + surname unless no_surname, national_id_unconfirmed
├── core/card_reading.py               # constants (data-model › Constants), MRZ check digit helper
├── models/draft.py                    # + CardReading model, new draft columns
├── schemas/drafts.py                  # + DraftOut keys, PATCH keys, CardReadingStatusOut
├── api/drafts.py                      # + GET …/card-reading, POST …/card-reading/retry; upload queues job
├── api/client_config.py               # + open_source
└── config.py                          # + OCR_MODE, OCR_URL, OCR_SOURCE_URL
api/migrations/versions/0007_card_reading.py
api/migrations/versions/0008_card_back_fields.py    # owner change: the five back fields (R13)
api/tests/
├── unit/test_card_reading_rules.py    # step-0 shapes (synthetic), thresholds, O→0, MRZ verification
├── integration/test_card_reading.py   # upload → job → fields; no overwrite; retry; timeout; 404 for others
├── integration/test_card_fields.py    # edited marks, no_surname, NID confirmation, missing items
└── integration/test_log_safety.py     # + readings never log card text

web/src/
├── lib/cardReading.ts                 # status polling (2 s), merge rules, labels
├── lib/draftFormController.ts         # + reading state, merge without overwriting pending keys
├── pages/marketer/subscriber/
│   ├── CardSection.tsx                # reading banner, failure + «أعد المحاولة»
│   ├── ImageSlot.tsx                  # re-shoot reason + tips per side
│   ├── CardDataSection.tsx            # marks, no-surname checkbox + hint
│   ├── FieldSourceMark.tsx            # NEW «من البطاقة» / «عُدِّل يدوياً»
│   └── NationalIdCheck.tsx            # NEW confirmation panel
└── pages/AccountPanel.tsx             # + «رخص البرمجيات المفتوحة»
web/src/__tests__/cardReading.test.ts

e2e/tests/card-reading.spec.ts         # scenarios A–N with synthetic images (fake reader)

docker-compose.yml                     # + ocr service, ocr_net (internal), api on both networks
docker-compose.e2e.yml                 # OCR_MODE=fake; ocr not started
docker-compose.staging.yml             # + container_name sijil-ocr
deploy/staging.md                      # + build/check the reader, publish ocr/, OCR_SOURCE_URL
.env.example                           # + OCR_MODE, OCR_URL, OCR_SOURCE_URL
README.md                              # + ocr/ row and licence note
```

**Structure Decision**: The existing web-app layout (`api/`, `web/`, `e2e/`) gains a third
top-level service folder `ocr/`, as decided by the owner and allowed by constitution 1.2.0.
`api` never imports from `ocr/`; they share only the HTTP contract.

## Implementation notes for tasks

- **Batches**: setup (ocr image, compose, migration) → foundation (CardReader + fake, rules,
  job) → US1/US2 (fill + provenance) → US3 (re-shoot) → US4 (NID) → US5/US6 (failure, retry,
  replace) → polish (account licences, docs, e2e, staging).
- **Second-document threshold**: R6.4 uses second-pass ≥ 0.90 as "high confidence". It is above
  step 0's phantom detection (0.876), so the phantom is ignored and the owner's rule is kept.
  To review with the owner at the tasks step if real use shows false re-shoots.
- **Before the first staging deployment**: remind the owner, then create the public copy of
  `ocr/` on the owner's GitHub account and set `OCR_SOURCE_URL` (owner's instruction).

## Complexity Tracking

No constitution violations. The new `ocr` service is the one allowed by constitution 1.2.0.
