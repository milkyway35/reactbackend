# AI 와인 소믈리에 API (React 연동 FastAPI 백엔드)

[fastapiproject](../fastapiproject)(FastAPI + Jinja2)의 기능을 React에서 호출할 수 있는 **JSON API 서버**로 바꾼 프로젝트입니다.
화면(React)은 별도 프로젝트에서 만들며, 이 저장소에는 React 코드가 없습니다.

## 주요 기능

- 벡터 DB 상태 조회 (홈 화면용)
- 와인 유사도 검색 (가격/재고 필터, 유사도 점수 포함)
- AI 소믈리에 챗봇 (대화 기록 유지)
- YouTube 와인 영상 추천

`backend/data`의 와인 데이터(60종)를 OpenAI `text-embedding-3-small`로 임베딩해 ChromaDB에 저장하고 검색합니다.
챗봇은 `gpt-5-nano` 에이전트가 `search_wine`(DB 검색), `youtube_search`(영상 검색) 도구를 골라 사용합니다.

## 기술 스택

FastAPI, Uvicorn, Pydantic, ChromaDB, LangChain / LangGraph, OpenAI API, SQLite(대화 기록), slowapi(호출 제한)

## 프로젝트 구조

```
reactbackend/
├─ requirements.txt
├─ .env                  OPENAI_API_KEY (Git에 올리지 않음)
└─ backend/              ※ 실행 위치
   ├─ main.py            앱 생성, 보안 설정, 라우터 연결
   ├─ common/            config.py(설정값), security.py(CORS, 보안 헤더, 호출 제한)
   ├─ home/              GET /api/home
   ├─ search/            GET /api/search
   ├─ chat/              챗봇 API, 에이전트, 도구
   ├─ vectordb/          create_vector_db.py(임베딩 저장), wine_store.py(검색)
   ├─ data/              wine_brief.csv, wine_detail.md
   └─ storage/           실행 시 자동 생성 (ChromaDB, 대화 기록 SQLite)
```

## 실행 방법

프로젝트 루트에 `.env` 파일을 만들고 키를 넣습니다.

```
OPENAI_API_KEY=발급받은 키
```

```powershell
cd reactbackend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd backend
python vectordb/create_vector_db.py   # 최초 1회, 데이터가 바뀌면 다시 실행
uvicorn main:app --reload
```

API 문서: http://localhost:8000/docs

> `create_vector_db.py`를 다시 실행했다면 서버를 재시작해야 합니다.
> 임베딩, 챗봇 질문, 검색어 임베딩에는 OpenAI API 비용이 듭니다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/home` | 벡터 DB 상태 (`ready`가 false면 `create_vector_db.py` 실행 필요) |
| GET | `/api/search` | 유사도 검색 |
| POST | `/api/chat` | 챗봇 질문 `{"message": "..."}` → `{"answer": "마크다운", "tools_used": [...]}` |
| GET | `/api/chat/history` | 저장된 대화 조회 |
| DELETE | `/api/chat/history` | 대화 삭제 (새 대화), 응답 204 |

`/api/search` 파라미터

| 이름 | 설명 |
|---|---|
| `query` | 검색어 (필수, 1~500자) |
| `source_type` | `all` \| `Structured Data` \| `Unstructured Data` (기본 `all`) |
| `k` | 결과 수 1~10 (기본 5) |
| `min_price`, `max_price` | 가격 범위, 단위 만원 (지정하면 가격 미정 와인 제외) |
| `in_stock_only` | `true`이면 재고 있는 와인만 |

예: `/api/search?query=불고기&max_price=20&in_stock_only=true`

대화는 HttpOnly 쿠키 `wine_thread_id`로 구분되며, 챗봇 답변은 마크다운 원문으로 응답합니다.
오류는 JSON(`detail`)으로 응답합니다. (400, 403, 411, 413, 422, 429, 500, 502, 503)

## 환경 변수

`.env`에 지정하면 기본값 대신 사용됩니다. `OPENAI_API_KEY`만 필수입니다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `CORS_ORIGINS` | localhost, 127.0.0.1의 5173, 3000 포트 | 허용할 React 주소 (쉼표 구분, `*` 사용 시 서버 시작 거부) |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | 이 API 서버의 도메인 |
| `COOKIE_SECURE` | `false` | HTTPS 배포 시 `true` |
| `COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |
| `ENABLE_DOCS` | `true` | 배포 시 `false` (`/docs` 숨김) |
| `CHAT_RATE_LIMIT` | `20/minute` | IP별 챗봇 호출 제한 |
| `SEARCH_RATE_LIMIT` | `60/minute` | IP별 검색 호출 제한 |

## React 연동

**Vite 프록시 사용을 권장합니다.** 같은 주소로 호출하므로 CORS 문제가 없습니다.

```js
// vite.config.js
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: "http://127.0.0.1:8000" } } },
});
```

API를 직접 호출한다면 React와 API의 호스트 이름을 맞춰야 합니다.
(`127.0.0.1:5173` → `localhost:8000`은 쿠키가 전달되지 않아 질문마다 새 대화가 됩니다.)

`fetch`에는 반드시 `credentials: "include"`(axios는 `withCredentials: true`)를 지정해야 대화가 이어집니다.

```js
const response = await fetch("/api/chat", {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "불고기에 어울리는 와인 추천해줘" }),
});
```

챗봇 답변은 `react-markdown`으로 렌더링하고, `dangerouslySetInnerHTML`과 `rehype-raw`는 사용하지 않습니다.
API 키는 React(`VITE_` 변수 포함)에 두지 않습니다.

## 보안

- CORS: 등록한 주소만 허용, 오류 응답에도 CORS 헤더 포함
- CSRF: POST/DELETE의 Origin 검사, `SameSite` 쿠키, JSON 외 형식 거부
- HttpOnly 쿠키, 서버가 만든 uuid4 형식만 허용
- TrustedHost 검사, 보안 헤더(CSP, `X-Frame-Options`, `nosniff`, `no-store`)
- IP별 호출 제한, 질문당 LLM 호출 최대 6회, 요청 본문 32KB 제한
- 내부 오류 내용은 응답에 포함하지 않고 서버 로그에만 기록

## 배포 예시

React `https://wine.example.com`, API `https://api.example.com`

```
CORS_ORIGINS=https://wine.example.com
ALLOWED_HOSTS=api.example.com
COOKIE_SECURE=true
ENABLE_DOCS=false
```

```
uvicorn main:app --host 127.0.0.1 --port 8000 --no-server-header
```

HTTPS는 Nginx 같은 리버스 프록시에서 처리하고, 프록시 뒤에서는 `--proxy-headers --forwarded-allow-ips=<프록시 IP>`를 추가합니다.
서로 다른 사이트(예: `wine.com` ↔ `api.net`)라면 `COOKIE_SAMESITE=none`이 필요하지만, 가능하면 같은 도메인 프록시 구성을 권장합니다.

## 주의사항

- 로그인 기능이 없습니다. 호출 제한은 비용만 제어하므로 공개 시 로그인이나 OpenAI 사용 한도 설정을 검토하세요.
- 호출 제한은 서버 메모리에 저장됩니다. 재시작하면 초기화되고, 여러 서버로 운영하려면 Redis가 필요합니다.
- 지역 필터와 정렬("가장 저렴한 와인")은 지원하지 않으며, 음식 페어링은 의미 유사도 기준이라 정확하지 않을 수 있습니다.
  맛/음식 검색은 `source_type=Unstructured Data`가 더 정확합니다.
- 코드는 `backend` 폴더 기준으로 import 합니다. (PyCharm에서는 `backend`를 Sources Root로 지정)
