# Quickstart: validating 018

Synthetic data only; everything on the owner's machine.

## Prerequisites

- `docker compose up` (no new migration; head stays `0020`).
- Accounts: the main admin, admins with `review` only, `link` only, `reports` only, `settings` only, and two
  marketers.
- A synthetic legacy import (014) and SAS import (015) whose rows share a phone or a family number with some
  synthetic requests.

## Automated

```powershell
docker compose exec api pytest -q tests/unit/test_subscriber_search.py tests/unit/test_arabic_fold.py tests/integration -k subscriber
cd web; npx vitest run subscriber   # from PowerShell
bash scripts/e2e.sh                 # the full Playwright suite, local stack only
```

Expected: all green; each new test was run red first.

## Manual scenarios

1. **Search across sources** — by a shared phone: the request and the SAS row; by the family number (as `review`):
   the request and the legacy row; by part of a name with «أ»/«ا» or «ة»/«ه» swapped: the same rows. (US1)
2. **Deleted** — by phone: not found; by number: «سجل محذوف» with the number only. (FR-006)
3. **The file** — linked records with «نفس الشخص»/«نفس الهاتف»/«نفس العائلة»; a rejected request and a «ملغي»
   legacy row are listed; history in time order. (US2, FR-007, FR-008)
4. **Permissions** — as `link` or `reports`: no national ID, family number or images anywhere; a national-ID search
   says «البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة» for an existing and a made-up number alike; as
   `settings`: no menu entry, direct URL refused; as a marketer: no access. (FR-001, FR-002, FR-009)
5. **Images** — as `review`, open a card image from the file; the image access log has the open. (FR-011)
6. **Read-only** — no edit control anywhere in the file. (FR-010)

The Arabic manual test for the owner goes in `manual-test-ar.md` at the end of implementation.
