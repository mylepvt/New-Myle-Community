"""Public JSON metadata for the SPA.

**Not** a webhook endpoint: no Meta/Facebook/social POST ingest here — only ``GET`` bootstrap
(environment + feature flags). Do not add webhook handlers under ``/meta``.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.meta import ClientFeatures, MetaResponse

router = APIRouter()


@router.get("", response_model=MetaResponse)
async def meta() -> MetaResponse:
    """Public bootstrap: version, environment, feature flags for smart client shell."""
    return MetaResponse(
        name="myle-vl2",
        api_version=1,
        environment=settings.app_environment,
        features=ClientFeatures(intelligence=settings.feature_intelligence),
    )
