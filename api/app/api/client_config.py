"""/api/client-config — runtime configuration for the browser (specs/005 research.md R10).

The Maps JavaScript key is visible to browsers by design; it is restricted to the app's domain
(HTTP referrer) and to the Maps JavaScript API in the Google Cloud console. Keeping it in `.env`
lets one web build serve every environment, and keeps it out of the repository.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthContext, current_user
from app.config import get_settings

router = APIRouter(tags=["client-config"])


class LatLng(BaseModel):
    lat: float
    lng: float


class MapsConfig(BaseModel):
    api_key: str
    map_id: str
    default_center: LatLng


class OpenSourceItem(BaseModel):
    """An open-source component the app's users may get the source of (specs/006 FR-022)."""

    name: str
    licence: str
    url: str


# The card reader is AGPL-3.0: its source (with our changes) is offered to every user through
# the public copy of `ocr/` (OCR_SOURCE_URL), or the upstream project until that copy exists.
OCR_UPSTREAM_URL = "https://github.com/Hai800Z/ID_Iraqi_Project"


def open_source_items() -> list[OpenSourceItem]:
    url = get_settings().ocr_source_url.strip() or OCR_UPSTREAM_URL
    return [OpenSourceItem(name="ID_Iraqi_Project", licence="AGPL-3.0", url=url)]


class ClientConfig(BaseModel):
    maps: MapsConfig | None
    open_source: list[OpenSourceItem] = []


@router.get("/client-config", response_model=ClientConfig)
def get_client_config(_: AuthContext = Depends(current_user)) -> ClientConfig:
    settings = get_settings()
    if not settings.google_maps_api_key:
        return ClientConfig(maps=None, open_source=open_source_items())
    lat, lng = settings.map_center
    return ClientConfig(
        maps=MapsConfig(
            api_key=settings.google_maps_api_key,
            map_id=settings.google_maps_map_id,
            default_center=LatLng(lat=lat, lng=lng),
        ),
        open_source=open_source_items(),
    )
