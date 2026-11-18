# 홈 기능 : React 홈 화면에 필요한 벡터 DB 상태를 제공

from fastapi import APIRouter

from home.schemas import HomeResponse
from vectordb.wine_store import get_chunk_counts

router = APIRouter()


# 서버 동작 확인용 (React 화면은 React 개발 서버가 제공)
@router.get("/", include_in_schema=False)
def root():
    return {"message": "AI 와인 소믈리에 API 서버입니다."}


# ready가 false이면 create_vector_db.py 를 아직 실행하지 않은 상태
@router.get("/api/home", response_model=HomeResponse, tags=["home"])
def home():
    counts = get_chunk_counts()
    return {"ready": counts["total"] > 0, "counts": counts}
