from fastapi import APIRouter

from app.schemas.meta import MetaResponse

router = APIRouter()


@router.get("", response_model=MetaResponse)
async def meta() -> MetaResponse:
    return MetaResponse(name="myle-vl2", api_version=1)
