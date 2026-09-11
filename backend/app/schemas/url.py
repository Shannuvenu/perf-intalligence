from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UrlCategory = Literal["homepage", "article", "category", "other"]


class UrlCreate(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    url_category: UrlCategory = "other"
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class UrlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url_id: int
    site_id: int
    url: str
    url_category: str
    enabled: bool
    created_at: datetime
