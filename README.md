# 高级实战（P1–P6 合并版 · 进阶扩展基底）

本目录复制自 `01-总课程/实战`，内容与基础版完全一致，作为**进阶内容的开发基底**：后续多用户隔离、附件多模态、AI 网关等扩展都加在这里，不影响基础版。基础用法仍见 `实战步骤.md`；**进阶内容**：第七部分「多用户隔离」（身份/会话/本地记录三层隔离 + 八条 curl 验收）→ 第八部分「Workspace 与 Memory」（工作区卸载 + 按用户隔离的长期记忆 + 状态快照）。后续附件多模态、AI 网关生产形态等也加在这里。

六个阶段的实战代码**去重合并**后的唯一工程：配套文档是 `实战步骤.md`，从第一部分 P1 做到第六部分 P6，全程在这一个目录里完成，不在目录间复制代码。

## 合并规则（去重不去功能）

| 来源 | 去重方式 |
|---|---|
| P1 + P3 + P4 后端 | P4 后端本就是 P3 的超集，P1 回声以 `MODE=echo` 收进同一 `server.py`；**保留四个阶段全部可验证行为** |
| P1 + P3 前端 | P3 前端是 P1 的超集（同一套 MateChat 四层 + `useSSE.ts`），P4 的十行改动作为第四部分的一个动手小节 |
| P2 知识库 | 检索脚本 + 合同样本保留，改为直接打本机真实 RAGFlow（控制台 80 / API 9380） |
| P5 部署 | compose / 安全清单 / CI 样例保留，build 上下文改指向本目录 |
| P6 | 无独立代码，复用 backend + frontend，验收记录表保留 |

## 目录结构

```text
高级实战/
├── 实战步骤.md            # 合并版实战步骤（六个部分，大步骤分小节）
├── 验收记录表.md           # P6 总判定签字
├── README.md              # 本文件
├── docker-compose.yml     # P5 拓扑草图（config 校验用）
├── ci-cd.github-actions.yml
├── security-checklist.md  # 安全五条
├── frontend/              # Vue3 + @matechat/core（第三部分装一次 npm i，后续只用 npm run dev）
│   └── src/useSSE.ts      # SSE 流式解析（含中文乱码、半行 JSON 两个修法）
├── backend/               # 四种 MODE 的 SSE 后端（.venv 与 .env.example 都在这里）
│   ├── workspace_mgr.py   # 第八部分：工作区 + AgentRuntime 生命周期
│   ├── memory.py          # 第八部分：按用户隔离的长期记忆
│   └── ws.Dockerfile      # 第八部分：docker 工作区基础镜像（带 uv）
├── scripts/retrieve.py    # P2 三问检索（打真 RAGFlow /api/v1/retrieval）
└── 样本/                  # 采购合同（电子版 / 扫描件）
```

## 一张端口表

| 端口 | 服务 | 起它的阶段 |
|---|---|---|
| 5173 | frontend（vite） | P1 起，全程 |
| 8000 | backend 主服务 | 全程 |
| 80 / 9380 | RAGFlow 控制台 / API | 第二部分配好；第三、四部分经 MCP 复用 |
| 8001 | A2A Server | P4 |
| 8002 | MCP Server | P4 |

## 三分钟跑通（无 Key 保命路径）

```bash
# 终端 1：主服务（P1 回声）
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MODE=echo uvicorn server:app --reload --port 8000

# 终端 2：前端
cd frontend && npm install && npm run dev
```

浏览器开 `http://127.0.0.1:5173`，随便输入一句，应能看到气泡逐字出现「回声：…」。之后按 `实战步骤.md` 逐部分推进；第二部分起接入本机真实 RAGFlow（控制台 `http://127.0.0.1`，API `9380`）。

## 课前环境

Node 20+ / Python 3.11+（AgentScope 需要）/ Docker 可选。详见 `实战步骤.md` 第一部分「课前检查」。
