# 와인 검색 기능 : JSON API (API는 http://localhost:8000/docs 에서 테스트 가능)

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from openai import OpenAIError

from common.config import SEARCH_RATE_LIMIT
from common.security import limiter
from search.schemas import PriceQuery, SearchResponse, SourceType
from vectordb.wine_store import get_chunk_counts, search_wines

logger = logging.getLogger(__name__)

router = APIRouter()


# 유사도 검색 API : /api/search?query=...&source_type=all&k=5&min_price=&max_price=20&in_stock_only=true
@router.get("/api/search", response_model=SearchResponse, tags=["search"])
@limiter.limit(SEARCH_RATE_LIMIT)
def search(
    request: Request,
    query: str = Query(min_length=1, max_length=500),
    source_type: SourceType = "all",
    k: int = Query(5, ge=1, le=10),
    min_price: PriceQuery = None,
    max_price: PriceQuery = None,
    in_stock_only: bool = False
):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="검색어를 입력해 주세요.")

    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="최소 가격이 최대 가격보다 큽니다.")

    if get_chunk_counts()["total"] == 0:
        raise HTTPException(status_code=503, detail="벡터 DB가 비어 있습니다. python vectordb/create_vector_db.py 를 먼저 실행해 주세요.")

    try:
        results = search_wines(query, source_type, k, min_price, max_price, in_stock_only)
    except OpenAIError:
        logger.exception("임베딩 모델 호출 실패")
        raise HTTPException(status_code=502, detail="임베딩 모델 호출에 실패했습니다.")

    return {
        "query": query,
        "source_type": source_type,
        "k": k,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock_only": in_stock_only,
        "results": results
    }
