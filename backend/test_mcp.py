"""MCP 连通性自检。

    python test_mcp.py              # 自建 mcp_server（默认）
    python test_mcp.py --ragflow    # RAGFlow 自带 MCP（需先按 4.7.1 开启，端口 9382）
"""

from __future__ import annotations

import sys

from mcp_client import MCPClient, call_tool_ragflow, list_tools_ragflow


def main() -> int:
    if "--ragflow" in sys.argv:
        tools = list_tools_ragflow()
        print("RAGFlow MCP tools:", [t["name"] for t in tools])
        print("---")
        print(call_tool_ragflow("ragflow_retrieval", {"question": "付款期限多久"}))
        return 0

    client = MCPClient()
    print("tools:", [t["name"] for t in client.list_tools()])
    print("---")
    print(client.call_tool("search_contract", {"question": "付款期限多久"}))
    print("---")
    print(client.call_tool("calc_penalty", {
        "due_date": "2024-11-09",
        "paid_date": "2024-11-20",
        "total_amount": 186000,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
