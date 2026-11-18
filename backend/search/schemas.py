# 와인 검색 API 요청/응답 스키마

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

SourceType = Literal["all", "Structured Data", "Unstructured Data"]

# 가격 조건(단위: 만원). React 입력칸을 비우면 빈 문자열로 전달될 수 있으므로 None으로 바꿔줌
# ge 제약이 None에 적용되면 오류가 나므로 float 쪽에만 지정
PriceQuery = Annotated[
    Annotated[float, Field(ge=0, allow_inf_nan=False)] | None,
    BeforeValidator(lambda value: value or None)
]


class WineResult(BaseModel):
    name: str
    vintage: str
    region: str
    price: str
    stock: str
    price_value: float | None = Field(default=None, description="가격 숫자값(단위: 만원), 미정이면 null")
    stock_value: int = Field(default=0, description="재고량 숫자값")
    pairing: str = ""
    tasting_note: str = ""
    source_type: str
    content: str
    score: float = Field(description="코사인 유사도")


class SearchResponse(BaseModel):
    query: str
    source_type: SourceType
    k: int
    min_price: float | None
    max_price: float | None
    in_stock_only: bool
    results: list[WineResult]
