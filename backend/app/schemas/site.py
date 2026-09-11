from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., min_length=1, max_length=1024)


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: int
    name: str
    base_url: str
    created_at: datetime
    url_count: int = 0
