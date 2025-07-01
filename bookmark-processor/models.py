from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class Bookmark(BaseModel):
    href: str
    description: str
    extended: str
    meta: str
    hash: str
    time: str
    shared: str
    toread: str
    tags: List[str]

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return v.split()
        return v


class LivenessResult(BaseModel):
    status: Literal["success", "failed"]
    method: Optional[Literal["head_then_get", "get", "headless"]] = None
    final_url: Optional[str] = None
    content: Optional[str] = None  # HTML content
    error_message: Optional[str] = None
