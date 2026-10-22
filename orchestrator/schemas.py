from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class WorkflowRequest(BaseModel):                     #Input required to run a coaching workflow.

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty or contain only whitespace.")
        return value


class WorkflowResponse(BaseModel):

    session_id: str | None
    status: Literal["completed", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
