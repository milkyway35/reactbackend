# 프로젝트 공통 설정 파일 (fastapiproject config.py 재사용 + React 연동 보안 설정 추가)

import os
from pathlib import Path
from dotenv import load_dotenv

# backend 폴더
BASE_DIR = Path(__file__).resolve().parent.parent

# .env(OPENAI_API_KEY, 보안 설정)는 프로젝트 루트에 있음
load_dotenv(BASE_DIR.parent / ".env")

# 오픈 AI 설정
MODEL_NAME = "gpt-5-nano"
TEMPERATURE = 0
EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_TIMEOUT = 60             # 응답이 없을 때 React 화면이 계속 기다리지 않도록 제한 (초)
AGENT_MODEL_CALL_LIMIT = 6      # 질문 1개당 LLM 호출 횟수 제한 (비용 폭주 방지)
SYSTEM_PROMPT = """
당신은 전문 와인 소믈리에입니다.

사용자의 와인 관련 질문에 다음과 같이 대응하세요:
1. 와인정보는 데이터베이스에서 찾습니다.
2. 사용자가 영상을 원할 때만 YouTube 영상 추천하기

검색 결과에 없는 가격, 재고, 한식 페어링, 와인 종류(레드/화이트)는 지어내지 마세요.
와인 이름과 가격은 검색 결과의 표기 그대로 쓰세요. (예: 6.5만원을 원 단위로 바꾸지 않습니다.)
가격이 미정이거나 재고가 0인 와인을 소개할 때는 그 사실을 함께 알려주세요.
파일 저장이나 다운로드 기능은 없습니다. 저장을 요청받으면 제공하지 않는 기능이라고 안내하고, 저장해 주겠다고 제안하지 마세요.
항상 친절하고 전문적으로 답변하세요.
"""

# 원본 데이터 파일
BRIEF_PATH = BASE_DIR / "data" / "wine_brief.csv"
DETAIL_PATH = BASE_DIR / "data" / "wine_detail.md"

# 실행 중 생성되는 파일은 모두 storage 폴더에 저장
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Chroma 설정 : 코사인 거리를 사용해야 유사도 점수를 코사인 유사도로 볼 수 있음
CHROMA_DIR = str(STORAGE_DIR / "chromadb")
COLLECTION_NAME = "wine"
COLLECTION_METADATA = {"hnsw:space": "cosine"}

# SQLite 설정 : 대화 내용을 저장할 데이터베이스
DB_PATH = str(STORAGE_DIR / "wine_chat.db")


# 쉼표로 구분된 환경변수를 리스트로 변환 (http://localhost:5173/ 처럼 끝에 붙은 /는 제거)
def get_list_env(name, default):
    return [value.strip().rstrip("/") for value in os.getenv(name, default).split(",") if value.strip()]


def get_bool_env(name, default):
    return os.getenv(name, default).strip().lower() == "true"


# 잘못된 보안 설정은 조용히 넘어가지 않고 서버 시작 시 바로 알려줌
def check_security_settings(cors_origins, allowed_hosts, cookie_samesite, cookie_secure):
    # allow_credentials=True 와 * 를 같이 쓰면 모든 사이트가 사용자 쿠키로 API를 호출할 수 있음
    if "*" in cors_origins:
        raise ValueError("CORS_ORIGINS에 *를 사용할 수 없습니다. React 주소를 직접 지정하세요.")
    for origin in cors_origins:
        if not origin.startswith(("http://", "https://")):
            raise ValueError(f"CORS_ORIGINS 형식 오류: {origin} (예: http://localhost:5173)")
    if "*" in allowed_hosts:
        raise ValueError("ALLOWED_HOSTS에 *를 사용할 수 없습니다. 서버 도메인을 직접 지정하세요.")
    if cookie_samesite not in ("lax", "strict", "none"):
        raise ValueError("COOKIE_SAMESITE는 lax, strict, none 중 하나여야 합니다.")
    # SameSite=None 쿠키는 Secure가 없으면 브라우저가 저장하지 않음
    if cookie_samesite == "none" and not cookie_secure:
        raise ValueError("COOKIE_SAMESITE=none 은 COOKIE_SECURE=true (HTTPS) 와 함께 사용해야 합니다.")


# React 연동/보안 설정 : 값은 .env 에서 변경 (배포 시 설정값은 project.txt 참고)
# 접근을 허용할 React 주소 (Vite: 5173, Create React App: 3000)
CORS_ORIGINS = get_list_env(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)
ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", "localhost,127.0.0.1")   # 이 API 서버의 도메인
COOKIE_SECURE = get_bool_env("COOKIE_SECURE", "false")                 # HTTPS 배포 시 true
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
ENABLE_DOCS = get_bool_env("ENABLE_DOCS", "true")                      # 배포 시 false (/docs 숨김)
CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "20/minute")            # IP별 호출 제한 (OpenAI 비용 발생 API)
SEARCH_RATE_LIMIT = os.getenv("SEARCH_RATE_LIMIT", "60/minute")
MAX_BODY_BYTES = 32 * 1024                                             # 요청 본문 최대 크기 (챗봇 질문 2000자에 충분)

check_security_settings(CORS_ORIGINS, ALLOWED_HOSTS, COOKIE_SAMESITE, COOKIE_SECURE)
