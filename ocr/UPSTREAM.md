# Card reader service (`ocr`)

This folder is the card reader of the Sijil app (feature 006). It is published as a public copy,
because the reader is licensed under the **GNU AGPL-3.0** (see `LICENSE`). Users of the app can
get this source from the link in «حسابي» → «رخص البرمجيات المفتوحة». The rest of the Sijil app
is a separate program that talks to this service over HTTP and is not covered by this licence.

## Upstream

| | |
|---|---|
| Project | ID_Iraqi_Project (`idcard-extractor`) |
| Source | https://github.com/Hai800Z/ID_Iraqi_Project |
| Commit | `c12a24e` |
| Licence | AGPL-3.0 (code and trained weights; the detectors are built with Ultralytics YOLO) |
| Weights | Release `v1.0.0` of the same repository: `findCard.pt`, `text.pt`, `MRZ1.pt`, checked against `upstream/models/SHA256SUMS` at build time |

Note: the upstream README points the weights at `Hai800Z/Id_iraqi`, which no longer serves them.
The build uses `https://github.com/Hai800Z/ID_Iraqi_Project/releases/download/v1.0.0`.

`upstream/` is a verbatim copy of these upstream paths at that commit: `src/`,
`models/SHA256SUMS`, `scripts/download_weights.py`, `requirements.txt`, `pyproject.toml`,
`LICENSE`, `README.md`, `README.ar.md`. Tests, CI files, images and the Windows launcher are not
copied.

## Local changes to upstream

None. All of our code is in `service/`:

| File | Purpose |
|---|---|
| `service/reader.py` | Loads the models once and reads **one photo**, returning every detected document with its fields and MRZ (no front/back pairing, no rejection rules) |
| `service/app.py` | HTTP API: `GET /health`, `POST /read` (one reading at a time) |
| `service/evaluate.py` | Offline check on a folder of photos; prints to the terminal only |

The contract is described in the Sijil repository at
`specs/006-card-ocr/contracts/ocr-service.md`.

## Privacy

The service keeps no image and no result. It writes no file other than `mrzmini`'s short-lived
temporary files, which go to `/tmp`, a `tmpfs` mount. It logs no card text or number. In the
Sijil deployment it has no internet access, and only the app's server can reach it.
