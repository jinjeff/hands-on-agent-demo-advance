"""P4 后端：装配合同问答 / 审查 Agent（人设 + MCP 工具 + A2A 子 Agent）。

与 P3 的区别：
  - search_contract / calc_penalty 不再直接调 RAGFlow，而是通过 MCP Client 调 mcp_server.py；
  - 新增 compliance_review，通过 A2A Client 委派给合规子 Agent。

第八部分进阶（workspace + memory）在 build_agent 的可选参数里：
  - offloader：工作区，超限工具结果落盘，上下文只留 workspace:// 引用（课件第 21 页）
  - middlewares：长期记忆（按 user_id 隔离，课件第 22 页）
  - context_config：压缩阈值与工具结果上限
  - workspace_tools：把工作区的 Read/Write/Bash 等内置工具也挂给 Agent

按 **AgentScope 2.0.8** API 编写。
"""

from __future__ import annotations

import os
from typing import Any

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool, Toolkit

from tools import calc_penalty, compliance_review, search_contract

SYS_PROMPT = """你是「采购合同问答助手」。只回答与这份采购合同有关的问题。

规则：
1. 涉及合同里的具体条款（付款期限、验收标准、违约金比例、金额、交付时间等），
   必须先调用 search_contract 拿到条款原文，再回答，并在答案末尾附上出处。
2. 涉及「逾期几天、违约金多少」这类计算，先用 search_contract 查到付款期限和违约金比例，
   再调用 calc_penalty 计算，不要自己心算。
3. 如果用户问「风险」「审一下合同」等审查类问题，先调用 search_contract 拿条款，
   再调用 compliance_review 做风险评估。
4. 查不到就明说「合同里没有约定」，不要编造。
5. 用简体中文，简洁作答。
6. 用户说「记住…」「我喜欢…」这类关于他本人的信息时，调用 remember_fact 记下来，
   以后同一用户再问起就能用上；不要替其他用户记任何事。
"""

# 课堂演示：工具默认允许执行，否则 2.0.8 会停下来等用户确认
_ALLOW = PermissionDecision(
    behavior=PermissionBehavior.ALLOW,
    message="P3 课堂工具，默认允许调用。",
)


def _build_model() -> OpenAIChatModel:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 OPENAI_API_KEY，无法创建真 Agent。")
    model_name = os.environ.get("OPENAI_MODEL", "qwen-plus")
    extra: dict | None = None
    # Qwen3 等带思维链的模型：打开 enable_thinking，前端才能收到 think 事件
    if os.environ.get("ENABLE_THINKING", "1") == "1" and "qwen3" in model_name.lower():
        extra = {"enable_thinking": True}
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        ),
        model=model_name,
        stream=True,
        extra_body=extra,
    )


def build_agent(
    *,
    uid: str = "anonymous",
    cid: str = "default",
    offloader: Any | None = None,
    middlewares: list | None = None,
    workspace_tools: bool = False,
) -> Agent:
    """装配 Agent。uid/cid 只用于日志与工作区定位，不参与模型调用。"""
    tools: list = [
        FunctionTool(search_contract, name="search_contract", permission=_ALLOW),
        FunctionTool(calc_penalty, permission=_ALLOW),
        FunctionTool(compliance_review, name="compliance_review", permission=_ALLOW),
    ]

    # 长期记忆：中间件本身 + 交给模型自己调用的 remember_fact 工具
    # （permission 必须显式 ALLOW，否则非交互请求里工具会被静默跳过）
    if middlewares:
        for mw in middlewares:
            if hasattr(mw, "as_tool"):
                tools.append(mw.as_tool(permission=_ALLOW))

    # 工作区内置工具（Read/Write/Bash…）：默认关，打开前先想清楚权限（课件第 20 页）
    if workspace_tools and offloader is not None:
        tools.extend(offloader.list_tools())

    toolkit = Toolkit(tools=tools)

    return Agent(
        name="contract_helper",
        system_prompt=SYS_PROMPT,
        model=_build_model(),
        toolkit=toolkit,
        middlewares=middlewares or None,
        offloader=offloader,
        react_config=ReActConfig(max_iters=50),
        # 课件第 22 页的三个默认值：到 80% 压缩、留 10% 给摘要、工具结果超 5 万 token 卸载
        context_config=ContextConfig(
            trigger_ratio=0.8,
            reserve_ratio=0.1,
            tool_result_limit=50000,
        ),
    )


if __name__ == "__main__":
    import asyncio

    from agentscope.message import UserMsg

    async def _demo() -> None:
        agent = build_agent()
        reply = await agent.reply(UserMsg(name="user", content="这份合同的付款期限是多久？"))
        print(reply.get_text_content())

    asyncio.run(_demo())
