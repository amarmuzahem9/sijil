"""Synthetic «card» photos for the fake reader (specs/006 research R10).

The whole image is filled with the scenario's colour, so the fake reader's corner sample picks
that scenario even after resizing or JPEG compression. The text says «بطاقة تجريبية»: no real
card, name or number is ever drawn.
"""

import io

from PIL import Image, ImageDraw

from app.services.card_reader_fake_data import SCENARIOS


def scenario_jpeg(name: str, width: int = 1200, height: int = 760) -> bytes:
    colour = tuple(SCENARIOS[name]["rgb"])
    image = Image.new("RGB", (width, height), colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (width // 4, height // 3, width * 3 // 4, height * 2 // 3), outline=(255, 255, 255)
    )
    draw.text((width // 3, height // 2), "synthetic card - بطاقة تجريبية", fill=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
