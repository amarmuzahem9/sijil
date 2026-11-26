# Research: 018 Subscriber File and Search

All spec questions were answered by the owner on 2026-11-26 (Q1: A, Q2: A, Q3: A, assumptions approved). The
decisions below map the rules onto the existing code; there are no open unknowns.

## R1. One record kind, three sources

- **Decision**: a record is addressed as `(source, ref)` with `source ∈ {sijil, legacy, sas}` and `ref` its row id,
  the same `MatchRef` shape the check engine and the review file already use (`core/matches.py`,
  `services/linked_records.py`). Routes take `/{source}/{ref}`.
- **Rationale**: 010/014/015 already resolve `(source, ref)` into display rows; the file reuses that vocabulary.
- **Alternatives**: a new "person" table (rejected by Q1: no merging).

## R2. The search box: one kind per query

- **Decision**: new pure module `core/subscriber_search.py` with `classify(text) -> Term | None`, in this order:
  1. a legacy number: «T3C-» and exactly 3 digits («T3C-001»…«T3C-999»), checked first so `request_number.parse`
     never reads it as request 1 (request numbers start at 1001; analysis A1); then a request number («1004»,
     «T3C-1004», «#t3c-١٠٠٤») via `request_number.parse`;
  2. 12 digits (Arabic digits converted) → `national_id`;
  3. a full phone (§8.1) → `phone`;
  4. the family-number shape after the comparison key (§6.2: 4 digits, a letter, 13 characters) → `family`;
  5. a SAS/Sijil username shape (`PREFIX-07XXXXXXXXX`, case-insensitive) → `username`;
  6. an Arabic name after `clean_arabic_name`, ≥ 3 letters → `name` (folded, R3).
  Anything else → no search («اكتب اسماً أو هاتفاً أو رقماً»). `%`, `_` and Latin text never reach a LIKE pattern.
- **Rationale**: the marketer's `request_search.classify` (012) and `link_search.classify` (013) use the same
  "guess the kind" approach with a shared fixture; owners approved it as an assumption.
- **Permission (Q2)**: `national_id` and `family` kinds from a caller without `review` (and not main admin) →
  `403 identity_search_forbidden` «البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة», decided before any
  query, so the answer is the same whether the number exists or not.

## R3. Arabic name folding

- **Decision**: `fold_arabic(text)` in `core/arabic_name.py`: أ/إ/آ/ٱ → ا, ة → ه, ى → ي, diacritics, tatweel and
  direction marks removed, spaces collapsed. In SQL the same folding is one `translate()` expression over
  `full_name` (plus `regexp_replace` for diacritics), built once in `services/subscriber_search.py` and applied to
  all three tables. Match = folded name `LIKE '%' || :folded || '%'`.
- **Rationale**: stored names are already cleaned (requests §5.1); legacy and SAS keep names "as written" (§12), so
  folding on read is the only way to match across them. Sizes (≈ 25,000 rows in all) keep a sequential scan with a
  `translate()` well under the 1 s goal; T-perf proves it (R9). No extension, no migration.
- **Alternatives**: `pg_trgm` and a generated folded column with a GIN index (a migration and an extension for a
  size that does not need it; can be added later if the perf check fails).

## R4. Search query per source

- **Decision**: one query per source, each capped at `offset + limit + 1` rows, then merged in Python by
  registration time (newest first) and paged (50). Sources:
  - `sijil`: requests not deleted (deleted only for `number`, R6); phone, national ID, family key, username
    (`upper`), number, folded name. All statuses (rejected included: it is a record, §6.1 only stops it counting).
  - `legacy`: all imported rows (also «ملغي»/«مرفوض»: §12.1 they do not count but they are records); phone, family
    key, legacy number, folded name. No national ID.
  - `sas`: phone or `username_phone`, `username_key`, folded name. No national ID or family number.
  Registration time: request `submitted_at`, legacy `form_submitted_at` (else `created_at`), SAS `sas_created_at`
  (else `created_at`). The total is the sum of per-source counts.
- **Rationale**: each source has its own indexes (phone, national ID, family key, username key); a UNION over
  different shapes would lose them. 50 rows per page keeps the merge trivial.

## R5. The file: one record and its linked records (Q1)

- **Decision**: `subscriber_file.build(db, user, source, ref)`:
  - the record itself (full fields for its source; identity fields only per R7);
  - linked records found with the record's own keys: same phone (any of its phones) → «نفس الهاتف»; same national
    ID **and** family key → «نفس الشخص»; same family key only → «نفس العائلة». A record found by two reasons keeps
    the strongest (نفس الشخص > نفس الهاتف > نفس العائلة). Rejected requests and non-counting legacy rows are
    included (they are the same person's history); deleted requests are excluded except a deleted request linked
    to a request by `request_reasons` refs, which shows «سجل محذوف» (011 R10), as in the review file.
  - capped at 50 linked records, with «و N سجلات أخرى» when more (a family number shared by a whole clan).
- **Rationale**: the check engine (`match_service`) only finds *counting* records; the file needs every record of
  the person, so it runs its own lookups on the same keys and normalizations (§6.2). Link reasons are those of §6.4.
- **Alternatives**: reuse `match_service.find_matches` (misses rejected and non-counting rows).

## R6. Deleted requests

- **Decision**: a deleted request is found only by its number (kind `number`) and returned as a row
  `{source: "sijil", deleted: true, number_label}`; its file is the kept fields only, «سجل محذوف»: number,
  marketer, type, status at deletion, dates, tower, plan, deletion mark — the same kept set as 011.
- **Rationale**: §7.4 and §4.3 (found by number only).

## R7. What each permission receives (Q2)

- **Decision**: allow-list schemas built per caller:
  - main admin or `review`: everything, incl. national ID, family number, card fields, readings, image ids;
  - `link` / `reports` without `review`: name, phone(s), username, tower, dates, status, history; `national_id`,
    `family_number`, `card_fields`, `images` are **absent** (not null) from the response, and legacy «بيانات
    إضافية» is limited to the fields that are not identity numbers (mother's names and birth date stay: they are
    in §12.1's extra data, not card numbers).
  Link reasons «نفس الشخص»/«نفس العائلة» still show (owner Q2), without the numbers.
- **Rationale**: absent keys make the leak test a key-set check (SC-004), as in 013's `LinkRow`.

## R8. Images and the access log

- **Decision**: the file returns image ids only to entitled callers; images open through the existing routes
  `/api/admin/request-images/{id}` and `/api/admin/legacy-images/{id}`, which already check `review` and log every
  open with `request_id` / `legacy_subscriber_id` (010 R9, 014 R13). No new image route.
- **Rationale**: FR-011 is already satisfied by those routes; reusing them keeps one access path.

## R9. Request history

- **Decision**: built from stored facts, oldest first: `submitted_at`; acceptance (`approved_at`, `approved_by`,
  auto when null) or rejection (`rejected_at`, `rejected_by`, reason label); each pin (`request_number_pins`:
  field and who/when, never the value); each `request_links` row (link/undo, who, when, undo reason); the deletion
  mark (who, when, reason). Admin names resolved; for a `link`/`reports` caller the pin lines keep only "تم تثبيت
  رقم" with who and when.
- **Rationale**: approved assumption; the audit log stays the main admin's (§10 item 11).

## R10. API and pages

- **Decision**: router `api/admin_subscribers.py`, `require_permission("review", "link", "reports")`:
  `GET /api/admin/subscribers?q=&offset=&limit=` and `GET /api/admin/subscribers/{source}/{ref}`. The web page
  `/admin/subscribers` replaces the 001 placeholder (`AdminSubscribers`), with the file at
  `/admin/subscribers/{source}/{ref}`. Page key `subscribers` already exists in both access maps. Read-only:
  no POST/PUT/PATCH/DELETE (tested, Q3).
- **Rationale**: Principle IX; the access map of 002 already lists the page for these three permissions.

## R11. Logs

- **Decision**: log lines carry the query kind and the record reference (`source:ref`) only; never the query text,
  a name, a phone or a number (FR-012). The query text is not written to the audit log either (a search is a read).

## R12. Tests (Principle VIII)

- Unit: `test_subscriber_search.py` from fixture `subscriber_search_cases.json` (every kind, Arabic digits, folding,
  refused inputs); `test_arabic_fold.py`.
- Integration: `test_subscriber_search_api.py` (each kind across the three sources, deleted by number only,
  paging, permission refusal of identity kinds, same answer whether the number exists), `test_subscriber_file.py`
  (link reasons and strongest reason, rejected and non-counting legacy included, deleted as «سجل محذوف», history
  order, SAS fields, legacy extra), `test_subscriber_privacy.py` (key sets per permission, no identity data for
  `link`/`reports`, marketer 403 on every route, marketer own search unchanged, read-only methods 405, logs clean),
  `test_subscriber_performance.py` (20,000 SAS, 500 legacy, 5,000 requests: search < 1 s, file < 1 s).
- Web: Vitest for the search page, result rows, the file with and without identity data, «سجل محذوف».
- e2e: `e2e/tests/subscriber-file.spec.ts` with its own seed, local only.
- Each new test is run red before its code.
