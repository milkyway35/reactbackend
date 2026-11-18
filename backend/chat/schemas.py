# 와인 챗봇 API 요청/응답 스키마
# 답변은 마크다운 원문으로 내려주고 React에서 react-markdown으로 렌더링함
# (서버에서 만든 HTML을 dangerouslySetInnerHTML로 넣으면 XSS 위험이 있으므로 html 필드는 제공하지 않음)

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
