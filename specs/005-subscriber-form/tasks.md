---

description: "Task list for feature 005: New Subscriber Form (single page)"
---

# Tasks: New Subscriber Form (single page)

**Input**: Design documents from `specs/005-subscriber-form/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's tests:
- a marketer cannot see another marketer's draft or its images
- a stale `version` gets a 409
- deleting a draft removes its files
- compression and field validation (vitest)
- the two-context acceptance test (Playwright)

Write each test task first and confirm it fails.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on
its own. The phases run in dependency order (analysis I2). US6 (location) and US7 (subscription)
come before US3, because the acceptance test of US3 fills both.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US7 from spec.md
- Paths follow plan.md: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)
- Test data is synthetic only: no real card images or subscriber data (CLAUDE.md)

**Implementation batches** (owner request: three batches, each ending at a phase boundary):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T016 |
| 2 | 3–5 (US1, US2, US6) | T017–T035 |
| 3 | 6–10 (US7, US3, US4, US5, Polish) | T036–T056 |

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add `python-multipart` and `Pillow` (pinned versions) to `api/pyproject.toml` dependencies (research.md R6). In `api/Dockerfile`, create `/data/uploads` owned by `app` (uid 10001) before `USER app` (research.md R7).
- [X] T002 [P] Add the `uploads` volume to `docker-compose.yml`:
  - mounted at `/data/uploads` on `api` only
  - declared under top-level `volumes:` as `uploads`, with no fixed `name:` (research.md R7)
  - not mounted on `web` or `proxy`
- [X] T003 [P] Add the variables of contracts/api.md › "Environment variables" to `.env.example`, with comments: `UPLOADS_DIR`, `MAX_IMAGE_BYTES`, `GOOGLE_MAPS_API_KEY` (empty; restrict by HTTP referrer in the Google console), `GOOGLE_MAPS_MAP_ID` and `MAP_DEFAULT_CENTER`.
- [X] T004 [P] Add the settings `uploads_dir`, `max_image_bytes`, `google_maps_api_key`, `google_maps_map_id` and `map_default_center` to `api/app/config.py`. `map_default_center` is parsed from `lat,lng`, and an invalid value is a startup error naming the variable. Defaults come from contracts/api.md.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Write the Alembic migration `api/migrations/versions/0005_drafts.py`, creating:
  - `drafts` per data-model.md › `drafts`:
    - `drafts.id`: uuid PK
    - `drafts.marketer_id`: FK RESTRICT
    - `drafts.status`: CHECK `= 'draft'`
    - length CHECKs on `drafts.subscriber_name`, `drafts.national_id`, `drafts.family_number`, `drafts.address`, `drafts.landmark` and `drafts.phone_input`
    - range CHECKs and a both-or-neither CHECK on `drafts.location_lat` and `drafts.location_lng`
    - `drafts.location_source`: `gps` or `map`
    - `drafts.location_accuracy_m`
    - `drafts.area_id`, `drafts.tower_id` and `drafts.plan_id`: FKs **ON DELETE SET NULL** (research.md R2)
    - the copies `drafts.area_name`, `drafts.tower_code`, `drafts.plan_name`, `drafts.trial_price` and `drafts.second_price`
    - `drafts.phone_normalized`: CHECK `^07[0-9]{9}$`
    - `drafts.version`: NOT NULL, default 1
    - `drafts.last_client_id`: uuid, nullable
    - `drafts.created_at` and `drafts.updated_at`: NOT NULL, default `now()`
    - index `(marketer_id, updated_at DESC)`
  - `draft_images` per data-model.md › `draft_images`:
    - `draft_images.id`: uuid PK
    - `draft_images.draft_id`: FK CASCADE to `drafts`
    - `draft_images.side`: CHECK
    - UNIQUE `(draft_id, side)`
    - `draft_images.file_name`
    - size and dimension CHECKs on `draft_images.size_bytes`, `draft_images.width` and `draft_images.height`
    - `draft_images.uploaded_by`: FK to users
    - `draft_images.created_at`
  - `image_access_log` per data-model.md › `image_access_log`:
    - `image_access_log.id`: identity PK
    - `image_access_log.user_id`: FK to users
    - `image_access_log.image_id` and `image_access_log.draft_id`: uuid, **no FK**
    - `image_access_log.side`
    - `image_access_log.created_at`: index DESC

  It has a working downgrade.
- [X] T006 [P] Create the SQLAlchemy models `Draft`, `DraftImage` and `ImageAccessLog` in `api/app/models/draft.py`, mirroring T005. Export them from `api/app/models/__init__.py`. Depends on T005.
- [X] T007 [P] Add every code of contracts/api.md › "New error codes" to `api/app/errors.py`. `draft_conflict` and `too_long` carry their extra fields through `AppError(extra=…)`.
- [X] T008 [P] Create `api/app/core/national_id.py` with `normalize_national_id(text) -> str | None` (research.md R9):
  - converts Arabic-Indic and Persian digits
  - strips spaces and direction marks, reusing the helpers in `app/core/phone.py`
  - returns the 12 digits or None

  Unit tests in `api/tests/unit/test_national_id.py`.
- [X] T009 [P] Create the shared fixture `api/tests/fixtures/draft_validation_cases.json`:
  - national IDs: 11, 12 and 13 digits, Arabic digits, with spaces, with letters
  - phones: reuse the §8.1 cases
  - empty and whitespace-only text
  - over-length text

  Copy it to `web/src/__tests__/fixtures/draft_validation_cases.json`.
- [X] T010 Create `api/app/services/draft_validation.py`. `missing(draft, images) -> list[{field, code}]` follows the order and codes of data-model.md › "Validation rules". Unit tests in `api/tests/unit/test_draft_validation.py`, driven by the T009 fixture. Depends on T006, T008 and T009.
- [X] T011 [P] Create `web/src/lib/nationalId.ts` (mirror of T008) and `web/src/lib/draftValidation.ts` (mirror of T010). The mirror keeps the same field order and codes, with these Arabic messages: «مطلوب», «الرقم الوطني 12 رقماً», «رقم غير صالح», «النص أطول من المسموح». Tests in `web/src/__tests__/draftValidation.test.ts`, driven by the shared fixture.
- [X] T012 [P] Add `api/app/schemas/drafts.py`, per contracts/api.md:
  - `DraftChanges`: `extra="forbid"`, all fields optional, a `location` sub-model, no price or copy fields
  - `PatchBody {version, changes}`
  - `DraftOut`, with `images`, `missing` and `notices`
  - `DraftListItem`
  - `VersionOut {version, updated_at, same_client}`
- [X] T013 Create the base of `api/app/services/draft_service.py`. Depends on T006, T007, T010 and T012.
  - `get_owned(db, user, id)` raises 404 `draft_not_found` both when the draft is missing and when another marketer owns it.
  - `apply_changes` handles the text fields, the location and the phone:
    - It trims text, and an empty value becomes null.
    - It raises `too_long` per data-model.md › `drafts.subscriber_name`, `drafts.national_id`, `drafts.family_number`, `drafts.address`, `drafts.landmark` and `drafts.phone_input`.
    - It sets data-model.md › `drafts.phone_normalized` from `app/core/phone.py` when the phone is valid, and otherwise to null.
  - `to_out(draft)` fills `missing` from T010.
  - No field value is logged (FR-022).
- [X] T014 Create the router `api/app/api/drafts.py` and register it in `api/app/main.py`.
  - Draft routes use `require_roles("marketer")`.
  - A dependency `client_id()` reads `X-Client-Id`. It must be a UUID on writes, otherwise 422 `validation_error` (research.md R3, analysis U1).
- [X] T015 [P] Create `web/src/lib/drafts.ts` with typed calls for every route in contracts/api.md.
  - It holds one module-level `clientId = crypto.randomUUID()` per page load, sent as `X-Client-Id` on every draft call. It is never persisted.
  - The image upload is a stub here, finished in T027.
- [X] T016 Add the routes `/drafts/new` and `/drafts/:id` (marketer only, inside `MarketerLayout`) to `web/src/router.tsx`. Create the shell `web/src/pages/marketer/subscriber/SubscriberForm.tsx`:
  - the five section headings in the §5 order (FR-003)
  - a sticky header slot for the save badge
  - a bottom slot for «النواقص» and the disabled «إرسال»

**Checkpoint (end of batch 1)**: The schema, models, validation (server and client) and the empty form shell are in place, and all 001–004 tests still pass.

**Batch 1 notes (2026-11-22, T001–T016)**:
- **File names**: `draft_images.file_name` is `<uuid4().hex>.jpg` (32 hex characters). Migration 0005 adds a CHECK on that exact format as a path-traversal backstop.
- **Shared code**: `app/core/phone.py` and `web/src/lib/phone.ts` now export `to_latin_digits` / `toLatinDigits`, which the national-ID helpers reuse.
- **Fixture**: `draft_validation_cases.json` also carries `limits` and `missing_order`. Both sides assert their constants against it, and the server additionally checks `TEXT_LIMITS` in `models/draft.py`.
- **API client**: `apiFetch` gained an optional `headers` option, used for `X-Client-Id`.
- **Router**: `api/drafts.py` exposes the `client_id` dependency (required on writes) and `optional_client_id` (reads). The routes come with US1.
- **Form constants**: the section list and the send note live in `pages/marketer/subscriber/sections.ts`, which keeps fast refresh working.
- **Tooling pitfall**: `\uXXXX` escapes typed through the editing tools were written as the literal invisible characters. The strip patterns in `national_id.py` and `nationalId.ts` were rewritten with real escapes, and no hidden direction marks remain in `api/app` or `web/src`.
- **Dashboard button**: it stays disabled until T025 (batch 2).
- **Checks run**:
  - upgrade, downgrade 0004 and upgrade again on a scratch database: OK
  - the `api` container (uid 10001) can write to `/data/uploads`
  - the `sijil_uploads` volume exists
  - full gate `scripts/test-all.sh`: green

---

## Phase 3: User Story 1 - Fill the form and have it saved automatically (Priority: P1) 🎯 MVP

**Goal**: The form's text fields save themselves to the server, with a visible status and retry.

**Independent Test**: Start a new subscriber, type the name and address, close the browser, reopen the draft by its URL, and find both values.

### Tests for User Story 1

- [ ] T017 [P] [US1] Write integration tests in `api/tests/integration/test_drafts_autosave.py`:
  - **Create:**
    - PUT with a new UUID gives 201 and `version` 1.
    - A repeated PUT by the same owner gives 200 and leaves the draft unchanged (idempotent).
    - An admin gets 403, and an anonymous caller gets 401.
  - **PATCH:**
    - A current `version` updates only the given keys, and `null` clears a field.
    - `version` increases by 1 and `updated_at` changes. Text is trimmed.
    - An over-length value gives 422 `too_long` with `field`. An unknown key gives 422.
    - A missing or malformed `X-Client-Id` gives 422.
  - **Conflicts:**
    - A stale `version` sent with a different `X-Client-Id` gives 409 `draft_conflict` with `same_client=false` and the current `version`. This holds **for the same session too**, because two tabs share one session (analysis U1).
    - A stale `version` sent with the same `X-Client-Id` gives 409 with `same_client=true`.
  - **Version endpoint:** GET returns `{version, updated_at, same_client}`.
- [ ] T018 [P] [US1] Write `web/src/__tests__/autosaveQueue.test.ts` for the queue logic:
  - Changes made while a save is in flight merge into the next PATCH.
  - Only one request is in flight at a time.
  - The backoff is 2, 4, 8 … up to 30 s.
  - A `same_client` 409 triggers a silent rebase and resend.
  - A 409 from another client puts the queue in state `conflict`, with no further saves.
  - On `session_ended`, the queue pauses and keeps its pending changes. After `resume()` it sends them.

### Implementation for User Story 1

- [ ] T019 [US1] Add `create_if_absent` (PUT) and `patch` to `api/app/services/draft_service.py`.
  - Both use the single `UPDATE … WHERE id AND marketer_id AND version = :v RETURNING` statement of research.md R3.
  - Each save increases data-model.md › `drafts.version` by 1, sets `drafts.updated_at`, and sets `drafts.last_client_id` from `X-Client-Id`.
  - When no row matches but the draft exists, the response is 409 with `same_client = (drafts.last_client_id == client_id)`.
- [ ] T020 [US1] Add `PUT /drafts/{id}`, `GET /drafts/{id}`, `GET /drafts/{id}/version` and `PATCH /drafts/{id}` to `api/app/api/drafts.py`.
- [ ] T021 [US1] Create `web/src/lib/useDraftAutosave.ts`: the pure queue logic tested in T018, plus the hook.
  - Text fields save about 1 s after the last keystroke, and immediately on blur. Selects, the pin and buttons save immediately.
  - The first real change generates the UUID, sends the PUT, and calls `navigate(replace)` to `/drafts/{id}` (US1 scenario 4).
  - States: `saved | saving | offline | failed | conflict | deleted | session_ended`.
  - It retries on the `online` event.
  - Nothing is written to localStorage (research.md R3).
- [ ] T022 [P] [US1] Create `web/src/pages/marketer/subscriber/SaveBadge.tsx` (research.md R11):
  - «محفوظ»
  - «جارٍ الحفظ…»
  - «غير متصل — سيُعاد الحفظ تلقائياً»
  - «لم يُحفظ — إعادة المحاولة», shown as a button after 3 failures
- [ ] T023 [US1] Add the in-place sign-in for the form (research.md R3, analysis U2):
  - **API listener:** `web/src/lib/api.ts` gets an opt-in hook, `setSessionEndedInterceptor`. While the form is mounted, `session_revoked` or a failed refresh is routed to the form instead of the global sign-out redirect. `account_inactive` keeps the existing behaviour.
  - **Dialog:** `web/src/pages/marketer/subscriber/SignInDialog.tsx` shows «انتهت الجلسة، سجّل الدخول للمتابعة» with the phone and password fields.
    - Signing in as the same user id resumes the queue.
    - Signing in as a different user clears the form state and goes to `/`.
  - **Test:** `web/src/__tests__/sign-in-dialog.test.tsx`.
- [ ] T024 [US1] Build `web/src/pages/marketer/subscriber/CardDataSection.tsx` and wire it to the autosave hook:
  - the subscriber name
  - the national ID, LTR with a numeric keyboard
  - the family number, LTR, stored as typed

  `SubscriberForm.tsx` loads an existing draft with GET. A 404 shows «المسودة غير موجودة».
- [ ] T025 [US1] Point the dashboard button «إضافة مشترك جديد» in `web/src/pages/marketer/Dashboard.tsx` to `/drafts/new`.

**Checkpoint**: Text fields autosave and survive a reload. An ended session asks for sign-in over the form without losing values.

---

## Phase 4: User Story 2 - Card images: capture, compress, upload with progress (Priority: P1)

**Goal**: Front and back card images, compressed on the device and uploaded with progress, retry and private storage.

**Independent Test**: Upload a synthetic 4000×3000 image, see the progress bar, interrupt and retry, and confirm the stored file is a JPEG of at most 1600px on its longest edge with no public URL.

### Tests for User Story 2

- [ ] T026 [P] [US2] Write integration tests in `api/tests/integration/test_draft_images.py`. Each test uses a temporary `UPLOADS_DIR` and synthetic images generated with Pillow.
  - **Upload:**
    - A valid JPEG gives 200.
    - The file `<uuid>.jpg` exists.
    - The `draft_images` row matches the file.
    - `drafts.version` increases by 1.
    - The back side can be uploaded before the front (spec US2 scenario 7, analysis G3).
  - **Refusals:**
    - A PNG or a text file gives 422 `invalid_image`.
    - A file over `MAX_IMAGE_BYTES` gives 413 `image_too_large`.
    - A 2000×1000 image gives 422 `image_too_big_dimensions`.
  - **Replace:** replacing a side keeps one row and removes the old file.
  - **Access:**
    - Another marketer and an admin without `review` get 404. An anonymous caller gets 401.
    - The owner, the main admin and a `review` admin get 200 `image/jpeg` with `Cache-Control: private, no-store`.
    - Each successful open writes one row with the correct `image_access_log.user_id`, `image_id`, `draft_id` and `side`.
  - **Privacy:** no path under `/api` or the web serves the file by its name.
- [ ] T027 [P] [US2] Write `web/src/__tests__/imageCompress.test.ts`:
  - `fitWithin`: 4000×3000 → 1600×1200; a 1200×1600 portrait stays 1200×1600; 800×600 stays unchanged, with no upscaling.
  - `compressImage`, with a mocked `createImageBitmap` and canvas: `toBlob` is called with `'image/jpeg', 0.8`, and the fallback path is used when `createImageBitmap` throws.

### Implementation for User Story 2

- [ ] T028 [US2] Create `api/app/services/image_store.py` (research.md R6, R7):
  - a streamed read capped at `max_image_bytes`
  - a magic-bytes check, then Pillow `verify` and a reload to read the dimensions
  - write a temp file, `fsync`, then `os.replace` to `<uuid4>.jpg` in `uploads_dir`
  - `unlink_quietly(name)`, which logs the file name only
  - `open_path(name)`, with a path-traversal guard on data-model.md › `draft_images.file_name`
- [ ] T029 [US2] Add `save_image(db, ctx, client_id, draft, side, upload)` to `api/app/services/draft_service.py`:
  - upsert the row per data-model.md › `draft_images.side`, `draft_images.file_name`, `draft_images.size_bytes`, `draft_images.width`, `draft_images.height` and `draft_images.uploaded_by`
  - increase `drafts.version` and set `drafts.last_client_id`
  - commit, then unlink the replaced file
- [ ] T030 [US2] Add `POST /drafts/{id}/images/{side}` and `GET /draft-images/{image_id}` to `api/app/api/drafts.py`.
  - The image GET allows the owner, `super_admin`, or `has_any_permission(..., ["review"])`. Everyone else gets 404.
  - Every successful open inserts one row per data-model.md › `image_access_log.user_id`, `image_access_log.image_id`, `image_access_log.draft_id`, `image_access_log.side` and `image_access_log.created_at` (research.md R7, analysis C1).
  - It returns a `FileResponse` with the headers of contracts/api.md.
- [ ] T031 [P] [US2] Create `web/src/lib/imageCompress.ts` with `fitWithin` and `compressImage(file)`, per research.md R5 (EXIF orientation, 1600px, JPEG 0.8).
- [ ] T032 [US2] Finish `uploadDraftImage(id, side, blob, onProgress)` in `web/src/lib/drafts.ts`:
  - an `XMLHttpRequest` multipart upload with the bearer token and `X-Client-Id`
  - progress events
  - one automatic token refresh on 401 `token_expired`
  - Arabic error messages from the response `code`

  Also add `fetchImageObjectUrl(imageId)`: a blob fetch with `Authorization`, shown through `URL.createObjectURL`, and revoked on unmount.
- [ ] T033 [US2] Build `web/src/pages/marketer/subscriber/ImageSlot.tsx` and `CardSection.tsx` (front, then back):
  - Each slot shows **two separate buttons**, «تصوير» and «من المعرض», each with its own hidden input. Only «تصوير» has `capture="environment"` (research.md R5, the owner's requirement for Android).
  - a progress bar
  - «فشل الرفع» with «إعادة المحاولة», which resends the kept compressed blob
  - a thumbnail with «تغيير»
  - a `beforeunload` warning «يوجد رفع غير مكتمل» while an upload runs
  - after an upload, the returned `version` is applied to the autosave hook

**Checkpoint**: Both card sides upload, display from the private endpoint, and survive a reload.

---

## Phase 5: User Story 6 - House location on the satellite map (Priority: P2)

**Goal**: The pin is set by GPS or on a satellite map. The address and nearest landmark are typed. The form works with no map key.

**Independent Test**: Grant location, tap «استخدم موقعي الحالي», drag the pin, and reload on another device to see the dragged position. With no key, see «الخريطة غير متوفرة حالياً» while GPS still works.

- [ ] T034 [P] [US6] Write integration tests in `api/tests/integration/test_client_config.py`:
  - **Config:**
    - A signed-in user gets 200. With no key, `maps` is `null`. With a key, the response has `api_key`, `map_id` and `default_center`.
    - An anonymous caller gets 401.
  - **Location:**
    - A PATCH with `location` stores `drafts.location_lat`, `drafts.location_lng`, `drafts.location_source` and `drafts.location_accuracy_m`.
    - A value out of range gives 422.
    - `null` clears both coordinates.
- [ ] T035 [US6] Implement location and map support:
  - **API:** create `api/app/api/client_config.py` (`GET /client-config`, `current_user`) and register it in `api/app/main.py`.
  - **Config client:** create `web/src/lib/clientConfig.ts` as a cached query.
  - **Map loader:** create `web/src/lib/googleMaps.ts` (research.md R10).
    - It injects the official bootstrap loader once, then calls `importLibrary('maps')` and `importLibrary('marker')`.
    - It resolves to `unavailable` when there is no config, the script errors, or 10 s pass.
  - **CSP:** extend `web/Caddyfile` with the **full** list of sources in research.md R10 › CSP (analysis I1).
  - **Location UI:** build `web/src/pages/marketer/subscriber/LocationSection.tsx` and `MapPicker.tsx`, all wired to autosave. The pin saves immediately.
    - «استخدم موقعي الحالي» uses `navigator.geolocation` with high accuracy and a 15 s timeout. Denied, unavailable and timeout each get an Arabic message.
    - «حدّد البيت على الخريطة» opens a satellite map with a draggable `AdvancedMarkerElement`. Tapping the map moves the pin. The map centers on the pin, else the device position, else `default_center`.
    - «الخريطة غير متوفرة حالياً» shows when the map is unavailable.
    - The «العنوان» and «أقرب نقطة دالّة» fields are included.

**Checkpoint (end of batch 2)**: Text, images and location autosave and survive a reload on another browser.

---

## Phase 6: User Story 7 - Subscription choice with prices (Priority: P2)

**Goal**: The marketer picks area → tower of that area → plan, and sees both prices. The server copies the names and prices on every save, and reports unavailable choices and changed prices.

**Independent Test**: With «العلم», ALM01 and PLUS (20,000 / 35,000), pick them and see both prices. Change the area and see the tower cleared. Change the price as admin, reopen the draft, and see «تغيّر السعر».

- [ ] T036 [P] [US7] Write integration tests in `api/tests/integration/test_drafts_catalog_copies.py`:
  - **Copies:**
    - A PATCH with `area_id`, `tower_id` and `plan_id` stores the copies from the catalog.
    - A body with a price key gives 422.
  - **Clearing choices:**
    - A tower of another area is cleared with a `choice_unavailable` notice.
    - Changing the area clears the tower.
    - A deactivated tower or plan, or a tower of a deactivated area, is cleared on the next save, with a notice.
  - **Price changes:**
    - After an admin price change, GET returns `price_changed` with the old and new values and leaves the row unchanged.
    - The next PATCH refreshes the copies.
  - **Deleting items:**
    - Deleting an unused tower sets `drafts.tower_id` to null (SET NULL, research.md R2).
    - Drafts register no usage check.
  - **Bad ids:** an id that does not exist gives 422 `invalid_choice`.
- [ ] T037 [US7] Add `refresh_copies(db, draft) -> notices` (applied on every PUT and PATCH) and `compute_notices(db, draft)` (read-only, for GET) to `api/app/services/draft_service.py`, per research.md R4.
  - They write data-model.md › `drafts.area_name`, `drafts.tower_code`, `drafts.plan_name`, `drafts.trial_price` and `drafts.second_price`.
  - Each copy is null whenever its id is null (data-model.md › "Copies").
- [ ] T038 [US7] Build `web/src/pages/marketer/subscriber/SubscriptionSection.tsx`:
  - area, tower and plan selects from `/api/catalog` (`web/src/lib/settings.ts`); towers are filtered by area and cleared when the area changes
  - «لا توجد أبراج فعّالة» when the area has none
  - prices through `formatMoney`: «الشهر التجريبي: 20,000 د.ع — الشهر الثاني: 35,000 د.ع»
  - the notices «لم يعد متاحاً، اختر من جديد» and «تغيّر السعر»; opening a draft with notices sends an immediate save

---

## Phase 7: User Story 3 - Open the same draft from another device (Priority: P1)

**Goal**: The same draft opens on any device of the account. An outdated device or tab is told within 30 seconds and chooses which version to keep.

**Independent Test**: Fill the images, the card data, the location and the area/tower on context A. Open the draft on context B and see everything. Change the address on B and see the notice on A.

### Tests for User Story 3

- [ ] T039 [P] [US3] Write the Playwright test `e2e/tests/subscriber-form-acceptance.spec.ts` (quickstart A, B, D).
  - **Setup:**
    - two `browser.newContext()` sessions signed in as the same seeded marketer
    - synthetic JPEGs generated in the page with a canvas (text «بطاقة تجريبية»), 4000×3000 for the front, passed to `setInputFiles`
    - geolocation granted and mocked
    - the area, tower and plan seeded through the admin API
  - **Checks:**
    - Context 2 sees every value, the pin coordinates and both images (`img[src^="blob:"]` loaded).
    - After context 2 changes the address, context 1 shows «تغيّرت المسودة من جهاز آخر» within 30 s, and «تحميل الأحدث» shows the new address.
    - Two **pages in the same context** (one session) also get the notice (analysis U1).
    - The stored front image has `size_bytes` under 700 KB and a longest edge ≤ 1600 (SC-003, analysis G1).
    - Both image slots show «تصوير» and «من المعرض», and the gallery input has no `capture` attribute.

  Runs on `pixel-7`, `iphone-14` and `desktop-chrome` (FR-021, analysis G4).

### Implementation for User Story 3

- [ ] T040 [US3] Add version polling to `web/src/lib/useDraftAutosave.ts` (research.md R3):
  - It polls `GET /drafts/{id}/version` every 15 s while `document.visibilityState === 'visible'`, and also on `visibilitychange` and `focus`.
  - A newer version with `same_client=false` moves to state `conflict`.
  - A 404 moves to state `deleted`.
- [ ] T041 [US3] Build `web/src/pages/marketer/subscriber/ConflictBanner.tsx`. Autosave stays paused in both states (FR-017).
  - `conflict`: «تغيّرت المسودة من جهاز آخر», with two choices:
    - «تحميل الأحدث» runs a GET and replaces the form state.
    - «الإبقاء على نسختي» sends a PATCH with every local field and the server's current `version`.
  - `deleted`: «حُذفت هذه المسودة», with a link back to «الطلبات».

**Checkpoint**: The acceptance criterion (SC-001) passes in Playwright.

---

## Phase 8: User Story 4 - Drafts list and deleting a draft (Priority: P2)

**Goal**: «الطلبات ← مسودات» lists the marketer's own drafts with search. An unsubmitted draft can be deleted with its files and an audit entry.

**Independent Test**: Create two drafts and see them newest first, in the grey draft color. Search by name. Delete one after confirming, then check the audit entry and that the files are gone.

### Tests for User Story 4

- [ ] T042 [P] [US4] Write integration tests in `api/tests/integration/test_drafts_list_delete.py`:
  - **List:**
    - GET `/drafts` returns only the caller's drafts, ordered by `updated_at` DESC, with `missing_count` and `has_images`.
    - `q` matches a substring of the name and the phone digits.
  - **Delete:**
    - DELETE removes the `drafts` and `draft_images` rows and **both files from `UPLOADS_DIR`**.
    - It writes one `draft.deleted` audit entry. Its `before` has exactly the keys of data-model.md › "audit_log (existing)", and holds no name, national ID, family number, phone or file name.
  - **Other owners:** DELETE by another marketer gives 404 and removes nothing.
  - **Access log:** `image_access_log` rows survive the deletion.
  - **Orphan cleanup:** `python -m app.cli prune-uploads` removes an orphan file older than 1 hour, and keeps a fresh orphan and every referenced file.

### Implementation for User Story 4

- [ ] T043 [US4] Add `list_own(db, user, q)` and `delete(db, ctx, id)` to `api/app/services/draft_service.py`.
  - `delete` locks the row, collects the file names, deletes, audits `draft.deleted`, commits, then unlinks (research.md R8).
  - Add `GET /drafts` and `DELETE /drafts/{id}` to `api/app/api/drafts.py`.
  - Add the `prune-uploads` command to `api/app/cli.py`, using `image_store`.
- [ ] T044 [P] [US4] Add the action label `draft.deleted` → «حذف مسودة» and its target label to `web/src/lib/labels.ts` and `web/src/lib/auditFormat.ts`, with a case in `web/src/__tests__/audit-format.test.ts`.
- [ ] T045 [US4] Replace the `MarketerRequests` placeholder with `web/src/pages/marketer/Requests.tsx`, and update `web/src/router.tsx` and `web/src/pages/marketer/placeholders.tsx` (research.md R11):
  - the tabs بالانتظار / مقبولة / تم الربط / مرفوضة / مسودات, with `?tab=` kept in the URL
  - the other tabs show «لا توجد طلبات بعد»
  - the page opens on «مسودات» when drafts exist and no requests do
- [ ] T046 [US4] Build the drafts tab in `web/src/pages/marketer/DraftsTab.tsx`:
  - a search box
  - one card per draft: the name or «بدون اسم», the tower code, the last save in Baghdad time (`lib/time.ts`), «ناقص N», and the grey «مسودة» chip (§7.2)
  - tapping a card opens `/drafts/{id}`
  - «حذف» behind `ConfirmDialog` «حذف المسودة نهائياً؟»

**Checkpoint**: Drafts are reachable from any device through the list, and deleting one removes everything.

---

## Phase 9: User Story 5 - Field validation and missing-items summary (Priority: P2)

**Goal**: Inline Arabic field errors, the «النواقص» summary with links, and a disabled «إرسال».

**Independent Test**: Enter an 11-digit national ID and the phone «+964 780 123 4567». See the ID error and the phone accepted as 07801234567. See every empty field listed, and «إرسال» disabled.

- [ ] T047 [P] [US5] Add integration tests to `api/tests/integration/test_drafts_autosave.py`:
  - GET returns `missing` in page order for an empty draft.
  - After filling every field and both images, `missing` is empty.
  - Invalid values are still saved (US5 scenario 6).
- [ ] T048 [US5] Build `web/src/pages/marketer/subscriber/PhoneSection.tsx`, wired to autosave:
  - the subscriber phone, LTR with a tel keyboard
  - the normalized value shown under the field («سيُحفظ كـ 07801234567»)
- [ ] T049 [US5] Build `web/src/pages/marketer/subscriber/MissingSummary.tsx`:
  - It uses `draftValidation.ts` locally, then the server `missing` after each save, which is authoritative.
  - Each item is a link that scrolls to and focuses its field.
  - With nothing missing, it shows «كل الحقول مكتملة».
  - It ends with the disabled «إرسال» and «الإرسال يتفعّل بعد إضافة التحقق من الهاتف» (FR-014).

  `CardDataSection.tsx` and `PhoneSection.tsx` show inline field errors on blur.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T050 [P] Extend `api/tests/integration/test_log_safety.py` (FR-022, Principle II): errors raised while saving a draft or uploading an image write no national ID, family number, phone or file name to the app logs.
- [ ] T051 [P] Extend the Playwright file `e2e/tests/subscriber-form-acceptance.spec.ts` with quickstart E, F, I and J:
  - E: the national ID and phone errors, and the summary
  - F: «إرسال» stays disabled
  - I: another marketer opening the URL sees «المسودة غير موجودة»
  - J: with no map key, «الخريطة غير متوفرة حالياً» shows and GPS still sets the pin
- [ ] T052 [P] Document the uploads volume, the proxy limit and the Maps key:
  - **`docker-compose.staging.yml`:** a comment that the `uploads` volume (`sijil_uploads`) holds the card images and is kept on the server.
  - **`deploy/staging.md`:**
    - The `sijil_uploads` volume must be in every backup. Give a manual `docker run --rm -v sijil_uploads:/data … tar` command and the restore command, and note that the nightly job comes in 015 (analysis N1).
    - Nginx Proxy Manager › Proxy Host › Advanced: `client_max_body_size 6m;`
    - Google Cloud console: restrict the Maps key to the HTTP referrer `https://sijil.t3cftth.net/*` and to the Maps JavaScript API, and create the Map ID.
- [ ] T053 [P] Add 005 to the feature table in `README.md`.
- [ ] T054 Check the volume and the map:
  - The `api` container can write to `/data/uploads`.
  - `scripts/e2e.sh` removes the e2e `uploads` volume with `down -v`: no `sijil-e2e_uploads` volume is left after a run (analysis A1).
  - With a real key on staging, the satellite map and the draggable pin load with **no CSP errors** in the browser console (analysis I1).
- [ ] T055 On a phone viewport, and on a real Android phone if possible, check that «تصوير» opens the camera and «من المعرض» opens the gallery.
- [ ] T056 Close the feature:
  - Run `scripts/test-all.sh` and fix any failure.
  - Run `docker compose up -d --build`.
  - Write the Arabic manual-test steps to `specs/005-subscriber-form/manual-test-ar.md`, covering quickstart A–J, the two-phone acceptance, the two-tab notice and the map-key setup.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: none. T002–T004 can run in parallel after T001.
- **Foundational (Phase 2)**: needs Setup, and blocks every story.
  - T005 → T006 → T013.
  - T008 and T009 → T010 → T013.
  - T007 and T012 → T013 → T014.
  - T011, T015 and T016 run in parallel with the api chain.
- **US1 (Phase 3)**: needs Foundational. This is the MVP.
- **US2 (Phase 4)**: needs Foundational. T033 needs T021, because the upload applies `version` to the autosave hook.
- **US6 (Phase 5)** and **US7 (Phase 6)**: need US1's autosave hook (T021). They are independent of each other.
- **US3 (Phase 7)**: needs US1, US2, US6 and US7, because the acceptance test fills all of them.
- **US4 (Phase 8)**: needs Foundational and US2's `image_store` (T028) for file deletion.
- **US5 (Phase 9)**: needs US1.
- **Polish (Phase 10)**: after every story. T056 comes last.

**Within each story**: tests first (they must fail), then the service, then the routes, then the UI. Every story edits `draft_service.py` and `api/drafts.py`, so edit those files one task at a time, not in parallel.

### Parallel Opportunities

- Setup: T002, T003 and T004.
- Foundational: T007, T008, T009, T011, T012, T015 and T016, alongside the migration and model chain.
- US1: T017, T018 and T022.
- US2: T026, T027 and T031.
- The test tasks of the later stories (T034, T036, T042, T047) are in different files and can be written together.

## Parallel Example: User Story 2

```bash
Task: "T026 Integration tests in api/tests/integration/test_draft_images.py"
Task: "T027 Vitest in web/src/__tests__/imageCompress.test.ts"
Task: "T031 web/src/lib/imageCompress.ts"
# then T028 → T029 → T030 (api), T032 → T033 (web)
```

---

## Implementation Strategy

### MVP (acceptance criterion)

1. Batch 1: Phases 1–2.
2. Batch 2: US1 (autosave), US2 (images), US6 (location).
3. Batch 3: US7 (subscription), then US3 (second device and conflict). The acceptance test T039 must pass here; stop and validate.

### Incremental delivery

4. US4 (the drafts list and deletion), then US5 (the summary and the validation UI).
5. Polish: log safety, the remaining e2e scenarios, the staging docs, README, the full test gate, `docker compose up`, and the Arabic manual steps.
