"""Request/response contracts."""

from pydantic import BaseModel, model_validator


class PayloadRequest(BaseModel):
    list_1: list[str]
    list_2: list[str]

    @model_validator(mode="after")
    def _equal_lengths(self) -> "PayloadRequest":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreatedResponse(BaseModel):
    id: str
    cached: bool


class PayloadResponse(BaseModel):
    output: str
