"""用真实图状态验证待办更新发生在执行结束之前。"""

import asyncio
import pytest
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode

from yuxi.agents.base import BaseAgent
from yuxi.agents.context import BaseContext


@pytest.mark.asyncio
async def test_root_todo_state_is_streamed_before_next_stage_finishes():
    """节点状态更新必须实时可见，不能只等最终 checkpoint。"""
    release, observed, work_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class State(MessagesState):
        """保留真实待办字段。"""

        todos: list

    async def plan(state):
        """构造确定的工具调用，使用生产待办工具写入阶段状态。"""
        return {
            "messages": [
                AIMessage(
                    "",
                    tool_calls=[
                        {
                            "id": "todo-plan",
                            "name": "write_todos",
                            "args": {"todos": [{"content": "核验材料", "status": "in_progress"}]},
                        }
                    ],
                )
            ]
        }

    async def work(state):
        """在测试允许之前不结束下一阶段。"""
        work_started.set()
        await release.wait()
        return {
            "messages": [
                AIMessage(
                    "",
                    tool_calls=[
                        {
                            "id": "todo-complete",
                            "name": "write_todos",
                            "args": {"todos": [{"content": "核验材料", "status": "completed"}]},
                        }
                    ],
                )
            ]
        }

    builder = StateGraph(State)
    builder.add_node("plan", plan)
    tools = TodoListMiddleware().tools
    builder.add_node("start_todos", ToolNode(tools))
    builder.add_node("work", work)
    builder.add_node("finish_todos", ToolNode(tools))
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "start_todos")
    builder.add_edge("start_todos", "work")
    builder.add_edge("work", "finish_todos")
    builder.add_edge("finish_todos", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    class Agent(BaseAgent):
        """复用生产事件转换，执行本测试的真实图。"""

        async def get_graph(self, **kwargs):
            """返回真实图。"""
            return graph

    updates = []

    async def consume():
        """执行中采集完整待办快照。"""
        async for mode, data in Agent().stream_messages_with_state(
            ["整理材料"], context=BaseContext(thread_id="todo-test", uid="test-user")
        ):
            if mode == "values" and data.get("todos"):
                updates.append(data["todos"])
                observed.set()

    consumer = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(observed.wait(), 3)
        await asyncio.wait_for(work_started.wait(), 3)
        assert not consumer.done()
        assert updates[-1][0]["status"] == "in_progress"
        release.set()
        await asyncio.wait_for(consumer, 3)
        assert updates[-1][0]["status"] == "completed"
    finally:
        release.set()
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
