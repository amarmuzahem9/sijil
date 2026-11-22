# Quickstart: validating feature 006 (card reading)

Contracts: [api.md](./contracts/api.md), [ocr-service.md](./contracts/ocr-service.md). Data:
[data-model.md](./data-model.md).

## Prerequisites

- Docker Desktop; the dev stack from 005 (`docker compose up`).
- **Build the reader once**: `docker compose build ocr`. The image is about 4.3 GB, and the build
  needs internet for the packages and the model weights. The build fails if a weight checksum
  does not match.
- `.env` has `OCR_MODE=http` and `OCR_URL=http://ocr:8080`. `OCR_SOURCE_URL` may stay empty
  locally.

## Automated checks (all must pass)

```bash
docker compose exec api pytest          # rules, apply/no-overwrite, NID check, no-surname, jobs (fake reader)
docker compose exec web npm test        # marks, merge without overwriting pending edits, polling
bash scripts/e2e.sh                     # Playwright with OCR_MODE=fake (synthetic images)
docker compose run --rm ocr pytest      # reader: /health and /read shape on a blank synthetic image
```

## Isolation checks

| # | Check | Expected |
|---|---|---|
| I1 | `docker compose exec ocr python -c "import urllib.request; urllib.request.urlopen('https://github.com', timeout=5)"` | Fails: no route to the internet |
| I2 | `docker compose ps ocr` | No published ports |
| I3 | `docker compose exec api python -c "import httpx; print(httpx.get('http://ocr:8080/health').json())"` | `{"status": "ok", "models": "loaded", ...}` |
| I4 | `docker stats --no-stream sijil-ocr-1` | Memory limit 2 GiB, CPU use ≤ 200% while reading |
| I5 | `docker compose logs ocr api \| grep -E "[0-9]{12}"` after a reading | No national ID or other card number in the logs |

## Scenarios (with the fake reader, `OCR_MODE=fake`)

Synthetic images whose top-left corner colour selects the scenario (R10). The e2e helper draws
them.

| # | Scenario | Expected |
|---|---|---|
| A | Upload a clear front only | No reading; «ارفع الوجه الآخر لتبدأ قراءة البطاقة» |
| B | Then upload a clear back | «جارٍ قراءة البطاقة», then 8 fields filled with «من البطاقة»; draft saved |
| C | Edit the grandfather's name | The mark becomes «عُدِّل يدوياً»; the original reading is kept (GET the draft: `card_fields.grandfather_name.original`) |
| D | Replace the front with another clear front | Unedited fields take the new values; the edited grandfather is unchanged |
| E | Front with an empty surname | Surname empty, with the hint pointing to «لا يوجد لقب على البطاقة»; ticking it removes «اللقب» from «النواقص» |
| F | Mismatched national ID (verified MRZ) | «تأكد من الرقم الوطني» with both numbers; «النواقص» lists it until «اعتماد هذا الرقم» |
| G | No card in the front photo | Front slot: «لم نتمكن من قراءة وجه البطاقة» + «أعد التصوير» + tips; fields stay editable |
| H | Back photo in the front slot | «هذه صورة الظهر، ضعها في خانتها» |
| I | Two cards in one photo | «يظهر أكثر من مستمسك في الصورة» |
| J | Same card detected twice | Read normally, no re-shoot |
| K | Reader failure | «تعذّرت القراءة الآلية، أكمل يدوياً» + «أعد المحاولة»; typing still works |
| L | Slow reader (> 60 s) | Same failure message within 60 s |
| M | Open the draft on a second device after B | The same values and marks; the second device first shows «تغيّرت المسودة من جهاز آخر» |
| N | «حسابي» → «رخص البرمجيات المفتوحة» | Reader name, AGPL-3.0 and the source link |

## Real-reader check (owner, private photos, never committed)

```bash
docker compose run --rm --network none -v "$PWD/test-cards:/cards:ro" ocr \
  python -m service.evaluate /cards/*.jpeg
```

The command prints each photo's detections, fields, MRZ checks and timing to the terminal only.
Compare with the cards to confirm SC-002. Do not save the output in the repository.

## Staging

- Follow the new section of `deploy/staging.md`:
  - build `ocr` on the server, which needs internet for the build only;
  - check I1–I4.
- Publish the `ocr/` folder to the public copy, and set `OCR_SOURCE_URL` before the first
  deployment. You will be reminded before the public copy is created.
- The server needs about 5 GB of free disk for the image and 2 GB of memory for the reader.
