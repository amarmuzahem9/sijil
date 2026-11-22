# Contract: internal reader service `ocr` (feature 006)

Reachable only from `api` at `http://ocr:8080` on the internal network `ocr_net` (R3). No
authentication: no other container is on that network and no port is published. The service
keeps no image, no result and no log line with card content (FR-019).

## `GET /health`

- 200 `{"status": "ok", "models": "loaded", "upstream": "c12a24e"}` once all four models are
  in memory.
- 503 while loading. Loading takes about 8 s at start; models are never reloaded between
  readings.

## `POST /read`

`multipart/form-data`:
- `image`: JPEG or PNG, at most 6 MB;
- `side`: `front` | `back`, the slot it was uploaded to. Every detection is reported anyway.

One reading runs at a time (an internal lock); further requests wait. The caller's timeout is
45 s (R5).

200:

```json
{
  "duration_ms": 3120,
  "detections": [
    {
      "class": "iraq id card",
      "confidence": 0.95,
      "second_pass": 0.94,
      "box": [10, 20, 900, 590],
      "orientation": "NORMAL",
      "fields": {"name": {"text": "...", "confidence": 0.99}, "id": {"text": "...", "confidence": 0.99}},
      "mrz": null,
      "error": null
    },
    {
      "class": "back",
      "confidence": 0.85,
      "second_pass": 0.85,
      "box": [12, 30, 880, 560],
      "orientation": "NORMAL",
      "fields": {"nu_f": {"text": "...", "confidence": 0.99}, "city": {"text": "...", "confidence": 0.93}},
      "mrz": {
        "mrz_type": "TD1", "number": "...", "optional1": "...", "date_of_birth": "...",
        "expiration_date": "...", "sex": "M",
        "valid_number": true, "valid_date_of_birth": true,
        "valid_expiration_date": true, "valid_composite": true
      },
      "error": null
    }
  ]
}
```

- `detections` lists every document found, in any order; it is empty when there is none.
- Fields are read only for detections with `second_pass >= 0.50`; the others have empty `fields`.
- Front labels: `name dad gf last mom gm gn id id2`. Back labels: `city nu_f`, plus `mrz`.
- `valid_composite` comes from `mrzmini`, or is computed from the raw MRZ lines (R4). It is null
  when it cannot be known.
- A back detection with both `city` and `nu_f` also carries `bands` (R13): the raw readings of
  the printed rows located by position:

  ```json
  "bands": {
    "issue": ["...", "..."],
    "expiry": ["..."],
    "birth": ["..."],
    "authority": {"text": "...", "confidence": 0.93}
  }
  ```

  Each date row lists up to 6 candidate texts: the Arabic recogniser and Tesseract (digits and
  «/» only), on the whole band and on its value end. The service makes no decision about them.
  `bands` is null when `city` or `nu_f` was not found.

Errors: 400 `bad_image` (not decodable), 413 (too large), 503 `loading`, 500 `reader_error`.
The body never echoes the image or the text.

## Build and runtime guarantees

- The upstream code in `ocr/upstream/` is pinned to commit `c12a24e`. Local changes are listed
  in `ocr/UPSTREAM.md`.
- The weights are fetched at build and checked against `SHA256SUMS`, or the build fails. The OCR
  recognition model is fetched at build too. At runtime the service makes no network call.
- The service runs as a non-root user, with `/tmp` on `tmpfs`, and at most 2 CPUs and 2 GB.
