# 实战后端：一个 backend 覆盖 P1–P6（MODE 开关）

本目录是六个阶段实战代码去重合并后的**唯一后端**：P4 的代码本就是 P3 的超集（P4 = P3 + MCP/A2A），P1 的回声服务以 `MODE=echo` 收进同一个 `server.py`。按 `实战步骤.md` 从 P1 做到 P6，全程只在这一个目录里操作，不用在目录间复制代码。

## 四种运行模式

| MODE | 对应阶段 | 行为 | 需要 Key |
|---|---|---|---|
| `echo`（默认） | P1 | SSE 回声：先通水管 | 否 |
| `p3` | P3 | 离线两轮 ReAct mock（`mock_retrieval.plan`） | 否 |
| `p4` | P4 | 离线 MCP 检索 + A2A 委派 mock | 否 |
| `agent` | P3-D / P4-G / P6 | 真 AgentScope 2.0.8 Agent | 模型 Key |

改模式只改一处：`backend/.env` 里的 `MODE=...`，或启动前 `export MODE=p4`。
`/api/health` 会回带当前模式：`echo` / `p3-mock` / `p4-mock` / `agent`。

## 端口表

| 服务 | 端口 | 何时起 |
|---|---|---|
| RAGFlow API（P2 配好） | 9380 | 第二部分从控制台配 Embedding + Key；MCP Server 经它检索 |
| 主服务 server.py | 8000 | 全程 |
| A2A Server | 8001 | P4 实验 B–D |
| MCP Server | 8002 | P4 实验 B–D |
| 前端 vite | 5173 | P1 起 |

## 文件说明

| 文件 | 作用 | 新增于 |
|---|---|---|
| `server.py` | FastAPI + SSE 主服务（含 echo / p3 / p4 / agent 四种流） | P1 起持续演进 |
| `tools.py` | 工具入口：`search_contract` 走 MCP Client，`compliance_review` 走 A2A Client | P4 |
| `tools_impl.py` | 工具实际实现：直接调 RAGFlow / 本地计算（即 P3 的 tools.py 原样搬来，函数名加 `_impl`） | P4 |
| `mcp_server.py` / `mcp_client.py` | MCP Server / Client（`GET /tools`、`POST /tools/{name}`） | P4 |
| `a2a_server.py` / `a2a_client.py` | A2A Server（Agent Card、`POST /tasks/send`）/ Client | P4 |
| `agent.py` | AgentScope Agent 装配（MODE=agent 才 import） | P3 |
| `mock_retrieval.py` | P3 离线两轮 ReAct 脚本（MODE=p3 用） | P3 |
| `list_datasets.py` | 列出 RAGFlow 知识库名称和 id | P3 |
| `test_retrieval.py` / `test_mcp.py` / `test_a2a.py` | 三类服务的连通性自检 | P3 / P4 |

## 快速启动

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # Windows: copy .env.example .env

MODE=echo uvicorn server:app --reload --port 8000   # P1：通水管
MODE=p3   uvicorn server:app --reload --port 8000   # P3：两轮 ReAct mock
MODE=p4   python mcp_server.py & python a2a_server.py & MODE=p4 python server.py   # P4
```

验证：

```bash
curl http://127.0.0.1:8000/api/health    # {"ok": true, "mode": "echo"}
curl http://127.0.0.1:8002/tools         # MCP 工具列表
curl http://127.0.0.1:8001/.well-known/agent.json   # A2A Agent Card
```

> 装了 `agentscope`（需 Python 3.11+）才能 `MODE=agent`；mock 三个模式只需要 `requirements.txt` 里的基础依赖。
