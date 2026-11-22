"""Offline check of the reader on private photos: prints to the terminal only, writes nothing.

Run it in a container with no network, the photos mounted read-only:

    docker compose run --rm --no-deps --network none \\
      -v "$PWD/test-cards:/cards:ro" ocr python -m service.evaluate /cards/*.jpeg

For each photo it prints every detected document with its class, confidences, the field texts,
the MRZ check digits, the printed back rows (`bands`) and the reading time. The output contains
card data: read it, compare it with the cards, and do not save it in the repository.
"""

import json
import sys
import time

from service import reader


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: python -m service.evaluate PHOTO [PHOTO ...]", file=sys.stderr)
        return 2
    started = time.perf_counter()
    models = reader.load()
    print(f"models loaded in {time.perf_counter() - started:.1f} s")
    for path in paths:
        with open(path, "rb") as fh:
            image = reader.decode(fh.read())
        if image is None:
            print(f"== {path}: not an image")
            continue
        result = reader.read(models, image)
        print(f"== {path}  ({result['duration_ms']} ms, {len(result['detections'])} detections)")
        print(json.dumps(result["detections"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
