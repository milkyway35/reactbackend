# React 연동을 위한 CORS, 보안 설정

import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from common.config import ALLOWED_HOSTS, COOKIE_SECURE, CORS_ORIGINS, MAX_BODY_BYTES

logger = logging.getLogger(__name__)

# IP별 호출 횟수 제한 : 라우터에서 @limiter.limit(...) 로 사용 (OpenAI 비용 보호)
limiter = Limiter(key_func=get_remote_address)


# 호출 제한 초과 응답 : Retry-After 로 다시 시도할 수 있는 최대 대기 시간(초)을 알려줌
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
        headers={"Retry-After": str(exc.limit.limit.get_expiry())}
    )


# 모든 응답에 보안 헤더 추가
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    # JSON API는 스크립트, 이미지 등을 불러올 일이 없음 (/docs 화면만 외부 스크립트가 필요)
    if not request.url.path.startswith(("/docs", "/redoc")):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # HTTPS 배포에서만 의미가 있는 헤더
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


# 처리되지 않은 오류를 JSON으로 응답
# 오류가 CORS 미들웨어 바깥까지 나가면 CORS 헤더가 없는 응답이 되어,
# React에서는 실제 오류 대신 CORS 오류로 보이므로 CORS 미들웨어 안쪽에서 처리함
async def catch_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("처리되지 않은 오류: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."})


# 데이터를 변경하는 요청 검사 : 다른 사이트에서 보낸 요청(CSRF) 차단, 요청 크기 제한
async def check_request(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # 브라우저는 다른 출처로 보내는 POST, DELETE에 Origin을 항상 붙임 (자바스크립트로 변경 불가)
        # 같은 출처 요청(/docs 화면 등)과 Origin이 없는 요청(curl 등 브라우저가 아닌 호출)은 CSRF 대상이 아님
        origin = request.headers.get("origin")
        if origin and origin not in CORS_ORIGINS and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse(status_code=403, content={"detail": "허용되지 않은 출처의 요청입니다."})

        # 크기를 알 수 없는 요청은 받지 않음 (브라우저 fetch, axios는 항상 Content-Length를 보냄)
        if "transfer-encoding" in request.headers:
            return JSONResponse(status_code=411, content={"detail": "Content-Length가 필요합니다."})
        if int(request.headers.get("content-length", 0)) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "요청 크기가 너무 큽니다."})

    return await call_next(request)


# 앱에 보안 설정 적용
def setup_security(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # add_middleware는 나중에 추가한 것이 바깥쪽이므로, 요청은 아래쪽 미들웨어부터 통과함
    # 보안 헤더 → 호스트 검사 → CORS → 오류 처리 → 요청 검사 → 라우터
    app.add_middleware(BaseHTTPMiddleware, dispatch=check_request)
    app.add_middleware(BaseHTTPMiddleware, dispatch=catch_errors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,                     # 대화 구분용 쿠키를 주고받기 위해 필요
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["Retry-After"],             # 429 응답의 대기 시간을 React에서 읽을 수 있게 함
        max_age=600                                 # 사전 요청(OPTIONS) 결과를 10분간 재사용
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    app.add_middleware(BaseHTTPMiddleware, dispatch=add_security_headers)
