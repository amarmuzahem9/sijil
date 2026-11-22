"""Iraq bounding box for house locations (docs/system.md §5.2).

A generous rectangle around Iraq's borders: it rejects swapped or mistyped coordinates
(e.g. "43.68, 34.70" or a point in another country far away) without a polygon test. Points just
across a border may still pass; the reviewer sees the pin on the map. Keep in sync with
web/src/lib/coordinates.ts.
"""

LAT_MIN = 29.0
LAT_MAX = 37.5
LNG_MIN = 38.7
LNG_MAX = 48.8


def in_iraq(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX
