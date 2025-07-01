from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class Bookmark(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Added for Pydantic v2+

    url: str
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    added_date: datetime = Field(default_factory=datetime.now)
    extended_description: Optional[str] = None
    liveness: Optional["LivenessResult"] = None  # Forward reference

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        return v


class LivenessResult(BaseModel):
    is_live: bool
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    html_content: Optional[str] = None
    error_message: Optional[str] = None
    check_method: Optional[str] = None


# Update forward references
Bookmark.model_rebuild()
