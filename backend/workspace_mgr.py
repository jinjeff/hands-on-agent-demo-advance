"""Workspace 管理（第八部分）：按 (user, conversation) 开工作区，并持有一条 Agent 运行时。

- WORKSPACE_BACKEND=local（默认，零依赖）| docker（需要 Docker + 镜像）
- 目录：{DATA_DIR}/workspaces/{user}/{conversation}/，其下 data/ skills/ sessions/
  由 AgentScope 的 Workspace 自管（课件第 21 页的目录约定）
- 作用一：offloader——超限的工具结果/上下文被写到 sessions/，对话里只留 workspace:// 引用
- 作用二：可选把工作区内置工具（Read/Write/Bash…）挂给 Agent（WS_BUILTIN_TOOLS=1）
- 生命周期：initialize() 后连 Agent 一起缓存；reset 时 close()，别留孤儿进程
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
BACKEND = os.environ.get("WORKSPACE_BACKEND", "local").strip().lower()
BUILTIN_TOOLS = os.environ.get("WS_BUILTIN_TOOLS", "0") == "1"


def workspace_dir(user_id: str, conversation_id: str) -> Path:
    return DATA_DIR / "workspaces" / user_id / conversation_id


async def open_workspace(user_id: str, conversation_id: str):
    """开一个工作区并 initialize。local 后端零依赖；docker 后端失败时抛错由调用方兜底。"""
    wdir = workspace_dir(user_id, conversation_id)
    wdir.mkdir(parents=True, exist_ok=True)

    if BACKEND == "docker":
        from agentscope.workspace import DockerWorkspace

        ws = DockerWorkspace(
            base_image=os.environ.get("WS_IMAGE", "python:3.12-slim"),
            host_workdir=str(wdir),
            env={"TZ": "Asia/Shanghai"},
            skill_paths=[str(wdir / "skills")],
        )
    else:
        from agentscope.workspace import LocalWorkspace

        ws = LocalWorkspace(
            workdir=str(wdir),
            workspace_id=f"{user_id}:{conversation_id}",
            skill_paths=[str(wdir / "skills")],
        )
    await ws.initialize()
    return ws


@dataclass
class AgentRuntime:
    """一个 (用户, 会话) 的完整运行时：Agent + 工作区 + 记忆中间件。"""

    agent: Any
    workspace: Any
    user_id: str
    conversation_id: str
    workdir: Path | None = None        # 工作区根目录（快照/文件清单用）
    closed: bool = False
    meta: dict = field(default_factory=dict)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            await self.workspace.close()
        except Exception:  # noqa: BLE001  关闭失败不该炸掉请求
            pass

    def snapshot_state(self) -> str:
        """把 AgentState 存到 data/sessions/{user}/{conversation}/ 下（课件第 39 页）。

        为什么不写进工作区目录：docker 后端下工作区是容器里 root 建的，
        宿主机进程再往里写会 PermissionError——快照是我们的元数据，放自己的目录。
        """
        sid = getattr(getattr(self.agent, "state", None), "session_id", None) or "snapshot"
        out = DATA_DIR / "sessions" / self.user_id / self.conversation_id / f"{sid}.json"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(self.agent.state.model_dump_json(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            # 别再静默吞：快照失败要能在日志里看见（课堂排障）
            import logging

            logging.getLogger("workspace").warning("快照失败 %s: %r", out, exc)
            return ""
        return str(out)
