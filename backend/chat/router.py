# 와인 챗봇 기능 : JSON API (API는 http://localhost:8000/docs 에서 테스트 가능)

import logging
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from openai import OpenAIError

from chat.agent_builder import delete_chat_history, get_chat_history, run_agent
from chat.schemas import ChatMessage, ChatRequest, ChatResponse
from common.config import CHAT_RATE_LIMIT, COOKIE_SAMESITE, COOKIE_SECURE
from common.security import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

THREAD_COOKIE = "wine_thread_id"
THREAD_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


# 브라우저별로 대화를 구분 : 서버가 만든 값(uuid4)만 사용하고, 형식이 다른 쿠키는 새로 발급함
# HttpOnly 쿠키는 자바스크립트에서 읽을 수 없으므로 React 쪽 XSS로 대화 id가 유출되지 않음
def get_thread_id(request: Request, response: Response):
    thread_id = request.cookies.get(THREAD_COOKIE)
    if not thread_id or not THREAD_ID_PATTERN.fullmatch(thread_id):
        thread_id = uuid4().hex
        response.set_cookie(
            THREAD_COOKIE,
            thread_id,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=60 * 60 * 24 * 30,
            path="/api"
        )
    return thread_id


# 챗봇 질문
@router.post("/api/chat", response_model=ChatResponse, tags=["chat"])
@limiter.limit(CHAT_RATE_LIMIT)
async def chat(request: Request, body: ChatRequest, thread_id: str = Depends(get_thread_id)):
    try:
        answer, tools_used = await run_agent(request.app.state.agent, body.message, thread_id)
    except OpenAIError:
        logger.exception("에이전트 실행 실패")
        raise HTTPException(status_code=502, detail="AI 모델 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.")

    answer = answer or "답변을 생성하지 못했습니다. 질문을 바꿔서 다시 시도해 주세요."
    return {"answer": answer, "tools_used": tools_used}


# 저장된 대화 조회 (새로고침해도 대화 유지)
@router.get("/api/chat/history", response_model=list[ChatMessage], tags=["chat"])
async def chat_history(request: Request, thread_id: str = Depends(get_thread_id)):
    return await get_chat_history(request.app.state.agent, thread_id)


# 저장된 대화 삭제 (새 대화)
@router.delete("/api/chat/history", status_code=204, tags=["chat"])
async def clear_chat_history(request: Request, thread_id: str = Depends(get_thread_id)):
    await delete_chat_history(request.app.state.agent, thread_id)
