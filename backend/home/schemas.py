# 홈 API 응답 스키마

from pydantic import BaseModel


class ChunkCounts(BaseModel):
    structured: int
    unstructured: int
    total: int


class HomeResponse(BaseModel):
    ready: bool
    counts: ChunkCounts
