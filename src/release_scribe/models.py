from pydantic import BaseModel, Field


class Change(BaseModel):
    type: str
    scope: str | None = None
    description: str
    breaking: bool = False


class ReleaseNotes(BaseModel):
    version: str
    title: str
    changes: list[Change] = Field(default_factory=list)