---

description: "Task list for feature 006: Automatic National Card Reading (OCR)"
---

# Tasks: Automatic National Card Reading (OCR)

**Input**: Design documents from `specs/006-card-ocr/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/ocr-service.md](./contracts/ocr-service.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII. Every rule in research R6–R9 gets pytest
cases. The critical flows get Playwright scenarios (quickstart A–N) with the fake reader. Write
each test task first and confirm it fails.

**Organization**: Tasks are grouped by user story (spec US1–US6) so each story can be built and
tested on its own. The FR-017 no-surname choice is part of US1 (its scenario 3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md
- **Paths**: `ocr/` (reader service), `api/` (FastAPI), `web/src/` (React), `e2e/tests/`
  (Playwright)
- **Test data**: synthetic images only (a corner colour selects the fake scenario, research R10).
  Never a real card or real names and numbers (CLAUDE.md). `test-cards/` stays out of git.

**Implementation batches** (each ends at a phase boundary):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T017 |
| 2 | 3–5 (US1, US2, US3) | T018–T034 |
| 2b | 5b (US7, owner change: back fields) | T056–T067 |
| 3 | 6–9 (US4, US5, US6, Polish) | T035–T055 |

---

## Phase 1: Setup (the reader service and wiring)

- [X] T001 Copy ID_Iraqi_Project at commit `c12a24e` verbatim into `ocr/upstream/`:
  - what to copy: `src/`, `models/SHA256SUMS`, `scripts/download_weights.py`,
    `requirements.txt`, `pyproject.toml`, `LICENSE`, `README.md` and `README.ar.md`;
  - what to leave out: `.github/`, `tests/`, `docs/images/` and `run_gui.bat`;
  - also: copy `LICENSE` to `ocr/LICENSE`, and write `ocr/UPSTREAM.md` with the source URL, the
    commit, the weights release URL (`Hai800Z/ID_Iraqi_Project` v1.0.0, noting the stale
    README link), and «Local changes: none» (research R1).
- [X] T002 Write `ocr/Dockerfile` (research R2, contracts/ocr-service.md › Build and runtime
  guarantees):
  - base: `python:3.12-slim`, with `tesseract-ocr libgl1 libglib2.0-0 libgomp1`;
  - packages: CPU torch/torchvision from the PyTorch CPU index, then
    `ocr/upstream/requirements.txt`, `pip install -e ocr/upstream`, and pinned `fastapi`,
    `uvicorn` and `python-multipart`;
  - weights: `download_weights.py --base-url …/ID_Iraqi_Project/releases/download/v1.0.0`; the
    build fails on a checksum mismatch;
  - OCR model: pre-fetch the PaddleOCR `arabic_PP-OCRv5_mobile_rec` into `/models/paddlex`;
  - environment: `YOLO_OFFLINE=1`, `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`,
    `PADDLE_PDX_CACHE_HOME=/models/paddlex` and `OMP_NUM_THREADS=2`;
  - user and port: a non-root user, port 8080, and `CMD uvicorn service.app:app`;
  - also add `ocr/.dockerignore`.
- [X] T003 [P] Write `ocr/service/reader.py`: `load()` loads the 3 YOLO models and the text
  recognizer once. `read(image_bytes, side)` returns the detections of
  contracts/ocr-service.md › `POST /read`:
  - **Upstream modules it uses**: `detect_cards`, `second_pass_confidence`, `orient_front` /
    `orient_back`, `detect_fields`, `crop_detections`, `split_mrz_crop`, `recognize_fields` and
    `read_mrz`.
  - **Second pass**: fields are read only for detections with second pass ≥ 0.50.
  - **The box**: comes from the detection.
  - **`valid_composite`**: from `mrzmini`, else computed from `raw_mrz` (research R4), else null.
  - **Upstream's own logic**: `combine_sides` and validation are never called.
  - **Logging**: set the upstream loggers to WARNING and log no field text.
- [X] T004 Write `ocr/service/app.py` (FastAPI) to the contract in contracts/ocr-service.md:
  - **`GET /health`**: 503 until the models are loaded, then 200 with `upstream: c12a24e`.
  - **`POST /read`**: multipart `image` up to 6 MB, plus `side`, guarded by one `asyncio.Lock`
    so one reading runs at a time; the reading runs in a thread.
  - **Errors**: 400 `bad_image`, 413, 503 `loading`, 500 `reader_error`. No error body or log
    line contains card content.
  - **Startup**: models load on startup in a background thread.
- [X] T005 [P] Write `ocr/tests/test_service.py` (runs inside the `ocr` image):
  - `/health` reaches 200;
  - `/read` on a blank synthetic 800×500 JPEG returns `{"detections": []}` with
    `duration_ms`;
  - an undecodable body gets 400.
- [X] T006 In `docker-compose.yml`, add the `ocr` service (research R3):
  - **Service**: build `./ocr`, `restart: unless-stopped`, `cpus: 2`, `mem_limit: 2g`, `tmpfs:
    /tmp`, no ports, and a healthcheck on `/health`.
  - **Network**: a new network `ocr_net` with `internal: true`. `ocr` is only on `ocr_net`.
    `api` is on `default` and `ocr_net`, with no `depends_on` on `ocr`.
  - **Staging overlay** (`docker-compose.staging.yml`): `container_name: sijil-ocr` and
    `ports: !reset []`.
  - **e2e overlay** (`docker-compose.e2e.yml`): `OCR_MODE: fake` on `api`, and `ocr` disabled
    with `profiles: ["ocr-real"]`.
- [X] T007 [P] In `api/app/config.py`, add `ocr_mode` (`http|fake`, default `http`; tests use
  `fake`), `ocr_url` (default `http://ocr:8080`) and `ocr_source_url` (default empty). Document
  them in `.env.example`, from contracts/api.md › Environment variables.

---

## Phase 2: Foundational (blocking prerequisites)

- [X] T008 Write migration `api/migrations/versions/0007_card_reading.py` (down_revision `0006`):
  - **New `drafts` columns**: `drafts.card_fields` (jsonb, NOT NULL, default `{}`),
    `drafts.no_surname` (boolean, NOT NULL, default false, CHECK
    `NOT no_surname OR surname IS NULL`), and `drafts.national_id_check` (jsonb, nullable).
  - **The `card_readings` table**, with the columns, UNIQUE (`draft_id`, `side`) and CHECKs of
    data-model.md › `card_readings`: `card_readings.state`, `card_readings.reason`,
    `card_readings.image_file_name`, `card_readings.raw`, `card_readings.result`,
    `card_readings.queued_by_client`, `card_readings.started_at`, `card_readings.finished_at`,
    `card_readings.duration_ms` and timestamps.
  - **Delete rule**: FK to `drafts` ON DELETE CASCADE.
  - **Access log**: `image_access_log.purpose` (text, NOT NULL, default `'view'`, CHECK
    `view|ocr`), per data-model.md › Change to `image_access_log` (analysis C1).
  - **Downgrade**: drops all of it.
- [X] T009 In `api/app/models/draft.py`, add the new `Draft` columns and the `CardReading` model,
  mirroring T008 (data-model.md › Changes to `drafts`, `card_readings`):
  - the relationship `Draft.card_readings` (cascade, `selectin`);
  - the constant `CARD_FIELDS` (the 8 keys of data-model.md › `drafts.card_fields`);
  - in `api/app/models/__init__.py`, export `CardReading`.
- [X] T010 [P] Add `api/app/core/card_reading.py`:
  - the constants of data-model.md › Constants;
  - `mrz_check_digit()` and `mrz_verified(mrz)`, which needs TD1 and all four checks true
    (research R7);
  - `mrz_national_id(mrz)`, which returns 12 digits or None;
  - `normalize_family_number(text)`, the O→0 rule and the pattern of data-model.md ›
    `drafts.family_number` row of the apply table (research R6.6).
- [X] T011 [P] Write unit tests `api/tests/unit/test_card_reading_rules.py` first (they must
  fail). Use synthetic raw detections rebuilt from the step-0 shapes, with no real text:
  - one clear front; one clear back;
  - a phantom front (second pass 0.876, no fields) beside a back → ignored;
  - a second front at 0.92 with no fields → `multiple`;
  - a second detection with 2 readable fields → `multiple`;
  - the same back twice (same MRZ number; and IoU 0.7) → one card;
  - nothing → `no_card`; only the other side → `wrong_side`;
  - a `drive` at 0.6 alone → `not_unified`;
  - the family number: `1066LOM12345678901` → `1066L0M12345678901`, an unread number and a bad
    shape → empty;
  - `mrz_verified`: any false check, or a composite of null, → False.
- [X] T012 Implement `api/app/services/card_reading_rules.py` (research R6) so T011 passes:
  - `evaluate_side(raw, side) -> SideOutcome(state, reason, result)`, where `result` follows
    data-model.md › `card_readings.result`;
  - the front's `surname_empty` is true when the `last` field was detected with empty text, or
    when the front was read without a `last` field.
- [X] T013 [P] Implement `api/app/services/card_reader.py` (research R10):
  - a `CardReader` protocol;
  - `HttpCardReader`, which calls `POST {ocr_url}/read` with httpx, a 45 s timeout, and no
    logging of the body;
  - `FakeCardReader`, which picks one of the R10 scenarios from the average colour of the
    image's top-left 32×32 block (Pillow, nearest palette colour), returns synthetic raw
    detections, and raises or sleeps for the failure and slow scenarios;
  - `get_card_reader()`, which selects by `settings.ocr_mode`.
  Put the palette and its synthetic values in `api/app/services/card_reader_fake_data.py`, and
  export the palette as JSON to `e2e/tests/fixtures/ocr-scenarios.json` for the e2e image
  helper.
- [X] T014 Implement `api/app/services/card_reading_service.py`, part 1 (research R5):
  - **`mark_pending(db, draft, side, file_name, client_id)`**: called inside the upload
    transaction. It resets `card_readings.state` to `pending` and clears
    `card_readings.raw`, `card_readings.result` and `card_readings.reason`.
  - **`queue_if_ready(draft_id)`**: when both sides have an image and a pending side exists, it
    submits `run(draft_id)` to a module `ThreadPoolExecutor(max_workers=2)`.
  - **`run`**: it uses its own session and sets `running` with `card_readings.started_at`. In
    the same transaction, it writes one `image_access_log` row per side sent, with
    `image_access_log.purpose = 'ocr'` and `user_id` = the uploader (analysis C1). Then
    it calls the reader for each pending side and checks `card_readings.image_file_name`
    against the current image, dropping stale results. It stores `raw` and the outcome of T012
    with `card_readings.finished_at` and `card_readings.duration_ms`.
  - **Failures**: an exception or a timeout becomes `failed` with `timeout`, `unavailable` or
    `error`. The overall limit is 60 s.
  - **`sweep_stale(db)`**: it turns `running` rows older than 60 s into `failed/timeout`. Call it
    at startup in `api/app/main.py` and lazily in the status read.
  - **Logs**: only the draft id, side, state, reason and ms.
- [X] T015 [P] In `api/app/schemas/drafts.py`, add these schemas (contracts/api.md):
  - the new `DraftOut` keys `no_surname`, `card_fields`, `national_id_check` and
    `card_reading`;
  - `CardReadingSideOut` and `CardReadingStatusOut`;
  - the `DraftChanges` keys `no_surname: bool | None` and `national_id_confirmed: bool | None`.

  Then extend `draft_service.to_out` to fill the new keys. The raw result is never included
  (research R11).
- [X] T016 [P] In `web/src/lib/drafts.ts`, add the matching types: `CardFieldMark`,
  `CardReadingSide`, `NationalIdCheck`, the `Draft` keys and the `DraftChanges` keys. Add
  `web/src/lib/cardReading.ts` with the labels and reason texts of contracts/api.md › UI strings
  and `getCardReadingStatus(id)`.
- [X] T017 [P] Add synthetic-image helpers:
  - **pytest**: `api/tests/helpers/card_images.py` with `scenario_jpeg(name)`, a plain image
    with the scenario's corner colour and the text «بطاقة تجريبية», made by Pillow.
  - **e2e**: `e2e/tests/helpers/cardImages.ts`, a canvas image with the same corner colour,
    read from `e2e/tests/fixtures/ocr-scenarios.json`.

**Checkpoint**: reader image builds; rules and fake reader tested; the job can run end to end
with the fake reader.

**Batch 1 notes (2026-11-23)**:
- `httpx` was a dev-only dependency of `api`; it is now a runtime dependency (the e2e stack
  caught the crash at start-up).
- `ocr/service/reader.py` puts back `<` fillers that OCR drops from the middle of MRZ line 2
  before computing the composite check (step 0 card 1). Fillers count as 0, so wrong data
  cannot pass. On the 11 private cards: 6 backs verified, 2 real misreads unverified, 3 with
  the composite digit itself unread (unverified, so no cross-check for them).
- Extra foundation tests: `api/tests/integration/test_card_reading_job.py` (fake reader after
  JPEG recompression, job states, `purpose = 'ocr'` access rows, stale results dropped,
  timeout, sweep, cascade on delete).

---

## Phase 3: User Story 1 - A clear card fills the form by itself (Priority: P1) 🎯 MVP

**Goal**: After both images are uploaded, the eight fields fill and are marked «من البطاقة».
The no-surname choice is available.

**Independent Test**: Upload clear synthetic front and back to a new draft (quickstart A, B,
E, M).

### Tests for User Story 1

- [X] T018 [P] [US1] Write integration tests `api/tests/integration/test_card_reading.py` with
  `OCR_MODE=fake`, running jobs synchronously through a test hook:
  - **Front only**: the side is `pending` and no reader call is made.
  - **Then the back**: the 8 fields are filled per data-model.md › Applying a `done` pair, with
    `card_fields[field].source = "card"`, plus `original`, `confidence` and `from`. `version`
    goes up and `last_client_id` is the uploader's.
  - **An invalid name**: one with a Latin letter is left empty, but its `original` is stored.
  - **Front ID missing, MRZ verified**: `national_id` is filled from the MRZ with
    `from = "mrz"`.
  - **Another marketer**: `GET …/card-reading` on that marketer's draft returns 404.
  - **Access log**: each side sent to the reader adds one `image_access_log` row with
    `purpose = 'ocr'`; viewing an image still adds `purpose = 'view'` (analysis C1).
- [X] T019 [P] [US1] Write tests `api/tests/integration/test_card_fields.py`, part 1, for
  `drafts.no_surname` (data-model.md › Rules on save):
  - `PATCH {no_surname: true}` clears `surname`, satisfies `missing`, and sets the surname mark
    to `edited`;
  - a non-empty surname resets it;
  - the CHECK holds;
  - the front scenario with an empty surname gives `card_reading.front.surname_empty = true`,
    and does not set `no_surname`.
- [X] T020 [P] [US1] Write Vitest tests `web/src/__tests__/cardReading.test.ts`, part 1:
  - polling starts while a side is `pending`/`running` and stops when none is;
  - merging after `done` fills only keys with no pending local change;
  - the marks map from `card_fields`.

### Implementation for User Story 1

- [X] T021 [US1] In `card_reading_service.py`, part 2, implement `apply_pair(db, draft_id)`. It
  takes a row lock and uses the mapping table of data-model.md › Applying a `done` pair, with
  `clean_arabic_name`, `normalize_national_id` and `normalize_family_number`. It then:
  - writes a field only when `card_fields[field]` is absent or `card` (FR-007), always updating
    `original`;
  - recomputes `full_name`;
  - re-evaluates `drafts.national_id_check` (the stub returns null until US4);
  - increments `version` and sets `last_client_id = card_readings.queued_by_client`.
  `run` calls it once both sides have finished.
- [X] T022 [US1] In `api/app/services/draft_service.py`, change `save_image` to call
  `mark_pending` inside its transaction. In `api/app/api/drafts.py`, after the upload commits,
  call `queue_if_ready` through FastAPI `BackgroundTasks`. Add `GET
  /api/drafts/{id}/card-reading`, which uses `get_owned` and `sweep_stale` and returns
  `CardReadingStatusOut` (contracts/api.md).
- [X] T023 [US1] In `draft_service.apply_changes` and `draft_validation.missing`, handle
  `no_surname` (research R9, data-model.md › `drafts.no_surname`). The surname is required
  unless `no_surname`. Add the cases to `api/tests/fixtures/draft_validation_cases.json` and
  update `web/src/lib/draftValidation.ts` to match.
- [X] T024 [US1] In `web/src/lib/draftFormController.ts`, add the reading state:
  - start a 2 s `getCardReadingStatus` poll after an upload response shows `pending`, or when the
    draft opens with a `pending`/`running` side;
  - on a side reaching `done`, `reshoot` or `failed`, fetch the draft and merge the card fields,
    skipping `queue.hasPendingKey(field)`;
  - take `card_fields`, `card_reading` and `no_surname` from the server.
  Expose them through `useDraftAutosave`.
- [X] T025 [P] [US1] Add `web/src/pages/marketer/subscriber/FieldSourceMark.tsx`, a small chip
  showing «من البطاقة» or «عُدِّل يدوياً». Use it in `CardDataSection.tsx` beside the eight
  fields.
- [X] T026 [US1] In `CardDataSection.tsx`, add the checkbox «لا يوجد لقب على البطاقة»
  (`saveNow({no_surname})`), which disables and clears the surname input. Show the hint from
  contracts/api.md when `card_reading.front.surname_empty`.
- [X] T027 [US1] In `CardSection.tsx`, show «ارفع الوجه الآخر لتبدأ قراءة البطاقة» when only one
  side exists, and «جارٍ قراءة البطاقة» (with a progress indicator) while a side is `pending` or
  `running`.
- [X] T028 [US1] Add the Playwright spec `e2e/tests/card-reading.spec.ts` with quickstart A, B,
  E and M. Use synthetic scenario images from `cardImages.ts`, and a second browser context for
  M.

**Checkpoint**: MVP: a clear synthetic card fills the form on one device and shows on another.

---

## Phase 4: User Story 2 - Correct a field; the original reading is kept (Priority: P1)

**Goal**: Edits become final values, marks switch to «عُدِّل يدوياً», the original reading stays,
and a reading never overwrites an edit.

**Independent Test**: quickstart C.

### Tests for User Story 2

- [X] T029 [P] [US2] Write `test_card_fields.py`, part 2, for the `drafts.card_fields` provenance
  rules (data-model.md › Rules on save):
  - a PATCH of a card field sets `source = "edited"` and keeps `original`;
  - clearing a field counts as edited;
  - typing the national ID before the reading → the reading keeps it and updates `original`
    (FR-007);
  - a PATCH that tries to send `card_fields` gets 422.
- [X] T030 [P] [US2] Write Vitest `cardReading.test.ts`, part 2: a field typed during the reading
  keeps the typed value after the merge, and its mark becomes «عُدِّل يدوياً».

### Implementation for User Story 2

- [X] T031 [US2] In `draft_service.apply_changes`, mark the edited fields (research R8): any
  change to a key of `CARD_FIELDS` sets `card_fields[key].source = "edited"` and keeps
  `original`, `confidence` and `from`.
- [X] T032 [US2] Extend `card-reading.spec.ts` with quickstart C (edit the grandfather → the mark
  changes; reload → the value and mark persist).

**Checkpoint**: US1 and US2 together meet the acceptance criterion «يعدّل حقلاً واحداً فتبقى
القراءة الأصلية محفوظة».

---

## Phase 5: User Story 3 - Unclear or wrong photo: «أعد التصوير» (Priority: P2)

**Goal**: Each side shows its reason, «أعد التصوير» and the tips. Manual entry is never blocked.

**Independent Test**: quickstart G, H, I, J.

- [X] T033 [P] [US3] Add integration cases to `test_card_reading.py` with the fake scenarios:
  - `no_card`, `wrong_side`, `multiple` and `not_unified` → the side is `reshoot` with that
    reason, and no field is filled from it;
  - the duplicate detection → `done`;
  - a front `reshoot` with a back `done` → only the back's family number is applied (spec edge
    case).
- [X] T034 [US3] In `web/src/pages/marketer/subscriber/ImageSlot.tsx`, show the side's reason
  text, «أعد التصوير» (opening the same camera/gallery choice) and the tips from contracts/api.md
  when `card_reading.<side>.state = reshoot`. Fields stay editable. Extend `card-reading.spec.ts`
  with quickstart G, H, I and J.

**Checkpoint**: Batch 2 ends. Run all tests and report.

**Batch 2 notes (2026-11-23)**:
- `AutosaveQueue.hasPendingKey` now also covers the request in flight. Without it, a reading that
  finished while a typed field was being saved would put the read value back on screen (the
  server kept the typed one). Found by `cardReading.test.ts`.
- Tests run the reading inline on the test session with the fake reader (`conftest.py`
  `_card_reading_runs_inline`).
- `test_drafts_list_delete` now expects the two `purpose = 'ocr'` access rows next to the
  marketer's `view` row (analysis C1).
- US6's "re-read only the replaced side" already holds: the job reads only `pending` sides and
  `apply_pair` reuses the other side's `done` result (tested in `test_card_fields.py`).

---

## Phase 5b: User Story 7 - The other fields on the back (Priority: P2, owner change)

**Goal**: The back also fills the date of birth, place of birth, issue date, expiry date and
issuing authority, accepted only when cross-checked (research R13). All five are required, and
an expired card blocks sending (system.md v1.8).

**Independent Test**: synthetic clear back → five fields filled and marked; synthetic expired
back → «البطاقة منتهية الصلاحية» in the missing items.

### Tests for User Story 7

- [X] T056 [P] [US7] Add unit tests to `api/tests/unit/test_card_reading_rules.py` for the
  back-field rules (research R13, data-model.md › Applying a `done` pair). Use synthetic dates
  only:
  - **MRZ dates**: the MRZ birth date with its own check digit is accepted, and the century comes
    from the national ID; the expiry is 20xx.
  - **Wrong birth check digit**: the printed birth date is accepted only with two agreeing
    candidates and a year equal to the national ID's first four digits. One candidate, or a
    wrong year, gives empty.
  - **Issue date**: accepted only when it equals expiry − 10 years + 1 day; otherwise empty.
  - **MRZ expiry unusable**: the printed expiry and issue are accepted together when they are
    consistent.
  - **Invalid dates**: dates such as `2034/13/40` are rejected.
  - **Authority**: snapped to the known text at a similarity of 0.70 or more; empty below that.
  - **Place of birth**: the text rule.
- [X] T057 [P] [US7] Add integration tests to `api/tests/integration/test_card_reading.py` and
  `test_card_fields.py` with new fake scenarios: `clear_back` with bands, `back_birth_print`
  (MRZ birth wrong, printed agrees), `back_issue_mismatch`, `back_expired`:
  - **Filling**: the five fields fill with marks and `original`.
  - **Expired card**: `missing` has `card_expired`.
  - **Edits**: an edited date is kept after a re-read.
  - **Variety (owner request)**: synthetic cases include a female card and a birth after
    2000 (century from the national ID «20…»).
  - **Bad values**: a PATCH with a bad date or a Latin place of birth gets 422.
- [X] T058 [P] [US7] Extend the shared fixture `draft_validation_cases.json` (api and web
  copies): the five required back fields, plus `card_expired` judged against a fixed «today»
  given in the case.

### Implementation for User Story 7

- [X] T059 [US7] Write migration `api/migrations/versions/0008_card_back_fields.py` and the model
  columns (data-model.md › Changes to `drafts`):
  - `drafts.birth_date`, `drafts.issue_date` and `drafts.expiry_date` (date);
  - `drafts.birth_place` and `drafts.issuing_authority` (text, CHECK ≤ 100);
  - `CARD_FIELDS` gains the five keys.
- [X] T060 [US7] Read the printed rows of the back in `ocr/service/reader.py` (research R13,
  contracts/ocr-service.md › `bands`):
  - **Locating**: rows by geometry from `city`/`nu_f`.
  - **Reading**: the Arabic recogniser and Tesseract candidates.
  - **Output**: `bands` on back detections.
  - **Tests**: extend `ocr/tests/test_service.py` (a synthetic back is not detected, so `bands`
    is absent; plus a unit test of the row geometry on fixed boxes). Rebuild the image.
- [X] T061 [US7] Add the back-field rules to `api/app/services/card_reading_rules.py` (R13 rules
  1–5): `_back_result` gains `dates: {birth, expiry, issue}`, each with `value`, `original` and
  `from`, plus `birth_place` and `authority`. Put the constants in `api/app/core/card_reading.py`
  (data-model.md › Constants). The national ID used for the century and the year check is the
  front's normalized ID, or the verified MRZ ID, passed in by `apply_pair`.
- [X] T062 [US7] Map the five fields in `card_reading_service.apply_pair` (data-model.md ›
  Applying a `done` pair) with the FR-007 rules. In `draft_service.apply_changes`, add the PATCH
  keys: ISO dates; `birth_place` checked by `clean_place_text` (Arabic letters, spaces, «-»,
  «/»), with 422 `invalid_place_text`; `issuing_authority` limited to ≤ 100. Add these to
  `DraftChanges`/`DraftOut` and to the edited marks.
- [X] T063 [US7] In `draft_validation.missing` (api) and `computeMissing` (web), make the five
  fields required and add `card_expired`: `expiry_date` before today in Baghdad
  (`app.core.timeutil`). The page passes its Baghdad «today».
- [X] T064 [US7] Web: add the five fields to the «بيانات البطاقة» section after the family number,
  plus the FR-032 warning «سنة الميلاد لا تطابق الرقم الوطني، تأكد منهما» (warning only, not a
  missing item):
  - **Dates**: native date inputs, saved immediately.
  - **Text**: the place of birth and authority as text fields.
  - **Marks**: «من البطاقة» / «عُدِّل يدوياً» on all five.
  - **Expired card**: an «البطاقة منتهية الصلاحية» alert.

  Add them to `FormValues`, `valuesFromDraft`, `CARD_FIELDS` (web) and the missing-summary labels.
- [X] T065 [US7] Update the fake reader data (`card_reader_fake_data.py`): synthetic bands and
  MRZ dates for the clear back, plus the new scenarios of T057. Regenerate
  `e2e/tests/fixtures/ocr-scenarios.json`.
- [X] T066 [US7] Extend `e2e/tests/card-reading.spec.ts`:
  - quickstart B checks the five back fields and their marks;
  - an expired back shows «البطاقة منتهية الصلاحية» and lists it in «النواقص».
- [X] T067 [US7] Re-run the owner's private check (T050 method, outside the repository) with the
  real reader on `test-cards/`. Report per-field correct, empty and wrong counts and the time per
  back. Accept only 0 wrong values.

**Checkpoint**: Batch 2b ends. Run all tests and report.

**Batch 2b notes (2026-11-23)**:
- Owner: place of birth option 1 (`fix_place_separators`: a lone «ا» between words → «/», a known
  governorate or city glued to the previous letter gets «-»); ~10 s per card accepted; the
  reading attempts stay as they are.
- 005 tests updated for the five new required items (missing counts 18 → 23, complete-draft
  fixtures).
- T067 (15 private cards, final code, nothing kept): birth 15/15, expiry 15/15, issue 14 right +
  1 empty, authority 14 right + 1 empty, **0 wrong dates**. National ID right on all 15. Place of
  birth exact on 3/15: the recogniser mostly turns «-» and «/» into spaces (no rule can tell
  which one was printed) and sometimes drops a letter, so it stays a «من البطاقة» value to
  check. Back reading 3.2–11.5 s on 2 CPUs.

---

## Phase 6: User Story 4 - National ID cross-check with the MRZ (Priority: P2)

**Goal**: A verified MRZ that differs from the national ID asks the marketer to confirm. An
unverified MRZ is ignored.

**Independent Test**: quickstart F.

### Tests for User Story 4

- [ ] T035 [P] [US4] Write `test_card_fields.py`, part 3, for `drafts.national_id_check`
  (data-model.md, research R7):
  - equal → no mismatch;
  - different → `mismatch: true`, and `missing` contains `national_id_unconfirmed`;
  - `{national_id: X, national_id_confirmed: true}` → confirmed, and the item is no longer
    missing;
  - changing `national_id` afterwards clears the confirmation and the comparison runs again;
  - an unverified MRZ (composite false or null) → `national_id_check` is null;
  - a typed value that differs from a verified MRZ is also flagged.

### Implementation for User Story 4

- [ ] T036 [US4] In `card_reading_service.py`, implement `refresh_national_id_check(draft)` and
  call it from `apply_pair`. It reads the verified MRZ from `card_readings.result` of the back
  and sets `drafts.national_id_check = {mrz, confirmed_value}` or null (data-model.md). In
  `draft_service.apply_changes`, handle `national_id_confirmed` and clear `confirmed_value` on
  any `national_id` change. In `draft_validation.missing`, add `national_id_unconfirmed` with the
  label «تأكد من الرقم الوطني», in both the shared fixture and `draftValidation.ts`.
- [ ] T037 [US4] Add `web/src/pages/marketer/subscriber/NationalIdCheck.tsx` below the national
  ID field. It shows «تأكد من الرقم الوطني» with «الرقم الحالي» and «في الشريط الآلي» and an
  «اعتماد هذا الرقم» button for each; a button calls `saveNow({national_id, national_id_confirmed:
  true})`. It is hidden when there is no mismatch or the mismatch is confirmed.
- [ ] T038 [US4] Extend `card-reading.spec.ts` with quickstart F (the summary lists the national
  ID until it is confirmed).

---

## Phase 7: User Story 5 - Reading is unavailable: the form keeps working (Priority: P3)

**Goal**: A failure or a timeout shows the message with «أعد المحاولة». Nothing is lost.

**Independent Test**: quickstart K, L.

- [ ] T039 [P] [US5] Add integration cases to `test_card_reading.py`:
  - the fake failure → `failed/unavailable`;
  - the slow scenario with a reduced limit → `failed/timeout` (the limit is patched in tests);
  - a `running` row older than 60 s → `failed/timeout` on `GET …/card-reading`;
  - retry re-queues the failed sides and returns 202, while a draft with nothing failed gets
    409 `reading_not_retryable`;
  - the fields typed meanwhile are kept;
  - retry on another marketer's draft returns 404 (FR-021, analysis L1).
- [ ] T040 [US5] Add `POST /api/drafts/{id}/card-reading/retry` in `api/app/api/drafts.py` and
  `card_reading_service.retry()` (contracts/api.md). Add the error code `reading_not_retryable`
  to `api/app/errors.py`.
- [ ] T041 [US5] In `CardSection.tsx`, show «تعذّرت القراءة الآلية، أكمل يدوياً» with «أعد
  المحاولة» (calling retry, then polling) when any side is `failed`. Extend
  `card-reading.spec.ts` with quickstart K and L.

---

## Phase 8: User Story 6 - Replacing an image reads again (Priority: P3)

**Goal**: Replacing a side reads it again. Unedited fields take the new values; edited fields
stay.

**Independent Test**: quickstart D.

- [ ] T042 [P] [US6] Add integration cases to `test_card_reading.py`:
  - after a reading and an edit, replacing the front with another clear-front scenario → the
    unedited fields change and the edited one does not;
  - `card_readings.raw` and `card_readings.result` of the replaced side are new, and the
    original readings belong to the new image;
  - a result whose `card_readings.image_file_name` no longer matches is dropped (US6-3);
  - only the replaced side is re-read; the other side's `done` reading is reused;
  - deleting the draft removes its `card_readings` rows (FR-010, analysis L2).
- [ ] T043 [US6] Make the job re-read only the `pending` sides and reuse the other side's
  `done` result in `apply_pair` (research R5). Then extend `card-reading.spec.ts` with quickstart
  D.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T044 [P] Licences (FR-022, research R12):
  - in `api/app/api/client_config.py`, add `open_source` from `ocr_source_url`, falling back to
    the upstream URL (contracts/api.md), with a test in
    `api/tests/integration/test_client_config.py`;
  - in `web/src/pages/AccountPanel.tsx`, add «رخص البرمجيات المفتوحة» as a dialog with the
    name, «AGPL-3.0» and the link;
  - add quickstart N to the e2e spec.
- [ ] T045 [P] In `api/tests/integration/test_log_safety.py`, run a full fake reading and a
  failure, then assert that no synthetic name, national ID, family number or MRZ text appears in
  the captured logs or the error bodies (FR-019, SC-007).
- [ ] T046 [P] Add `ocr/service/evaluate.py`, the owner's offline check: it reads the paths given
  on the command line and prints detections, fields, MRZ checks and timing to stdout. It writes
  no file. Document it in `ocr/UPSTREAM.md` and quickstart › Real-reader check.
- [ ] T047 [P] Update `deploy/staging.md` with a new section «قارئ البطاقة (الفيزة 006)»:
  - build `ocr` on the server (internet for the build only, ~5 GB of disk);
  - the checks I1–I4 from quickstart;
  - set `OCR_MODE`, `OCR_URL` and `OCR_SOURCE_URL`;
  - «انشر مجلد ocr/ إلى النسخة العامة قبل كل نشر يغيّره»;
  - the reader's memory and CPU limits.
- [ ] T048 [P] In `README.md`, add an `ocr/` row and a licence note: the reader is AGPL-3.0 with
  a public copy, and the rest of the app is private.
- [ ] T049 Run the isolation checks I1–I5 (quickstart) on the dev stack with the real reader:
  - no internet from `ocr`;
  - no published port;
  - `api` reaches `/health`;
  - limits of 2 CPUs and 2 GiB;
  - no card numbers in the logs.
  Record the results in the batch report.
- [ ] T050 Owner's real-reader check (SC-002), run by the agent on the owner's machine **outside
  the repository**:
  - `ocr/service/evaluate.py` on `test-cards/` in a `--network none` container;
  - compare with step 0;
  - measure the time from the second upload to the filled fields for clear cards (SC-001,
    analysis M1);
  - report in Arabic; nothing is saved.
- [ ] T051 Full gate:
  - `pytest` (api), `pytest` (ocr image), `vitest`, lint and format (api, web);
  - `scripts/e2e.sh` (all projects);
  - `docker compose up` with the real reader, then a manual pass of quickstart B with a real card
    photo by the owner.
- [ ] T052 Mark `specs/006-card-ocr/checklists/requirements.md` and these tasks done. Write the
  Arabic manual-test steps in `specs/006-card-ocr/manual-test-ar.md` (CLAUDE.md). Verify
  quickstart A–N.
- [ ] T053 Before the first staging deployment, remind the owner, then create the public copy of
  `ocr/` on the owner's GitHub account (owner's instruction). Then set `OCR_SOURCE_URL` in the
  server `.env`. This is an outward-facing step, so confirm first.
- [ ] T054 Staging check (owner): reader healthy, I1–I4 on the server, one real card read end to
  end within 15 s of the second upload (SC-001, analysis M1), and the licence link opens the
  public copy.
- [ ] T055 Update `CLAUDE.md` only if a new runtime instruction is needed, for example «لا
  تشغّل قارئ البطاقة على صور حقيقية إلا بحاوية بلا شبكة». Otherwise leave it unchanged.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**:
  - T001 → T002, T003 → T004 → T005.
  - T006 needs T002.
  - T007 is independent.
- **Foundational (Phase 2)**: needs T007, and blocks every story.
  - T008 → T009 → T014.
  - T010 → T011 → T012 → T014.
  - T013 → T014.
  - T015, T016 and T017 run in parallel with that chain.
- **US1 (Phase 3)**: needs Foundational. This is the MVP.
  - T021 → T022.
  - T023 needs T015.
  - T024 needs T016 and T022.
  - T025–T027 need T024.
  - T028 is last.
- **US2 (Phase 4)**: needs US1 (T021, T024).
- **US3 (Phase 5)**: needs US1 (the job and the polling).
- **US4 (Phase 6)**: needs US1 (`apply_pair`).
- **US5 (Phase 7)**: needs US1.
- **US6 (Phase 8)**: needs US1 and US2 (edits must survive a re-read).
- **US7 (Phase 5b, owner change)**: needs US1 (`apply_pair`, marks) and US2; done before
  batch 3.
- **Polish (Phase 9)**: after every story. T053–T054 come only at deployment time, and T055 is
  last.

**Within each story**: tests first (they must fail), then the service, then the routes, then
the UI, then e2e. `draft_service.py`, `card_reading_service.py`, `api/drafts.py` and
`card-reading.spec.ts` are edited by several stories, so edit them one task at a time.

### Parallel Opportunities

- **Setup**: T003 alongside T002; T005 and T007.
- **Foundational**: T010, T011, T013, T015, T016 and T017, alongside the migration and model
  chain.
- **US1**: T018, T019, T020 and T025.
- **Later stories**: their test tasks (T029, T030, T033, T035, T039 and T042) can be written
  together.
- **Polish**: T044–T048.

## Parallel Example: Foundational

```bash
Task: "T011 Unit tests in api/tests/unit/test_card_reading_rules.py"
Task: "T013 api/app/services/card_reader.py (Http + Fake)"
Task: "T016 web/src/lib/drafts.ts types + web/src/lib/cardReading.ts"
Task: "T017 Synthetic image helpers (pytest + e2e)"
# then T012 (rules) → T014 (job), after T008 → T009
```

---

## Implementation Strategy

### MVP (acceptance criterion)

1. Batch 1: Phases 1–2. The reader image builds and passes its own tests; the rules and the fake
   reader are tested.
2. Batch 2: US1 (fill + no-surname), US2 (edits keep the original), US3 (re-shoot). The
   acceptance criterion holds here: a clear card fills, an edit keeps the original, and an
   unclear photo gives «أعد التصوير» with manual continuation. Stop and validate.

### Incremental delivery

3. Batch 3: US4 (national ID cross-check), US5 (failure and retry), US6 (replace re-reads).
4. Polish:
   - licences link, log safety, the evaluate tool, docs;
   - isolation checks, the owner's real-reader check;
   - the full gate, `docker compose up`, and the Arabic manual steps.
5. At deployment: remind the owner, create the public copy (T053), then do the staging check
   (T054).
