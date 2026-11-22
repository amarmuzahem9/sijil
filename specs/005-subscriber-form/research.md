# Research: New Subscriber Form (005)

The owner fixed the tables, the autosave protocol (partial PATCH, `version`, 409), browser
compression, the private `uploads` volume with UUID names, the permission-checked image endpoint,
deletion with files, the satellite map, catalog reconciliation, and the tests in the
`/speckit-plan` input. The decisions below fill in the rest.

## R1. Drafts live in their own table

- **Decision**: Add the owner's two tables, `drafts` and `draft_images`. Drafts are not rows of a
  future `requests` table. Feature 008 turns a complete draft into a request: it copies the
  values and moves the images, then marks or removes the draft.
- **Primary key**: a UUID that the browser generates on the first real change. It is sent with
  `PUT /api/drafts/{id}` (create-if-absent), so a retried create never makes two drafts (US1
  scenario 4). The id is also unguessable in URLs.
- **Rationale**: A draft may hold invalid and incomplete values. Requests must be complete and
  carry a request number (FR-020). One table for both would loosen every request constraint.
- **Alternatives**: A `requests` row with `status='draft'` was rejected. Every NOT NULL, CHECK
  and number rule would need a draft exception, and the owner named a separate table.

## R2. Settings foreign keys use `ON DELETE SET NULL`

- **Decision**: `drafts.area_id`, `tower_id` and `plan_id` reference the 004 tables with
  `ON DELETE SET NULL`. No usage check is registered for drafts.
- **Rationale**: 004 defines "used" as referenced by a request or a subscriber. A draft is
  neither (system.md §5 v1.4). If an admin deletes an unused tower, the draft simply loses the
  choice, the same way a deactivated choice is cleared (R6).

## R3. Autosave protocol and concurrent edits

- **Save**: `PATCH /api/drafts/{id}` with `{version, changes}`.
  - `changes` is a partial object: an omitted key is unchanged, and `null` clears the field.
  - The server runs one statement: `UPDATE … SET …, version = version + 1 WHERE id = :id AND
    marketer_id = :me AND version = :v RETURNING …`.
  - When no row matches but the draft exists, the server returns 409 `draft_conflict` with the
    current `version`, `updated_at`, and `same_session`.
- **Same-session conflicts are not real conflicts**: Each save stores the session id that made
  it (`last_session_id`, from `AuthContext.session`). An image upload also increases the version.
  When the conflicting save came from the same session (for example, an upload that finished
  during typing), the response has `same_session: true`. The client then takes the new version
  and sends its pending changes again without showing anything.
- **Different session**: Autosave pauses and the banner «تغيّرت المسودة من جهاز آخر» appears
  (FR-017).
  - «تحميل الأحدث» runs a GET and replaces the screen with the server's version.
  - «الإبقاء على نسختي» sends every field of the local form with the current server version.
    That save becomes the latest one, and the other device then gets the notice.
- **Detection within 30 seconds (SC-004)**: While the form is visible, the client polls
  `GET /api/drafts/{id}/version` every 15 seconds. It also polls when the tab becomes visible
  again or the window regains focus. The response is tiny: `{version, updated_at, same_session}`.
  A 404 there means the draft was deleted, and the client shows «حُذفت هذه المسودة» (US4
  scenario 5).
- **Debounce**: Text fields are saved about 1 second after the last keystroke, and immediately on
  blur (owner input). Selects, the pin and the location button save immediately. The client keeps
  one save queue per draft: one PATCH is in flight at a time, and changes made during it are
  merged into the next one.
- **Offline**: On a network error the status shows «غير متصل». The client retries with backoff
  (2, 4, 8 … up to 30 seconds) and on the browser's `online` event. Unsaved values stay in memory
  on screen. Nothing is written to localStorage, because card data must never be stored on the
  device (Principle II).
- **Alternatives**:
  - Field-level merging was rejected. The owner chose "last save wins", and merging hides
    surprises (Principle VI).
  - WebSockets or SSE were rejected. Polling every 15 seconds meets the 30-second target with no
    new infrastructure.

## R4. Prices and names are copied on the server

- **Decision**: The client sends only `area_id`, `tower_id` and `plan_id`. On every save that
  touches the subscription (and on every save, to catch admin changes), the server:
  - checks each chosen item is still active, its area is active, and the tower belongs to the
    area;
  - writes the copies `area_name`, `tower_code`, `plan_name`, `trial_price` and `second_price`
    from the current catalog (FR-011).
- **Inactive or mismatched choices**: An inactive item, or a tower outside the chosen area, is
  cleared along with the items that depend on it (area → tower). The response includes
  `notices`, for example `[{field: "tower_id", code: "choice_unavailable"}]`.
- **Reopening a draft**: `GET` compares the stored copies with the current catalog without
  changing anything. It returns `notices` with `choice_unavailable` or `price_changed`, carrying
  the old and new prices. The client shows «لم يعد متاحاً، اختر من جديد» or «تغيّر السعر» and
  sends an immediate save, which refreshes the copies (US7 scenario 5).
- **Rationale**: The server is the authority for prices (Principle IV). A client could never
  write a wrong price. This refines 004 research R4: "copies at each draft save, final at
  submission" (spec Clarifications, system.md §5 v1.4).

## R5. Image compression in the browser

- **Decision**: `web/src/lib/imageCompress.ts`:
  1. Decode with `createImageBitmap(file, {imageOrientation: 'from-image'})`, which corrects the
     EXIF rotation. If that fails (an older Safari), fall back to an `HTMLImageElement`, where
     modern browsers apply EXIF orientation by default.
  2. Scale so the longest edge is at most 1600px. Smaller images are never upscaled.
  3. Draw on a canvas and encode with `canvas.toBlob(…, 'image/jpeg', 0.8)`.
- **Side benefits**: Re-encoding strips all EXIF data, including the GPS position and the device
  model. iPhone HEIC photos picked in Safari decode natively and come out as JPEG.
- **Testing**: The target-size maths (`fitWithin(w, h, 1600)`) is a pure function and is tested
  with Vitest. The canvas step is tested with a mocked canvas in jsdom. The real encoding is
  covered by Playwright.
- **Inputs (owner requirement)**: Each slot MUST show two separate buttons, «تصوير» and «من
  المعرض». Each button has its own hidden input:
  - «تصوير»: `<input type=file accept="image/*" capture="environment">`
  - «من المعرض»: `<input type=file accept="image/*">`, with no `capture` attribute
  One input carrying `capture` is not enough, because on Android it opens the camera directly
  and hides the gallery. Playwright asserts that both buttons exist in both slots, and that the
  gallery input has no `capture` attribute.

## R6. Upload with progress and retry

- **Decision**: `POST /api/drafts/{id}/images/{side}` with `multipart/form-data` and one field,
  `file`. The upload uses `XMLHttpRequest`, because `fetch` has no upload progress events.
  - The slot keeps the compressed `Blob` in memory until the upload succeeds, so «إعادة المحاولة»
    resends the same bytes (FR-006).
  - A 401 `token_expired` refreshes the token once and retries automatically, the same as
    `lib/api.ts` does.
  - Leaving the page during an upload triggers a `beforeunload` warning.
- **Server checks**, in order:
  1. owner check
  2. the size, from the streamed read capped at 5 MB, giving 413 `image_too_large`
  3. the JPEG magic bytes `FF D8 FF`, otherwise 422 `invalid_image`
  4. Pillow `verify()`, then a reload to read the dimensions; a longest edge above 1600px gives
     422 `image_too_big_dimensions`
  5. write to a temporary file in the uploads directory, `fsync`, then `os.replace` to
     `<uuid>.jpg`
  6. upsert the `draft_images` row for that side and increase the draft `version`
  7. commit, then remove the replaced file, if any
- **New dependencies**:
  - `python-multipart`, which FastAPI needs for `UploadFile`.
  - `Pillow`, to verify the image and read its dimensions; feature 006 (OCR) will also use it.
  Both are justified under Principle VII, which fixes the frameworks but not the helper
  libraries.
- **Proxy limits**:
  - Caddy (web and local proxy) has no default body limit. The API enforces 5 MB itself.
  - Nginx Proxy Manager on the server defaults to `client_max_body_size 1m`. Compressed photos
    are usually under 1 MB, but not always. `deploy/staging.md` gets a step to add
    `client_max_body_size 6m;` under the Proxy Host's Advanced tab.

## R7. Private storage, serving and access log

- **Volume**:
  - The compose volume key is `uploads`, mounted at `/data/uploads` in `api` only; the web
    container never sees it. It is set by `UPLOADS_DIR`, default `/data/uploads`.
  - Under the project name `sijil`, Docker names it `sijil_uploads`, like the existing
    `sijil_pgdata`.
  - The owner wrote "sijil-uploads". The underscore form is kept, because a fixed `name:` would
    make the e2e project (`sijil-e2e`) share and then delete (`down -v`) the same volume.
  - The Dockerfile creates `/data/uploads` owned by `app` (uid 10001), so a new named volume
    inherits that owner.
- **File names**: `<uuid4>.jpg`, in a flat directory. The database keeps only the relative file
  name and never a user-supplied name.
- **Serving**: `GET /api/draft-images/{image_id}`.
  - Allowed: the owner marketer, the main admin, and admins holding `review` (FR-002, via
    `has_any_permission`). Everyone else gets 404, so a draft's existence is never revealed to
    another marketer.
  - Response headers: `Content-Type: image/jpeg`, `Cache-Control: private, no-store`,
    `Content-Disposition: inline`, `X-Content-Type-Options: nosniff`.
  - The `<img>` cannot send the in-memory bearer token. The client therefore fetches the image
    as a blob with `Authorization` and shows it through `URL.createObjectURL`. CSP already allows
    `img-src blob:`. The service worker never caches `/api/*` (existing rule).
- **Access log**: Every successful open writes a row to `image_access_log` (user, image, draft,
  time). That covers the owner as well, not only admins: the owner's input says "every admin
  open", and Principle II and §13 say "every access". Logging all of them satisfies both.
  - The log is kept out of `audit_log`, so the audit viewer is not flooded by form reloads.
  - No viewer page is added in this feature; the admin requests pages (010) will show it.
- **Backups**: This feature adds no backup job; that is feature 015. `deploy/staging.md`
  documents that the `sijil_uploads` volume holds the card images, must be part of every backup,
  and gives a manual `tar` command for it.

## R8. Deleting a draft removes rows and files

- **Decision**: `DELETE /api/drafts/{id}` runs in one request:
  1. lock the draft row (owner only)
  2. collect its image file names
  3. delete the `draft_images` and `drafts` rows (`ON DELETE CASCADE` from images to drafts)
  4. write the audit entry `draft.deleted`
  5. commit, then unlink the files
- **Why files go after the commit**: If the commit fails, the files are still there. If an unlink
  fails after the commit, the orphan file is logged by name only.
- **Orphan cleanup**: `python -m app.cli prune-uploads` removes files that no row refers to and
  that are older than 1 hour. It covers crashes between the commit and the unlink, and uploads
  that were abandoned mid-write.
- **Image access log rows**: They keep `image_id` and `draft_id` as plain values, not foreign
  keys, so the access history survives the deletion (Principle III).
- **Audit entry**: `entity_type="draft"`, `entity_id=<uuid>`.
  - `before` holds `{created_at, updated_at, tower_code, image_count, missing_count}`.
  - It never holds the name, the national ID, the family number, the phone or file names
    (FR-019, Principle II).

## R9. Validation shared by server and client

- **Server**: `app/services/draft_validation.py` computes `missing: [{field, code}]` for every
  draft response (FR-013).
  - The codes are `required`, `invalid_national_id`, `invalid_phone` and `too_long`.
  - The field order matches the page order, so the summary reads top to bottom.
- **National ID** (`app/core/national_id.py`): convert Arabic-Indic digits, remove spaces and
  direction marks, then require `^\d{12}$`. The draft stores the text as typed. The normalized
  value is used for validation and, in 008, for comparison.
- **Phone**: `app/core/phone.py` (§8.1, existing). The draft stores `phone_input` as typed and
  `phone_normalized` when it is valid, which the drafts search uses.
- **Client mirror**: `web/src/lib/draftValidation.ts` gives instant feedback.
  - Both sides run the same cases from a shared fixture,
    `api/tests/fixtures/draft_validation_cases.json`, copied to
    `web/src/__tests__/fixtures/`. This follows the existing `phone_cases.json` pattern.
  - The server result is authoritative.
- **Lengths**: name 100, address 300, landmark 200, family number 30, phone input 30, national ID
  input 30.

## R10. Map configuration at runtime

- **Decision**: The key reaches the browser from the server at runtime, not at build time.
  - New environment variables:
    - `GOOGLE_MAPS_API_KEY`
    - `GOOGLE_MAPS_MAP_ID`, needed by `AdvancedMarkerElement` with `gmpDraggable`
    - `MAP_DEFAULT_CENTER`, as `lat,lng`, used when there is no pin and no position
  - `GET /api/client-config` returns `{maps: {api_key, map_id, default_center} | null}` to any
    signed-in user.
- **Rationale**: The owner allowed either option. One web image serves local, e2e, staging and
  production with only `.env` differing. The key never appears in the repository or the build
  output. A Maps JavaScript key is visible to the browser by nature, which is why the owner
  restricts it by HTTP referrer (`https://sijil.t3cftth.net/*`) and to the Maps JavaScript API
  only, in the Google Cloud console. `deploy/staging.md` documents that step.
- **Loading**:
  - `web/src/lib/googleMaps.ts` injects the official bootstrap script once, then calls
    `importLibrary('maps')` and `importLibrary('marker')`. It adds no npm package.
  - The map uses `mapTypeId: 'satellite'`. Tapping the map moves the pin, and dragging the pin
    saves its position.
  - With no key, the script failing, or no network, the section shows «الخريطة غير متوفرة
    حالياً». «استخدم موقعي الحالي» (`navigator.geolocation`, high accuracy, 15-second timeout)
    still sets the pin coordinates (FR-009).
- **CSP**: `web/Caddyfile` allows Google's documented hosts:
  - `script-src`: `https://maps.googleapis.com`
  - `img-src`: `https://*.googleapis.com`, `https://*.gstatic.com`, `https://*.google.com`,
    `data:`, `blob:`
  - `connect-src`: `https://*.googleapis.com`, `https://*.google.com`
  - `font-src`: `https://fonts.gstatic.com`
  - `worker-src`: `blob:`
  - `style-src` already allows `'unsafe-inline'`.
  - `Permissions-Policy` already allows `camera=(self), geolocation=(self)`.
- **e2e**: There is no key in e2e. Playwright checks the «الخريطة غير متوفرة حالياً» path and
  sets the pin through a granted, mocked geolocation.

## R11. Pages and routes (marketer)

- `/` (dashboard): «إضافة مشترك جديد» goes to `/drafts/new`.
- `/drafts/new`: an empty form. The UUID is generated and the URL becomes `/drafts/{id}` on the
  first real change, using `replace`.
- `/drafts/:id`: opens an existing draft. If the draft is not found or belongs to someone else,
  the page shows «المسودة غير موجودة».
- `/requests`: tabs بالانتظار / مقبولة / تم الربط / مرفوضة / مسودات. Only «مسودات» has content;
  the others show «لا توجد طلبات بعد». The page opens on «مسودات» when drafts exist and no
  requests do. The tab is kept in the URL (`?tab=drafts`).
- **Save badge**: «محفوظ», «جارٍ الحفظ…», «غير متصل — سيُعاد الحفظ تلقائياً», or «لم يُحفظ —
  إعادة المحاولة» after 3 failed attempts. It is sticky at the top of the form.
- **Send button**: It is shown disabled, with «الإرسال يتفعّل بعد إضافة التحقق من الهاتف»
  (FR-014). The «النواقص» summary sits above it.
