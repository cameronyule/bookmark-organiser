from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Bookmark(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    href: str
    description: str
    extended: str = ""
    meta: str
    hash: str
    time: str
    shared: str
    toread: str
    tags: List[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return v.split()
        return v


class LivenessResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str
    is_live: bool
    status_code: Optional[int] = None
    method: Literal["GET", "HEADLESS", "NONE", "ERROR"]
    final_url: Optional[str] = None
    content: Optional[str] = None
