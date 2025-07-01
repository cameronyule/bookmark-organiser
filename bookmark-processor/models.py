from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict
import pendulum


class Bookmark(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True) # Added for Pydantic v2+

    href: str
    description: str
    extended: str = ""  # Default to empty string
    meta: str
    hash: str
    time: str
    shared: str
    toread: str
    tags: List[str] = Field(default_factory=list) # Default to empty list

    # New fields for processing results
    is_live: Optional[bool] = None
    liveness_checked_on: Optional[pendulum.DateTime] = None
    liveness_method: Optional[Literal["HEAD", "GET", "HEADLESS", "NONE", "ERROR"]] = None
    liveness_status_code: Optional[int] = None
    content: Optional[str] = None  # Main content extracted from the page
    summary: Optional[str] = None  # AI-generated summary of the content

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return v.split()
        return v


class LivenessResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True) # Added for Pydantic v2+

    url: str
    is_live: bool
    status_code: Optional[int] = None
    method: Literal["HEAD", "GET", "HEADLESS", "NONE", "ERROR"]
    final_url: Optional[str] = None
    content: Optional[str] = None
