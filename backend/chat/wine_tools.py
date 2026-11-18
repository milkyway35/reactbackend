# 에이전트 도구 정의 (이전 프로젝트 mcp_server/rag_server.py 를 앱 내부 도구로 변경)
#
# MCP stdio 서버는 도구를 호출할 때 subprocess를 실행하는데,
# Windows에서 uvicorn --reload 로 실행하면 subprocess를 지원하지 않는 SelectorEventLoop가 사용됨

from langchain_core.tools import tool

from vectordb.wine_store import mmr_search


# 와인 RAG 검색 도구 정의
@tool
def search_wine(
    query: str,
    k: int = 3,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False
) -> str:
    """
    와인 정보를 벡터 검색으로 조회합니다.
    결과에는 이름, 빈티지, 지역, 가격, 재고량, 한식 페어링, 테이스팅 노트가 포함됩니다.

    가격과 재고 조건은 query에 넣지 말고 반드시 아래 인자로 지정합니다. (벡터 검색은 숫자 조건을 구분하지 못합니다.)
    - "20만원 이하" -> max_price=20, in_stock_only=True
    - "10만원 이상" -> min_price=10, in_stock_only=True
    - "5만원대" -> min_price=5, max_price=5.99, in_stock_only=True
    - "재고 있는 와인", "지금 살 수 있는 와인" -> in_stock_only=True
    - "불고기에 어울리는 10만원 이하 와인" -> query="불고기에 어울리는 와인", max_price=10, in_stock_only=True
    가격 조건을 지정하면 가격이 미정인 와인은 제외됩니다.

    Args:
        query: 와인 이름, 품종, 음식, 맛 키워드
        k: 결과 개수(1-10)
        min_price: 최소 가격(단위: 만원)
        max_price: 최대 가격(단위: 만원)
        in_stock_only: True이면 재고가 있는 와인만 검색
    """
    # 상세 문서에 기본정보가 모두 들어 있으므로 상세 문서만 검색
    # 페어링 정보가 없는 정형 데이터를 고르면 LLM이 페어링과 와인 종류를 지어내는 문제가 있었음
    results = mmr_search(query, "Unstructured Data", max(1, min(k, 10)), min_price, max_price, in_stock_only)

    if not results:
        return "검색 결과가 없습니다."
    return "\n\n".join(doc.page_content for doc in results)

