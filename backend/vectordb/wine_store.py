# Chroma 벡터 스토어 연결 및 유사도 검색 (이전 프로젝트 mcp_server/rag_server.py 의 검색 로직 재사용)

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from common.config import CHROMA_DIR, COLLECTION_METADATA, COLLECTION_NAME, EMBEDDING_MODEL


# 벡터 스토어는 앱 전체에서 하나만 생성
@lru_cache
def get_vector_store():
    return Chroma(
        collection_name=COLLECTION_NAME,
        collection_metadata=COLLECTION_METADATA,
        persist_directory=CHROMA_DIR,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL)
    )


# Chroma 검색 조건 생성 : 가격 단위는 만원, 가격 미정인 와인은 가격 조건을 지정하면 제외됨
def build_filter(source_type="all", min_price=None, max_price=None, in_stock_only=False):
    conditions = []
    if source_type != "all":
        conditions.append({"source_type": source_type})
    if min_price is not None:
        conditions.append({"price_value": {"$gte": min_price}})
    if max_price is not None:
        conditions.append({"price_value": {"$lte": max_price}})
    if in_stock_only:
        conditions.append({"stock_value": {"$gt": 0}})

    if not conditions:
        return None
    # 조건이 2개 이상이면 $and로 묶어야 함
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


# 저장된 청크 수 (0이면 create_vector_db.py 를 아직 실행하지 않은 상태)
def get_chunk_counts():
    vector_store = get_vector_store()
    structured = len(vector_store.get(where={"source_type": "Structured Data"}, include=[])["ids"])
    unstructured = len(vector_store.get(where={"source_type": "Unstructured Data"}, include=[])["ids"])
    return {"structured": structured, "unstructured": unstructured, "total": structured + unstructured}


# 유사도 검색 : 화면과 API에서 사용 (점수 포함)
def search_wines(query, source_type="all", k=5, min_price=None, max_price=None, in_stock_only=False):
    # 와인마다 정형/비정형 청크가 1개씩 있으므로 2배수를 가져와서 와인 단위로 묶음
    results = get_vector_store().similarity_search_with_relevance_scores(
        query, k=k * 2, filter=build_filter(source_type, min_price, max_price, in_stock_only)
    )

    # 결과가 유사도 순이라 와인별로 처음 나온 청크가 가장 점수가 높음
    wines = {}
    for doc, score in results:
        wines.setdefault(doc.metadata["name"], {
            **doc.metadata,
            "content": doc.page_content,
            "score": round(score, 4)
        })
    return list(wines.values())[:k]


# MMR 검색 : 에이전트 도구에서 사용 (유사도 60% + 다양성 40%)
def mmr_search(query, source_type="all", k=3, min_price=None, max_price=None, in_stock_only=False):
    retriever = get_vector_store().as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,            # 최종 결과 수
            "fetch_k": 15,     # 후보군 15개
            "lambda_mult": 0.6,
            "filter": build_filter(source_type, min_price, max_price, in_stock_only)
        }
    )
    return retriever.invoke(query)
