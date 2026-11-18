# agent 구성 및 생성 파일 (fastapiproject agent_builder.py 재사용)
import logging

from langchain.agents.middleware import ModelCallLimitMiddleware, wrap_tool_call
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from common.config import MODEL_NAME, TEMPERATURE, OPENAI_TIMEOUT, AGENT_MODEL_CALL_LIMIT, SYSTEM_PROMPT, DB_PATH
from chat.wine_tools import search_wine
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
from langchain_community.tools import YouTubeSearchTool

logger = logging.getLogger(__name__)


# 도구 실행 중 오류가 나도 대화가 끊기지 않도록 오류를 도구 결과로 돌려줌
# 오류 내용에는 API 키 일부 등이 포함될 수 있어 LLM(답변)에 전달하지 않고 로그에만 남김
@wrap_tool_call
async def handle_tool_errors(request, handler):
    try:
        return await handler(request)
    except Exception:
        logger.exception("도구 실행 오류: %s", request.tool_call["name"])
        return ToolMessage(content="도구 실행 중 오류가 발생했습니다.",
                           tool_call_id=request.tool_call["id"], status="error")


# 질문 1개당 LLM 호출 횟수 제한 (기본 제한이 9999단계라 도구 호출이 반복되면 비용이 계속 발생함)
# 도구 실행이 끝난 뒤 LLM 호출 직전에 멈추므로 제한에 걸려도 같은 대화를 이어서 사용할 수 있음
class WineCallLimit(ModelCallLimitMiddleware):
    def before_model(self, state, runtime):
        result = super().before_model(state, runtime)
        if result:
            result["messages"] = [AIMessage(content="질문을 처리하는 데 단계가 너무 많이 필요합니다. 질문을 나눠서 다시 물어봐 주세요.")]
        return result


#1. 에이전트 생성
async def create_wine_agent():
    conn = await aiosqlite.connect(DB_PATH)
    checkpointer = AsyncSqliteSaver(conn)

    model = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE, timeout=OPENAI_TIMEOUT)

    # youtube 도구 구해오기
    youtube_tool = YouTubeSearchTool()

    # 모든 도구 합치기
    all_tools = [search_wine, youtube_tool]

    # 에이전트 생성
    agent = create_agent(
        model = model,
        tools = all_tools,
        checkpointer = checkpointer,
        system_prompt = SYSTEM_PROMPT,
        middleware = [handle_tool_errors, WineCallLimit(run_limit=AGENT_MODEL_CALL_LIMIT)]
    )

    return agent


#2. 에이전트 실행 : 최종 답변과 사용한 도구 이름을 반환
async def run_agent(agent, query, thread_id):
    full_response = ""
    tools_used = []
    config = {"configurable":{"thread_id":thread_id}}

    async for chunk in agent.astream(
        {"messages":[{"role": "user", "content": query}]},
        config=config,
        stream_mode="values"
    ):
        if "messages" not in chunk:
            continue

        latest_msg = chunk["messages"][-1]

        if isinstance(latest_msg, AIMessage):
            if latest_msg.tool_calls:
                tools_used += [call["name"] for call in latest_msg.tool_calls]
            elif latest_msg.text:
                full_response = latest_msg.text

    # WAL 파일에 쌓인 대화 내용을 wine_chat.db 본 파일로 반영
    await agent.checkpointer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    return full_response, list(dict.fromkeys(tools_used))


#3. 저장된 대화 조회 : 사용자 질문과 최종 답변만 반환
async def get_chat_history(agent, thread_id):
    state = await agent.aget_state({"configurable":{"thread_id":thread_id}})

    history = []
    for msg in state.values.get("messages", []):
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.text})
        elif isinstance(msg, AIMessage) and msg.text and not msg.tool_calls:
            history.append({"role": "assistant", "content": msg.text})
    return history


#4. 저장된 대화 삭제
async def delete_chat_history(agent, thread_id):
    await agent.checkpointer.adelete_thread(thread_id)
