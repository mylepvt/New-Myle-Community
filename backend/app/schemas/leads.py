from pydantic import BaseModel, ConfigDict


class LeadPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class LeadListResponse(BaseModel):
    items: list[LeadPublic]
    total: int
