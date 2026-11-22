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


class ClientConfig(BaseModel):
    maps: MapsConfig | None


@router.get("/client-config", response_model=ClientConfig)
def get_client_config(_: AuthContext = Depends(current_user)) -> ClientConfig:
    settings = get_settings()
    if not settings.google_maps_api_key:
        return ClientConfig(maps=None)
    lat, lng = settings.map_center
    return ClientConfig(
        maps=MapsConfig(
            api_key=settings.google_maps_api_key,
            map_id=settings.google_maps_map_id,
            default_center=LatLng(lat=lat, lng=lng),
        )
    )
