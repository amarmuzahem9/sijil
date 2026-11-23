# Research: Existing Subscriber Paths (009)

Inputs: [spec.md](./spec.md) with the 2026-11-23 clarifications, `docs/system.md` v1.10 §3.1, §6.1,
§6.3, §10 item 6, and the 008 code (`core/decision.py`, `core/matches.py`,
`services/match_service.py`, `services/submit_service.py`, `services/phone_checks.py`).

## R1. Matches per record, not per key

**Problem**: 008's `Matches` holds three separate lists (phone, national_id, family) of `MatchRef`.
Rule 1 needs to know that the national ID **and** the family number match the **same** record, and
rule 2b needs "national ID matches, family number differs or is missing on that record". The lists
cannot answer either question.

**Decision**: sources return one `MatchRecord` per matching record:
`source`, `ref_id`, `phone: bool`, `national_id: bool`, `family: bool`, `pending: bool`
(the record is a request still in `pending_review`). `Matches` becomes a list of records with derived
views:

| View | Records |
|---|---|
| `phone` | `phone` |
| `same_person` | `national_id and family` |
| `id_conflict` | `national_id and not family` (covers a record with no family number) |
| `family` | `family and not national_id` (covers a legacy record with no national ID) |

The old `.phone`, `.national_id` and `.family` properties stay, so 008 callers keep working while
they move to the views. The sijil source asks for the three keys in one query per draft
(`WHERE phone = :p OR national_id = :n OR family_key = :f`, active statuses) and sets the flags by
comparing columns. 013 and 014 will fill the same flags from their own columns.

**Alternatives**: a second query "does the record matching the national ID also match the family"
(two round trips and the same question asked twice, once early and once at submit); comparing
`MatchRef` ids across the lists (works only inside one source, which is not enough once legacy and SAS
are added).

## R2. Return target and the phone exception

**Decision**: the **return target** `T` is:
- `same_person`, if it is not empty (basis `identity`);
- otherwise `phone`, if it is not empty (basis `phone`: the phone's owner returns; the admin checks
  the card);
- otherwise there is no return.

On a draft with a valid return choice, a used phone is allowed only if **every** record that holds it
is in `T` (FR-007). This covers spec Story 2.5: phone of A and card of B gives `T = {B}`, A's phone is
not in `T`, so it is refused.

**Known limit (013/014)**: a SAS record that has the same person's phone but no national ID is not in
`T` when `T` comes from identity. That case is decided when SAS import is specified; 009 has only the
sijil source.

## R3. Storing the choice: a key, like 008's confirmation

**Decision**: new column `drafts.return_key`, which stores the key that produced the choice:
- `identity:{national_id}:{family_key}`;
- or `phone:{phone}`.

The choice is valid only while the draft's current values give the same key and `T` is still not
empty. Changing a number or the phone makes it stale, so it drops with no extra code, the same as
008's `additional_confirmed_key` (FR-006). A stale key is set to NULL on the next save.

`PATCH /drafts/{id}` takes `return_chosen: true|false`. `true` is accepted only while `T` exists; the
server picks the basis (identity is preferred over phone). Choosing a return and choosing
«إضافة اشتراك ثاني» exclude each other. Choosing one clears the other.

## R4. Decision table v1.10

`decide(matches, edited_fields, additional_confirmed, return_valid)` stays pure.

With a valid return:
1. If any record in `T` is `pending`, refuse with `return_pending`.
2. If any phone record is outside `T`, refuse with `phone_used`.
3. Otherwise create type `return`, status `pending_review`, with these reasons:
   - `return`, holding the records of `T` and their basis;
   - plus `numbers_conflict` for `id_conflict` records outside `T`;
   - plus `family_exists` for family-only records outside `T` (shown to the admin; no
     confirmation needed);
   - plus `numbers_edited`.

Without a return:
1. A phone record refuses with `phone_used`.
2. `same_person` refuses with `national_id_exists`. The page offers the return choice.
3. Otherwise these reasons add up:
   - `numbers_conflict` (from `id_conflict`);
   - `family_exists`, which needs the confirmation, as in 008;
   - `numbers_edited`.
4. Type is `additional` when a family match is confirmed, otherwise `new`.

No reasons means approved.

**Pending blocks a return (interpretation)**: the spec blocks a second return while the same person's
return is pending. A pending **new** request for the same person is just as much a duplicate, so any
`pending` record in `T` blocks. The marketer sees «يوجد طلب سابق بالانتظار لهذا المشترك».

`result` gains `pending_approval` for `return` and `numbers_conflict`. Its text is
«بانتظار موافقة المسؤول», the same as `pending_family`.

## R5. Early checks: booleans and choices only

`DraftChecksOut` becomes:

```text
phone_used, national_id_exists (= same_person), id_conflict, family_exists,
additional_confirmed, return_available, return_basis ('identity'|'phone'|null),
return_chosen, return_pending
```

No ids and no counts. With a return chosen, `phone_used` is true only for a phone outside `T`.

Missing items:
- `national_id_exists` and `phone_used` drop once a return is chosen.
- New item `return_pending`.

The conflict is not a missing item: it is a notice, and sending stays allowed (FR-004).

## R6. OTP precheck on a return draft

`precheck_for_otp(db, draft, phone)` (the 007/008 hook) now uses the draft. When the draft's return
choice is valid and every record holding the phone is in `T`, the code may be sent. Otherwise
`phone_used`, as before. The pending block is checked at submission, and early through the checks,
not here.

## R7. Submission changes

Same transaction as 008. Locks: the three keys, as in 008. Under the locks the server:
1. recomputes `T` and the validity of the return;
2. decides (R4) and writes one `request_reasons` row per matched record (the `return` reason has
   `details.basis`).

A return chosen on the page but stale at submission (a record vanished) falls back to the no-return
rules. That gives `phone_used` / `national_id_exists` refusals, or approval.

**Username (FR-015)**: a sijil target record has a `username`. The return keeps the username of the
newest record in `T` that has one. Otherwise it uses `{tower_code}-{phone}`. Usernames are not unique
in the table, so a return may reuse one. The username stays hidden until approval (008).

## R8. «الاتصال بالإدارة»

- **Setting**: `app_settings` key `admin_whatsapp`. It is edited in the «عام» tab under `settings`:
  - stored normalized by §8.1 (`07XXXXXXXXX`); empty clears it;
  - an invalid value returns `invalid_phone`;
  - each change is audited with its before and after values.
- **Delivery to the page**: `GET /api/client-config` returns `admin_whatsapp` (string or null) to any
  signed-in user, the same way it exposes `otp_enabled`.
- **Link**: `https://wa.me/964XXXXXXXXXX?text=…`. The text is «مرحباً، أنا المسوّق {اسم المسوّق}.
  عندي مشترك رقم هاتفه مسجّل سابقاً وأحتاج مساعدة الإدارة.» It holds no subscriber data, not even the
  phone that was typed.
- **Opening**: the button is a real link (`<a target="_blank">`), so phone browsers do not block it.
  On click the page also sends `POST /api/drafts/{id}/contact-admin` (no body) and does not wait for
  the answer. That call audits `draft.contact_admin_opened` (draft id only). The draft does not
  change.
- **Empty setting**: the button is disabled with «رقم الإدارة غير مضبوط في الإعدادات».

**Alternatives**: building the link on the server (no gain: the number is not secret for signed-in
users); not auditing (FR-014 asks for it).

## R9. Dashboard button

`Dashboard.tsx`: «إضافة اشتراك لمشترك موجود» is enabled and «قريباً» is removed. It runs the same
action as «إضافة مشترك جديد» (creates a draft and opens the form). Nothing is stored about where the
draft came from (FR-005c).

## R10. Labels

New and renamed Arabic labels:

| Code | Arabic |
|---|---|
| return button | «طلب العودة للخدمة» |
| contact button | «الاتصال بالإدارة» |
| family button (renamed from «طلب اشتراك إضافي») | «إضافة اشتراك ثاني» |
| return chosen | «تم اختيار طلب العودة للخدمة» + «إلغاء» |
| `id_conflict` notice | «الرقم الوطني مسجّل سابقاً ببيانات مختلفة، سيُراجع الطلب من الإدارة» |
| `return_pending` | «يوجد طلب سابق بالانتظار لهذا المشترك» |
| reasons | `return` «إعادة للخدمة», `numbers_conflict` «تعارض بالأرقام» |
| request type | `return` «إعادة للخدمة» |
| audit actions | `draft.return_chosen`, `draft.return_withdrawn`, `draft.contact_admin_opened` |

## R11. Audit and logs

These are audited with the draft id and the basis only:
- `draft.return_chosen` and `draft.return_withdrawn`;
- `draft.contact_admin_opened`;
- `request.submitted`, whose `reasons` now include `return` / `numbers_conflict`.

No national ID, family number, full phone, name, or matched record id goes into the audit `after`
or into log lines. Matched ids are stored only in `request_reasons`, which only admins read (010).
`app_setting.updated` for `admin_whatsapp` stores the administration number. That is a company
number, not subscriber data.

## R12. Tests (tests fail first)

- **Unit** (`test_decision.py`, extended): every row and combination, including:
  - phone A with identity B;
  - return with a pending record;
  - conflict with family;
  - a stale return;
  - edited numbers on a return.
- **Unit** (`test_matches.py`, new): the record flags and the four views.
- **Integration**:
  - `test_return_path.py`: choose / withdraw / stale, the OTP precheck exception, submit, username,
    reasons and their links;
  - `test_numbers_conflict.py`;
  - `test_admin_whatsapp.py`: setting, client-config, contact-admin audit;
  - extensions to `test_submit.py` (the old national-ID refusal now offers a return),
    `test_submit_concurrency.py` (two returns for one person: one wins),
    `test_log_safety.py`, `test_audit_completeness.py`, and a privacy test (SC-003). The privacy test
    walks every marketer response of every path and checks that no field of the matched record
    appears in it.
- **Vitest**:
  - `returnNotice.test.tsx`;
  - `contactAdmin.test.tsx` (link shape, no phone in the text, disabled state);
  - the `familyMatchNotice` label;
  - the dashboard button.
- **Playwright**: `existing-subscriber.spec.ts`, covering a return through identity and a return
  through the phone, up to the result screen.
