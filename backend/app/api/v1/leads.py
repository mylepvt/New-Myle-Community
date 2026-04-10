from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import AuthUser, require_auth_user
from app.schemas.leads import LeadListResponse

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(_user: Annotated[AuthUser, Depends(require_auth_user)]) -> LeadListResponse:
    """Placeholder — wire SQLAlchemy + filters + role scopes next."""
    return LeadListResponse(items=[], total=0)
