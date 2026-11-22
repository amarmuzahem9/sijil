# Research: Automatic National Card Reading (OCR)

Decisions behind [plan.md](./plan.md). Step-0 evaluation of the reader (11 real cards, outside
the repository) is summarised in [spec.md › Clarifications](./spec.md#clarifications).

## R1. Where the reader's code lives and how we change it

- **Decision**: `ocr/` holds two parts:
  - `ocr/upstream/`: a verbatim copy of ID_Iraqi_Project at commit `c12a24e` (its `src/`,
    `models/SHA256SUMS`, `scripts/download_weights.py`, `requirements.txt`, `pyproject.toml`,
    `LICENSE`, `README*`). `ocr/UPSTREAM.md` records the URL, the commit, and every local
    change (none planned).
  - `ocr/service/`: our thin HTTP wrapper (≈200 lines) that imports `idcard_extractor` modules
    and reads **one side per request**.
- **Rationale**:
  - Keeping upstream untouched makes the AGPL obligation simple: the public copy (FR-022) is the
    `ocr/` folder.
  - Upstream fixes can be pulled by replacing `ocr/upstream/`.
  - The wrapper reuses the project's building blocks (`detect_cards`, `second_pass_confidence`,
    `orient_front`/`orient_back`, `detect_fields`, `recognize_fields`, `read_mrz`) and skips
    `combine_sides`/`validate` (owner decision 3).
- **Alternatives**:
  - `pip install` from GitHub at build time: hides the code we ship and still needs a public
    copy.
  - Rewriting the pipeline in `api/`: mixes AGPL code into the private app (forbidden by
    Principle VII as amended).

## R2. The reader image

- **Decision**: `ocr/Dockerfile`, based on `python:3.12-slim`:
  - **System packages**: `tesseract-ocr`, `libgl1`, `libglib2.0-0` and `libgomp1`.
  - **Python packages**: CPU-only `torch`/`torchvision` from the PyTorch CPU index first, then
    upstream `requirements.txt` (exact pins) and the wrapper's few packages (`fastapi`,
    `uvicorn`, `python-multipart`).
  - **Weights**: `findCard.pt`, `text.pt` and `MRZ1.pt` are fetched **at build time** from the
    project's `v1.0.0` release. `download_weights.py` checks them against `SHA256SUMS`, and the
    build fails on a mismatch.
  - **OCR model**: the PaddleOCR `arabic_PP-OCRv5_mobile_rec` model is pre-fetched at build into
    `/models/paddlex`.
  - **Runtime environment**: `YOLO_OFFLINE=1`, `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`, and
    `OMP_NUM_THREADS=2`. The service runs as a non-root user and listens on 8080.
- **Rationale**:
  - Step 0 showed the image works offline once the models are baked in (4.3 GB, ~1.4 GB RSS).
  - The CPU wheels avoid ~2 GB of CUDA libraries.
  - Note: the README's weight URL (`Hai800Z/Id_iraqi`) is stale; the assets are on
    `Hai800Z/ID_Iraqi_Project` releases.
- **Alternatives**:
  - Downloading weights at container start: needs internet at runtime, which is forbidden.
  - GPU image: the server has none.

## R3. Network isolation and resources

- **Decision**: In `docker-compose.yml`:
  - A network `ocr_net` with `internal: true`.
  - `ocr` joins only `ocr_net` and publishes no port.
  - `api` joins `default` and `ocr_net` and calls `http://ocr:8080`.
  - Limits: `cpus: 2` and `mem_limit: 2g`. The healthcheck is `GET /health`, which answers only
    once all models are loaded.
  - `api` does **not** depend on `ocr`'s health, so the app starts and works even if the reader is
    down (US5).
- **Rationale**:
  - An internal Docker network has no route out, which is FR-018 without firewall rules.
  - The limits match the owner's 2 processors / 2 GB budget. Measured peak was 1.38 GB.
- **Alternatives**: running the reader inside the `api` container (forbidden: shared process and
  licence mixing); a host firewall rule (not portable, easy to forget).

## R4. The reader's HTTP contract: raw detections only

- **Decision**: `POST /read` (multipart: `image`, `side` = `front|back`) returns every detected
  document in the photo:
  - its class, detection and second-pass confidences, and bounding box;
  - the chosen orientation;
  - each field's text and confidence;
  - for a back, the MRZ dict.
  - The MRZ dict includes `valid_number`, `valid_date_of_birth`, `valid_expiration_date` and
    `valid_composite`.
- **All business rules live in `api`** (R6): the side checks, merging duplicates, the second-document rule, normalization,
  the national-ID cross-check, and applying the values.
- **Rationale**: Rules must have pytest tests against a fake reader (Principle VIII). Keeping the
  reader dumb also keeps our AGPL-published changes minimal.
- **MRZ composite check**: `mrzmini` already returns `valid_composite` (step 0's script
  overwrote it by mistake). When the result comes from upstream's Tesseract fallback
  (`parse_td1`), which has no composite flag, the wrapper computes it from `raw_mrz` with the same
  ICAO 9303 rule (line 1 [5:30] + line 2 [0:7] + [8:15] + [18:29], check digit at line 2 [29]).
  If neither is available, `valid_composite` is `null`, which counts as not verified.
- **Dropped fillers (found in batch 1)**: OCR sometimes drops `<` fillers from the middle of
  MRZ line 2, so the composite digit is read from the wrong position (step 0, card 1). Before
  computing the composite, the wrapper rebuilds line 2 as `line[:-1]` padded with `<` to 29
  characters plus the last character. Fillers count as 0 in the sum, so this cannot make wrong
  data pass. When the last character is itself a filler (the digit was not read), the zone
  stays unverified.
- **Alternatives**: returning a ready-made "fill these fields" answer from the reader (puts our
  rules in AGPL code and makes them untestable without the models).

## R5. Running a reading: background job in `api`, polled by the page

- **Decision**:
  - **Upload**: An image upload (`POST /api/drafts/{id}/images/{side}`, unchanged route) saves
    the image and, in the same transaction, sets that side's `card_readings` row to `pending`
    with the image's `file_name`. When both sides exist after the upload, the upload response
    is returned, then a job is queued on an in-process `ThreadPoolExecutor(max_workers=2)` in
    `api`.
  - **The job** has its own DB session and runs these steps:
    1. Mark the pending sides `running`.
    2. Send each pending side's file to the reader.
    3. Store the raw result.
    4. Evaluate the rules.
    5. Apply the values to the draft in one locked transaction.
  - **Overall limit**: 60 s from the start of the job, including the wait (FR-014). The HTTP
    timeout per side is 45 s.
  - **Stale guard**: if the side's current `file_name` no longer matches (the image was replaced
    while reading), the result is dropped; the newer upload has queued its own job (US6-3).
- **Retry**: «أعد المحاولة» calls `POST /api/drafts/{id}/card-reading/retry`, which re-queues the
  failed or timed-out sides.
- **Access log (analysis C1)**: each side sent to the reader writes an `image_access_log` row
  with `purpose = 'ocr'` and the uploader as `user_id`, in the same transaction that marks the
  side `running` (Principle II: every access is logged).
- **Restart safety**:
  - At startup, and lazily on read, any `running` reading older than 60 s becomes
    `failed/timeout`.
  - Jobs are not persisted beyond the rows. A restart simply needs «أعد المحاولة».
- **Page**: while any side is `pending` or `running`, the form polls
  `GET /api/drafts/{id}/card-reading` every 2 s (tiny body). When a side becomes `done`, it fetches
  the draft once and merges (R8).
- **Rationale**:
  - The upload stays fast, and the 3–10 s reading does not hold an HTTP request open through NPM.
  - The reader serializes work itself (R4: one inference at a time), so two `api` threads are
    enough.
  - No new queue service (Principle VI).
- **Alternatives**:
  - Reading inside the upload request: slow uploads, timeouts on weak networks.
  - Celery/RQ with Redis: a new service for a few readings a day.
  - Server-sent events: more moving parts than 2-second polling while a reading runs.

## R6. Rules for one side (owner decisions 4 and 6, FR-015)

Evaluated in `api/app/services/card_reading_rules.py` on the reader's raw detections:

1. **Unsupported documents**: Detections of class `addres`, `car` or `drive` with confidence ≥ 0.50
   → `reshoot/not_unified`, unless a valid card side is also found.
2. **Candidates**: Card candidates are the `iraq id card` (front) and `back` detections whose
   second-pass confidence is ≥ 0.50, upstream's own threshold.
3. **Merging duplicates**: two candidates are one card when their MRZ document numbers are equal
   and verified, or their boxes overlap with IoU ≥ 0.5. Keep the one with more readable fields.
4. **A second document** counts only if it is **high-confidence** (second pass ≥ 0.90) **or
   has readable fields**:
   - at least 2 front fields with text, or
   - a TD1 MRZ, or
   - a non-empty family number.

   Otherwise it is ignored. The 0.90 threshold sits above step 0's phantom front (second pass
   0.876, no fields), so that phantom is ignored while the owner's rule is kept as given.
5. **Outcome**:
   - 0 candidates of any side → `reshoot/no_card`.
   - Only the other side → `reshoot/wrong_side`.
   - ≥ 2 distinct candidates after merging → `reshoot/multiple`.
   - Exactly 1 candidate of the expected side → `done`. Its fields may still be partly empty.
6. **Family number**:
   - Upper-case the reading and remove spaces.
   - Turn `O` into `0` in the positions that must be digits (0–3), and in positions 5–17 when
     the character is `O`. Position 4 is the series letter and is kept.
   - Accept only `^\d{4}[A-Z][0-9A-Z]{13}$`. Anything else stays empty, and the raw text is kept.

- **Note (analysis L4)**: this is the normalization for storing the read value. The comparison
  key of Principle I (O treated as 0 everywhere) is applied by the duplicate check in 008.
- **Rationale**: These thresholds reproduce step 0 on all 11 cards:
  - the duplicate back in photo 22 merged;
  - the phantom front in photo 1 ignored;
  - photo 21 → `no_card`;
  - the family number fixed on card 8 and empty on card 6.

  The rule tests encode these cases with synthetic raw results.
- **Alternatives**: a lower "high confidence" threshold such as 0.80 (step 0's phantom would
  have caused a false re-shoot); readable fields only (narrower than the owner's rule).

## R7. National ID and the MRZ (owner decision 5, FR-011–FR-013)

- **Decision**: An MRZ is **verified** when it is TD1 and all four check digits are true. From a
  verified MRZ the national ID is `optional1` stripped of `<`, which must be 12 digits.
  - **Fill**: When the front gave no valid 12-digit ID, the national ID is filled from the MRZ
    (source `card`, `original.from = "mrz"`).
  - **Comparison**: It runs on the **current value** of `national_id` (typed or read) whenever a
    verified MRZ exists. It is not tied to the moment of reading:
    - equal → no warning;
    - different → `national_id_check = {mrz, value, confirmed: false}`.
  - **Confirmation**: The marketer confirms by sending
    `{national_id: <value>, national_id_confirmed: true}`, which stores `confirmed_value`. Any
    later change of `national_id` clears the confirmation.
  - **Missing summary**: The national ID counts as missing while it differs from the verified MRZ
    and is not confirmed for this exact value.
- **Rationale**: One rule covers typed and read values and the edit case (US4-5), and it is easy
  to test.

## R8. Field provenance and the "never overwrite" rule (FR-007–FR-009)

- **Decision**: `drafts.card_fields` (JSONB) holds one entry per card field (`first_name`,
  `father_name`, `grandfather_name`, `surname`, `mother_first_name`, `mother_second_name`,
  `national_id`, `family_number`). Each entry has:
  - `source`: `card` or `edited`;
  - `original`: the normalized text as read, or null when the field was not read;
  - `confidence`;
  - `from`: `front`, `back` or `mrz`.

  **Writing the fields:**
  - **A save that touches one of these fields**: Any client save (PATCH) that changes such a
    field sets `source = edited`. A field never read gets `{source: edited, original: null}`.
  - **A reading**: It writes a field only when the entry is absent or `source = card`. It sets
    `source = card`, the value, and `original`. A value that fails the field's rules is not
    written, but its `original` is still stored, and an `edited` field keeps its value while
    `original` is updated.
  - **The page**: When merging after a reading, it never replaces a field that has a pending
    local change (`hasPendingKey`). A save that was already in flight is rebased by the existing
    `same_client` 409 handling, so the typed value wins (spec edge case).
- **The reading's version bump**: Applying a reading increments `version` and sets
  `last_client_id` to the `X-Client-Id` of the upload that queued it. On that page the version
  poll sees `same_client` and only takes the new version. The card-reading poll then merges the
  values. Another device sees the usual «تغيّرت المسودة من جهاز آخر» notice (005 behaviour),
  then «تحميل الأحدث».
- **Alternatives**: a separate provenance table (more joins for 8 fixed keys); client-side
  provenance (lost across devices, untrustworthy).

## R9. «لا يوجد لقب على البطاقة» (FR-017)

- **Decision**: New boolean column `drafts.no_surname` (default false).
  - **Setting it**: `PATCH {no_surname: true}` also clears `surname`, and marks the surname
    entry `edited`.
  - **Clearing it**: a non-empty `surname` in a PATCH sets it back to false.
  - **Validation**: the surname is required unless `no_surname`.
  - **A reading** never sets it. When the front was read and the surname text is empty, the
    reading result carries `surname_empty_on_card: true` so the page shows the hint next to the
    checkbox.
  - **The full name** skips the empty surname as before.
- **Rationale**: Owner answer C; one column, explicit, visible to the reviewer.

## R10. Fake reader for development and tests (Principle VII, FR-020)

- **Decision**: `api` talks to the reader through `CardReader` (`app/services/card_reader.py`)
  with two implementations:
  - `HttpCardReader`: the real `ocr` service.
  - `FakeCardReader`: returns fixed synthetic raw results without any model.
  - **Selection**: `OCR_MODE=http|fake`. The default is `http` in production and `fake` in tests
    and e2e.
- **How the fake picks a scenario**: from the colour of the image's top-left 32×32 block, matched
  to the nearest of a small palette. Each colour is one scenario:
  - clear front;
  - clear back;
  - a front with an empty surname;
  - a mismatched national ID;
  - no card;
  - the wrong side;
  - two cards;
  - a duplicate detection;
  - a reader failure;
  - a slow reading.

  Colour survives the browser's resize and JPEG compression, unlike a file hash.
- **Test images**: pytest and Playwright draw plain synthetic images with that corner colour and
  the text «بطاقة تجريبية». No real card, no real name or number.
- **Real-engine checks**:
  - `ocr/tests/` calls `/health` and `/read` on a blank synthetic image (no detections, correct
    shape).
  - `ocr/tools/evaluate.py` lets the owner measure SC-002 on private photos **outside** the
    repository. It prints to the terminal only, like step 0.
- **Alternatives**: running the real models in CI (4.3 GB image, no real cards allowed, synthetic
  cards are not detected by the models).

## R11. What is returned to the page and what stays server-side

- **The page receives**:
  - each side's reading state and reason;
  - the `card_fields` marks (`source` only, plus `original` for the marketer's own draft);
  - `no_surname`;
  - `national_id_check` (the MRZ number and the confirmation state);
  - `surname_empty_on_card`.
- **Server-side only**: The raw per-side result (`card_readings.raw`) is never sent to the page
  in this feature. It is for 008 (copy to the request) and 010 (reviewer).
- **Logs**: they record only the draft id, side, state, reason and timing. They never include
  text, numbers or the MRZ (FR-019).
- **The reader itself**:
  - Its own log level is WARNING, and upstream's INFO logs (which print field labels, not values)
    are silenced.
  - Images go to the reader as request bodies and are kept in memory only.
  - `mrzmini`'s temporary files go to a `tmpfs` mounted at `/tmp`.

## R12. Publishing the reader's source (FR-022)

- **Decision**:
  - **In the app**: «حسابي» gets a «رخص البرمجيات المفتوحة» item that opens a dialog with the
    reader's name, licence (AGPL-3.0), and the link from `OCR_SOURCE_URL` (served by
    `/api/client-config`). If the variable is empty, the item shows the upstream URL and the
    licence.
  - **Creating the public copy**: the public fork is created on the owner's GitHub account at
    deployment time, after reminding the owner (their instruction). `deploy/staging.md` gets a
    step: «انشر مجلد ocr/ إلى النسخة العامة قبل كل نشر يغيّره».
- **Rationale**: Owner answer A. The link must be visible to network users (AGPL §13).
