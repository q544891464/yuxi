"""现有子 Run 生命周期中的事实证据审查执行图。"""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from yuxi.agents import BaseAgent, BaseState
from yuxi.agents.backends import create_agent_composite_backend
from yuxi.agents.buildin.subagent.context import SubAgentContext
from yuxi.agents.context import prepare_agent_runtime_context
from yuxi.models.chat import load_chat_model, resolve_chat_model_spec

from .prompt import CALL_DESCRIPTION
from .review import review_evidence
from .schema import parse_review_input


class EvidenceReviewContext(SubAgentContext):
    """专业岗位仅暴露实际使用的模型配置。"""

    @classmethod
    def get_configurable_items(cls, user_role=None):
        """固定职责提示词和只读工具边界，避免展示无效配置。"""
        items = super().get_configurable_items(user_role=user_role)
        return {"model": items["model"]} if "model" in items else {}


class EvidenceReviewSubagent(BaseAgent):
    """只由主智能体调度的事实证据专业岗位。"""

    name = "事实证据审查子智能体"
    description = CALL_DESCRIPTION
    capabilities = ["files"]
    context_schema = EvidenceReviewContext

    async def get_graph(self, context=None, **kwargs):
        """复用平台模型、文件后端与 PostgreSQL checkpoint。"""
        context = await prepare_agent_runtime_context(
            context or self.context_schema(), context_schema=self.context_schema
        )
        if not context.is_subagent_runtime:
            raise ValueError("事实证据审查子智能体必须由主 Agent 调用。")
        backend = create_agent_composite_backend(context)
        model = load_chat_model(
            fully_specified_name=resolve_chat_model_spec(context.model), session_id=context.thread_id
        )

        async def review(state):
            """从本次用户消息校验输入，仅把验证通过的结果写入子 Run。"""
            message = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
            if message is None or not isinstance(message.content, str):
                raise ValueError("请在 task.description 中传入 EvidenceReviewInput JSON 字符串。")
            request = parse_review_input(message.content)
            result = await review_evidence(request, model, backend)
            return {"messages": [AIMessage(content=result.model_dump_json())]}

        graph = StateGraph(BaseState)
        graph.add_node("fact_evidence_review", review)
        graph.add_edge(START, "fact_evidence_review")
        graph.add_edge("fact_evidence_review", END)
        return graph.compile(checkpointer=await self._get_checkpointer())
