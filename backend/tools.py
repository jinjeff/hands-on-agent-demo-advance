"""P3/P4 工具入口：同一个 search_contract，三条检索链路按 RAG_MODE 路由。

RAG_MODE（环境变量，改完重启生效）：
    api          P3 直连：tools_impl.search_contract_impl 直接 POST RAGFlow /api/v1/retrieval
    mcp          走本仓 mcp_server.py 暴露的 search_contract（第四部分默认）
    ragflow-mcp  走 RAGFlow 自带 MCP（标准 JSON-RPC，端口 9382，需按其 compose 开启）

三条链路对上层（Agent / 前端）完全透明：模型看到的工具名永远只有一个
search_contract，换传输不改 Agent、不改 SSE、不改前端。
calc_penalty 始终是本地函数（RAGFlow MCP 只暴露检索，不暴露计算）。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from mcp_client import MCPClient, call_tool_ragflow  # noqa: E402
from tools_impl import search_contract_impl  # noqa: E402

DEFAULT_MCP_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8002")

RAG_MODE = os.environ.get("RAG_MODE", "mcp").strip().lower()
RAGFLOW_MCP_TOOL = os.environ.get("RAGFLOW_MCP_TOOL", "ragflow_retrieval")
RAGFLOW_DATASET_ID = os.environ.get("RAGFLOW_DATASET_ID", "")


def search_contract(question: str) -> str:
    """检索采购合同知识库，返回与问题最相关的条款原文以及出处（文档名、页码）。

    Args:
        question: 用户的自然语言问题，例如「付款期限是多久」。
    """
    if RAG_MODE == "api":
        # 第三部分：直连 RAGFlow REST，不经过任何中间层
        return search_contract_impl(question)

    if RAG_MODE == "ragflow-mcp":
        # 第四部分备选：RAGFlow 自带 MCP（标准协议），工具名与参数由 RAGFlow 定
        args: dict = {"question": question}
        if RAGFLOW_DATASET_ID:
            args["dataset_ids"] = [RAGFLOW_DATASET_ID]
        return call_tool_ragflow(RAGFLOW_MCP_TOOL, args)

    # 第四部分默认：本仓 mcp_server（简化 MCP）
    return MCPClient().call_tool("search_contract", {"question": question})


def calc_penalty(
    due_date: str,
    paid_date: str,
    total_amount: float,
    daily_rate: float = 0.0005,
) -> str:
    """通过 MCP 调用远程计算工具。"""
    return MCPClient().call_tool(
        "calc_penalty",
        {
            "due_date": due_date,
            "paid_date": paid_date,
            "total_amount": total_amount,
            "daily_rate": daily_rate,
        },
    )


def compliance_review(input_text: str, clauses: str) -> str:
    """通过 A2A 调用合规子 Agent（可选，用于风险审查场景）。

    这个函数不经过 MCP，而是走 A2A 协议。保留在这里是为了让 agent.py 的 Toolkit 注册更简单。
    """
    from a2a_client import A2AClient

    result = A2AClient().send_task(input_text, context={"clauses": clauses})
    artifacts = result.get("artifacts", [])
    if not artifacts:
        return "合规 Agent 未返回结果。"
    import json

    return json.dumps(artifacts[0].get("content", {}), ensure_ascii=False)


if __name__ == "__main__":
    print(f"RAG_MODE = {RAG_MODE}")
    print("=== search_contract ===")
    print(search_contract("付款期限多久"))
    print("\n=== calc_penalty ===")
    print(calc_penalty("2024-11-09", "2024-11-20", 186000))
