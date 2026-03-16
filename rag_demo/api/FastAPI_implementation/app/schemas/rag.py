from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    question_type: str | None = None
    include_debug: bool = False


class QueryResponse(BaseModel):
    answer: str
    refusal: bool
    reason: str = ""
    sources: list[int] = []
    gate: dict[str, Any] | None = None
    retrieval_debug: dict[str, Any] | None = None


class IndexResponse(BaseModel):
    chunks: int
    status: str = "completed"


class UploadResponse(BaseModel):
    filename: str
    status: str = "uploaded"
