"""P4 MCP Server：暴露 search_contract / calc_penalty 两个工具。

本服务可以单独启动（默认 8002），也可以被 P4 主 Agent 通过 MCP Client 调用。
HTTP 传输语义与 MCP 一致：
  - GET  /tools           -> list_tools
  - POST /tools/{name}    -> call_tool
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from tools_impl import calc_penalty_impl, search_contract_impl

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="P4 MCP Server", version="1.0.0")

TOOLS = [
    {
        "name": "search_contract",
        "description": "检索采购合同知识库，返回与问题最相关的条款原文以及出处（文档名、页码）。当用户问到合同里的具体条款——付款期限、验收标准、违约金比例、金额、交付时间等——时调用本工具，拿到原文后再回答，并附上出处。不要凭记忆编造。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "用户的自然语言问题，例如「付款期限是多久」。",
                }
            },
            "required": ["question"],
        },
    },
    {
        "name": "calc_penalty",
        "description": "计算逾期天数与违约金。用于「如果某天才付款，逾期几天、违约金多少」这类问题。通常在先用 search_contract 查到付款期限和违约金比例之后调用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "due_date": {"type": "string", "description": "应付款日期，格式 YYYY-MM-DD。"},
                "paid_date": {"type": "string", "description": "实际付款日期，格式 YYYY-MM-DD。"},
                "total_amount": {"type": "number", "description": "合同含税总价，单位元。"},
                "daily_rate": {"type": "number", "description": "日违约金比例，默认 0.0005（每日万分之五）。", "default": 0.0005},
            },
            "required": ["due_date", "paid_date", "total_amount"],
        },
    },
]


class CallToolReq(BaseModel):
    arguments: dict = Field(default_factory=dict)


@app.get("/tools")
def list_tools() -> dict:
    return {"tools": TOOLS}


@app.post("/tools/{name}")
def call_tool(name: str, req: CallToolReq) -> dict:
    tool_names = {t["name"] for t in TOOLS}
    if name not in tool_names:
        raise HTTPException(status_code=404, detail=f"unknown tool: {name}")

    args = req.arguments or {}
    if name == "search_contract":
        result = search_contract_impl(args.get("question", ""))
    elif name == "calc_penalty":
        result = calc_penalty_impl(
            due_date=args.get("due_date", ""),
            paid_date=args.get("paid_date", ""),
            total_amount=args.get("total_amount", 0),
            daily_rate=args.get("daily_rate", 0.0005),
        )
    else:
        raise HTTPException(status_code=400, detail=f"not implemented: {name}")

    return {
        "content": [{"type": "text", "text": result}],
        "isError": False,
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mode": "mcp", "tools": [t["name"] for t in TOOLS]}


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8002"))
    print(f"启动 MCP Server：http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
