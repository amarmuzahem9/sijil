# sijil-ocr

The Iraqi national ID card reader used by the Sijil app. It is published here because it is
licensed under the **GNU AGPL-3.0** (see [LICENSE](LICENSE)): users of the app can get its
complete source, including every change made to it.

It is built on the open-source project
[ID_Iraqi_Project](https://github.com/Hai800Z/ID_Iraqi_Project) (commit `c12a24e`, unchanged in
[`upstream/`](upstream/)), with a small HTTP wrapper in [`service/`](service/). Details, the list
of local changes and the privacy notes are in [UPSTREAM.md](UPSTREAM.md).

## What it does

- `GET /health` reports whether the models are loaded.
- `POST /read` (multipart `image` + `side` = `front`|`back`) returns every document detected in
  the photo: its class and confidences, the text of each field, the MRZ with its check digits,
  and for a back the raw readings of the printed rows. It makes no decision and keeps nothing.

## Build and run

```bash
docker build -t sijil-ocr .          # needs internet: packages and model weights (SHA-256 checked)
docker run --rm --network none --tmpfs /tmp --cpus 2 --memory 2g -p 127.0.0.1:8080:8080 sijil-ocr
```

The image is about 4.3 GB, uses about 1.4 GB of memory, and runs without any network access.

Tests: `docker run --rm --network none --tmpfs /tmp sijil-ocr python -m pytest -q tests`

## Licence

GNU AGPL-3.0, like the upstream project and its trained weights.
