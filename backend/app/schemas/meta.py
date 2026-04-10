from pydantic import BaseModel


class MetaResponse(BaseModel):
    name: str
    api_version: int
