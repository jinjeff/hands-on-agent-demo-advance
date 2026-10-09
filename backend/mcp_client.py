"""MCP 客户端：两套传输，一个入口。

- 自建 mcp_server（简化协议）：GET /tools、POST /tools/{name}
  → class MCPClient
- 标准 MCP（JSON-RPC 2.0 over HTTP，RAGFlow 自带 MCP 的 /mcp 端点）：
  POST /mcp  {"jsonrpc":"2.0","method":"tools/list"|"tools/call", ...}
  → rpc() / call_tool_ragflow()

由 tools.py 的 search_contract 按 RAG_MODE 选择走哪一套，对上层（Agent / 前端）透明。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

DEFAULT_MCP_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8002")
DEFAULT_RAGFLOW_MCP_URL = os.environ.get("RAGFLOW_MCP_URL", "http://127.0.0.1:9382/mcp")


class MCPClient:
    """自建 mcp_server 的简化协议客户端（第四部分默认走这条）。"""

    def __init__(self, base_url: str = DEFAULT_MCP_URL):
        self.base_url = base_url.rstrip("/")

    def list_tools(self) -> list[dict]:
        import requests

        resp = requests.get(f"{self.base_url}/tools", timeout=20)
        resp.raise_for_status()
        return resp.json().get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        import requests

        resp = requests.post(
            f"{self.base_url}/tools/{name}",
            json={"arguments": arguments or {}},
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        contents = data.get("content", [])
        texts = [c["text"] for c in contents if c.get("type") == "text"]
        return "\n".join(texts) if texts else str(data)


def rpc(method: str, params: dict | None = None, timeout: int = 180) -> dict:
    """标准 MCP 的 JSON-RPC 调用（RAGFlow 自带 MCP 用这条）。

    RAGFlow 默认开 JSON 响应模式；若对方配了 --no-json-response，返回会是
    SSE 文本而不是 JSON，这里给出人话报错而不是让上层拿到一堆 event: 行。
    """
    import requests

    url = os.environ.get("RAGFLOW_MCP_URL", DEFAULT_RAGFLOW_MCP_URL).rstrip("/")
    resp = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"Accept": "application/json, text/event-stream"},
        timeout=timeout,
    )
    resp.raise_for_status()
    if resp.text.lstrip().startswith("event:"):
        raise RuntimeError(
            f"{url} 返回的是 SSE 帧而非 JSON——RAGFlow MCP 被配了 --no-json-response，"
            "请在 RAGFlow compose 的 MCP 参数里去掉该开关（默认即 JSON 模式）。"
        )
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"MCP {method} 失败: {data['error']}")
    return data.get("result", {})


def call_tool_ragflow(name: str, arguments: dict | None = None, timeout: int = 180) -> str:
    """标准 MCP 的 tools/call，抽出 text 内容并整理成与 tools_impl 一致的形状。

    RAGFlow MCP 的 ragflow_retrieval 直接把原始 JSON（含 content_ltks / positions /
    document_metadata 等大字段）塞进 text——原样喂给模型会瞬间撑爆上下文。这里按
    我们的格式压缩成「[序号] 出处：文档 / 第 X 页 + 正文」，和其他两种模式同形。
    """
    result = rpc("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout)
    contents = result.get("content", [])
    texts = [c["text"] for c in contents if c.get("type") == "text"]
    raw = "\n".join(texts) if texts else str(result)
    return _format_retrieval_json(raw)


def _format_retrieval_json(raw: str, max_chunks: int = 5) -> str:
    """把 RAGFlow retrieval 的原始 JSON 压缩成「[1] 出处：…\\n正文」形状。"""
    import json

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    chunks = data.get("chunks") if isinstance(data, dict) else None
    if not chunks:
        return raw

    lines = []
    for i, ck in enumerate(chunks[:max_chunks], 1):
        doc = ck.get("document_keyword") or "未知文档"
        pos = ck.get("positions") or []
        page = pos[0][0] if pos and isinstance(pos[0], (list, tuple)) and pos[0] else "?"
        sim = ck.get("similarity")
        sim_text = f"  sim={float(sim):.2f}" if isinstance(sim, (int, float)) else ""
        lines.append(f"[{i}] 出处：{doc} / 第 {page} 页{sim_text}\n{(ck.get('content') or '').strip()}")
    return "\n\n".join(lines)


def list_tools_ragflow(timeout: int = 20) -> list[dict]:
    return rpc("tools/list", {}, timeout=timeout).get("tools", [])
