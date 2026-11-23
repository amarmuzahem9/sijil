# Research: Request Check and Decision at Submission (008)

The owner settled three questions on 2026-11-23 (spec › Clarifications, `docs/system.md` v1.9):
1. Rejected requests do not count as existing.
2. A row 1 or row 2 match at submission refuses the submission and keeps the draft.
3. A number typed by hand counts as an edit.

The decisions below fill in the rest. No item is left open.

## R1. A separate `requests` table; the draft is removed on submission

- **Decision**: New table `requests`, as 005 R1 decided.
  - Submission copies the draft's values into a new row.
  - The image rows move to `request_images`. The files stay where they are, under the same names.
  - The card readings (`raw` and `result` for each side) are copied into `requests.card_readings`.
  - Then the draft row is deleted. Its `draft_images` and `card_readings` rows go with it by cascade.
  - No `draft.deleted` audit entry is written, because this is a submission, not a deletion.
- **`requests.draft_id`**: a unique uuid with no foreign key. It keeps the draft's id, so a repeated
  submit finds the request it already made (R6).
- **Images**: `draft_service.referenced_file_names` also returns `request_images.file_name`, so the
  orphan sweep never deletes a request's file. Request images get no viewer in 008: no 008 screen
  shows them. The permission-checked route comes with the first screen that does (010).
- **OTP rows**: `otp_challenges.request_id` points to `drafts`, `ON DELETE SET NULL`. The rows stay
  and keep counting toward the hourly limit (007), as they already do when a draft is deleted.
- **Rationale**: Request columns can then be NOT NULL and CHECKed, which a draft can never be. The
  owner already chose separate tables in 005.
- **Alternatives**: Widening `drafts.status` and keeping one row, as a remark in 007 data-model
  suggested. Rejected: every NOT NULL rule would need a draft exception, and 005 R1 already ruled it out.

## R2. The check engine and its sources

- **Decision**: `services/match_service.py` exposes
  `find_matches(db, *, phone, national_id, family_key, exclude=None) -> Matches`.
  - `Matches` holds three lists of `MatchRef(source, ref_id)`: phone, national ID and family.
  - It asks each registered source. This is the same pattern as the 004 usage registry.
- **Sources in 008**: one, `sijil`. It looks in `requests` where
  `status IN ('pending_review','approved','linked')`.
  - Rejected requests are skipped (Q1).
  - Drafts are not a source (FR-005).
- **Later sources**: 013 registers `legacy` and 014 registers `sas`.
  - A missing value never matches. Legacy rows have no national ID; SAS rows may have no phone.
  - The engine does not change when they arrive.
- **Decision rules** live in `core/decision.py`, as a pure function `decide(matches, edited,
  additional_confirmed) -> Decision`:
  - Row 1 (phone) → `refuse: phone_used`.
  - Row 2 (national ID) → `refuse: national_id_exists`.
  - Rows 3 and 4 add up:
    - row 3 → reason `family_exists`, and type `additional`;
    - row 4 → reason `numbers_edited`.
  - No reason → `approved`.
  - Any reason → `pending_review`.
  - Row 3 without the marketer's confirmation is a missing item, so it never reaches `decide`.
- **Rationale**: The rules are a pure function. Each row and each combination gets a short pytest
  case (Principle VIII).

## R3. Comparison keys (§6.2)

- **Phone**: `core/phone.normalize_phone`, already in place. `requests.phone` holds the normalized value.
- **National ID**: `core/national_id.normalize_national_id`, already in place. Only 12-digit values
  are stored.
- **Family key**: new `core/family_key.family_key(text)`:
  - convert Arabic and Indic digits;
  - uppercase;
  - keep only `[A-Z0-9]`;
  - replace every `O` with `0`.
- **Why a new function**: the 006 `normalize_family_number` is not used for comparison. It keeps `O`
  at the series position and rejects odd shapes. Legacy data has odd lengths (§12.1), and §6.2 says
  O is treated as 0 everywhere.
- **Storage**: `requests.family_key` is stored and indexed. The family number itself is stored as written.
- **Tests**: a shared fixture `family_key_cases.json`.

## R4. "Numbers edited" (row 4, FR-005a)

For each of `national_id` and `family_number`, the server compares the final value with the card's
values, using the R3 keys:
- **Card values**:
  - `card_fields[field].original`;
  - for the national ID, also `national_id_check.mrz` (a verified MRZ only).
- **Not edited**: the final value equals one of the card values.
- **Edited**:
  - it equals none of them;
  - or there is no card value at all: the field was typed by hand, or the reading failed (Q3).
- **Effect**: if the card reader is down, every request goes to review with reason
  `numbers_edited`. This follows from Q3 and is what the owner chose. The pending reason records
  which field: `{"fields": ["family_number"]}`.
- **Names**: names are never part of this check (§6.1 note 2).

## R5. Early warnings come with every draft response

- **Decision**: every `DraftOut` (GET, PUT, PATCH, image upload, OTP calls) carries
  `checks: {phone_used, national_id_exists, family_exists, additional_confirmed}`, computed by
  `find_matches`. The flags drive missing items, which are added after the 005 pure list in page order:

  | Missing item | When | Arabic |
  |---|---|---|
  | `national_id_exists` | after `national_id` | المشترك لديه اشتراك سابق |
  | `family_exists_unconfirmed` | after `family_number` | لهذه العائلة اشتراك سابق — اختر «طلب اشتراك إضافي» |
  | `phone_used` | after `phone` | المشترك موجود سابقاً، هل يود العودة للخدمة؟ |

- **Cost**: three indexed equality lookups per response. Autosave is debounced, so this is cheap.
- **Display**: the page shows each message under its field and in `MissingSummary`. Only booleans
  reach the page; no ids, names or towers (FR-007, SC-006).
- **Probing**: the early check tells a marketer whether a phone, national ID or family number
  exists. §6 asks for exactly this, so no extra limit is added (spec Assumptions). Every call is
  already tied to a signed-in marketer.
- **Client mirror**: `draftValidation.ts` does not compute these items. It shows the server's.

## R6. Submission: one transaction, idempotent

`POST /api/drafts/{id}/submit` with body `{version}`.
1. **Already submitted?** If a request with `draft_id = id` and the caller as marketer exists, return
   it with 200 and stop. This covers a double tap and a network retry (FR-013). A request of another
   marketer gives 404.
2. **Load and check the draft**:
   - load the draft `FOR UPDATE`;
   - its owner must be an active marketer;
   - `version` must equal the stored version, else 409 `draft_conflict`. The page saves pending
     changes first, so the server checks what the marketer sees.
3. **Refresh the copies**: `refresh_copies`. If a choice is no longer available, return 409
   `catalog_changed` and save the cleared choice, as 005 does.
4. **Missing items**: if `missing` is not empty, return 422 `draft_incomplete` with the list. This
   includes the expired card, the unconfirmed national ID, and the unconfirmed family.
5. **Verification**: `otp_verified_at` is set and `otp_context_hash = context_hash(draft)`, else 409
   `otp_needs_reverify` («يحتاج تحقق جديد»).
6. **Locks**: take `pg_advisory_xact_lock` on `match:phone:<p>`, `match:nid:<n>` and
   `match:family:<k>`, in that fixed order (no deadlock). Then run `find_matches` again.
7. **Decide**:
   - Row 1 → 409 `phone_used`.
   - Row 2 → 409 `national_id_exists`.
   - On a refusal: roll back everything, write the audit entry `request.submit_refused` in a new
     transaction, and keep the draft (Q2).
   - Otherwise: `nextval('request_number_seq')`, insert the request and its reasons, move the image
     rows, copy the readings, delete the draft, audit `request.submitted`, commit.
8. **Response**: 201 with `RequestOut`.
- **Why locks and no unique index**: in 009 a «إعادة للخدمة» request may reuse the old phone and the
  same national ID while the old request is still approved or linked. A unique index would block it.
  The advisory locks serialize the check and the insert for the same key, and that is enough
  (SC-004).

## R7. Request number and username

- **Number**: PostgreSQL sequence `request_number_seq START 1001`.
  - It is stored as an integer in `requests.number` (unique).
  - It is shown as `T3C-1001` (§7.3).
  - A number taken by a rolled-back transaction is simply skipped. Refusals in step 7 happen before
    `nextval`, so in practice there are no gaps.
- **Legacy numbers**: T3C-001 to T3C-109 go in a separate field in 013, not here.
- **Username**: `f"{tower_code}-{phone}"` (§8.2). It is stored at submission and is not unique in
  the database, because a «إعادة للخدمة» request (009) keeps the old username. It is shown to the
  marketer only when the request is approved.

## R8. Values fixed at submission (Principle IV)

The request stores copies of:
- all form fields;
- `full_name`;
- `no_surname`;
- `card_fields`;
- `national_id_check`;
- the card readings;
- the five back fields;
- the location, its source and its accuracy;
- the address and the landmark;
- `area_name`, `tower_code`, `plan_name`, `trial_price` and `second_price`, after the refresh in R6
  step 3;
- the verified phone;
- `otp_verified_at`.

It also stores its own facts: `submitted_at`, plus `approved_at`, which is set for an automatic
approval (`approved_by` null = automatic). Later features add their own facts: rejection (010),
linking (012).

## R9. Status transitions and the catalog usage registry

- **Status**: `requests.status` has a CHECK on the five §7.2 values. 008 writes only `approved` and
  `pending_review` (FR-016). There is no `draft` value on a request; a draft is a separate table.
- **Type**: `requests.type` has a CHECK on `new`, `additional` and `return`. 008 writes `new` and
  `additional`.
- **Usage registry**: 008 registers usage checks for `area`, `tower` and `plan`, so a used item can no
  longer be deleted (004). The check counts requests of any status.

## R10. The 007 check point

- **Decision**: `phone_checks.precheck_for_otp` calls `find_matches(phone=...)`.
  - When the phone matches, it returns `AppError("phone_used", 409)`.
  - It runs before the locks and the limits, so nothing is counted (FR-006).
  - The 007 test that monkeypatches the function stays as it is. A new integration test uses real data.

## R11. Marketer screens

- **«إرسال»**: lives in `MissingSummary`. It is enabled when `missing` is empty and `otp.status ==
  "verified"`.
- **Before submitting**: the page flushes autosave, then submits with the current `version`.
- **Refusals**: `phone_used` and `national_id_exists` show the message on the form. The server's
  next draft response shows the same item.
- **Result page**: `/requests/:id` (`RequestResult.tsx`):
  - approved: «تمت الموافقة», `#T3C-1001` and the username, with «نسخ اليوزر»;
  - pending with `family_exists`: «بانتظار موافقة المسؤول»;
  - other pending: «طلبك بانتظار التدقيق».
- **Family confirmation**: `FamilyMatchNotice.tsx`, under the family number:
  - the message «لهذه العائلة اشتراك سابق»;
  - a «طلب اشتراك إضافي» button. Pressing it PATCHes `additional_confirmed_key`.
- **«الطلبات» page**:
  - «بالانتظار» and «مقبولة» list the marketer's requests (number, name, date, status color),
    opening the result page;
  - «تم الربط» and «مرفوضة» stay empty until 012 and 010;
  - search is 011;
  - the page opens on «بالانتظار» when there are requests.

## R12. The «طلب اشتراك إضافي» confirmation

- **Decision**: a draft column `additional_confirmed_key text null`.
  - The PATCH field `additional_confirmed: true` stores the current family key, and is refused
    unless a family match exists.
  - `false` clears it.
  - The confirmation is valid only while `additional_confirmed_key = family_key(draft.family_number)`
    and the match still exists.
  - Changing the family number therefore drops the confirmation with no extra code (FR-010).

## R13. Audit and logs

- **`request.submitted`**:
  - `entity_type = "request"`, `entity_id = number`;
  - `after = {number, type, status, reasons, tower_code, plan_name}`.
- **`request.submit_refused`**:
  - `entity_type = "draft"`, `entity_id = draft id`;
  - `after = {reason}`.
- **Never in an audit entry**: the national ID, the family number, the phone, names or images. The
  number is enough to find the request.
- **App log line**: `submit draft=<id> result=<approved|pending|phone_used|...> number=<n>`, with no
  card data and no full phone. `test_log_safety` is extended with a submission.
- **Arabic labels**: the two actions get labels in `labels.ts` for the 002 audit viewer.

## R14. Tests

- **Unit**:
  - `test_decision.py`: every row, the 3+4 combination, the order (1 beats 3, 2 beats 4);
  - `test_family_key.py`, using the shared fixture;
  - `test_numbers_edited.py`: equal to front, equal to MRZ, different, typed by hand.
- **Integration**:
  - `test_submit.py`: a clean approval, each refusal, incomplete, needs reverify, catalog changed,
    version conflict, idempotent retry, another marketer gets 404, the draft is gone and the images
    are kept, the copies are fixed after a price change;
  - `test_match_sources.py`: different written forms, rejected requests are ignored, drafts are
    ignored;
  - `test_submit_concurrency.py`: 20 threads, same phone, exactly one wins;
  - `test_otp.py` extended with the real «الهاتف مستخدم» precheck;
  - `test_log_safety` and `test_audit_completeness` extended.
- **Vitest**: `MissingSummary` enables «إرسال»; `RequestResult` shows the three states;
  `FamilyMatchNotice`.
- **Playwright**: `submit.spec.ts`:
  - a clean draft goes to «تمت الموافقة» with the username;
  - a second draft with the same phone gets the message on «تحقّق».
