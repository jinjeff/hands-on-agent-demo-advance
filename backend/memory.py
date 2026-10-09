"""长期记忆（第八部分）：按 user_id 隔离的事实库。

两种实现，用 MEMORY 环境变量切：
    file   （默认）JSON 文件事实库，完全离线——课堂保命路径
    mem0   Mem0Middleware（需要 pip install mem0ai + 模型 Key）
    none   不挂记忆

设计要点：
  - 检索走 on_system_prompt 钩子（签名稳定、同步、无流式解析风险）：把该用户的事实
    注入系统提示，模型自然会用；
  - 写入走 remember_fact 工具（agent_control 模式）：由模型在用户说「记住…」时调用，
    避免去猜 on_reply 的 input_kwargs 形状——生产可换 Mem0 的自动抽取；
  - 一切按 user_id 分文件：换用户 = 换记忆，这是第七部分隔离的延伸。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agentscope.middleware import MiddlewareBase

load_dotenv(Path(__file__).with_name(".env"))

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
MEMORY_MODE = os.environ.get("MEMORY", "file").strip().lower()
MAX_FACTS = int(os.environ.get("MEMORY_MAX_FACTS", "30"))


def _safe_name(uid: str) -> str:
    """user_id 可能带奇怪字符，落盘前洗成安全文件名。"""
    keep = re.sub(r"[^A-Za-z0-9_-]", "_", uid)[:40]
    if keep != uid:                      # 洗掉了信息就加个短哈希防碰撞
        keep += "_" + hashlib.md5(uid.encode()).hexdigest()[:6]
    return keep


class FileMemoryMiddleware(MiddlewareBase):
    """最小可用的长期记忆：on_system_prompt 注入 + remember_fact 工具写入。

    必须继承 MiddlewareBase——AgentScope 靠它提供的 is_implemented() 判断
    「这个中间件实现了哪些钩子」，普通类会直接报没有该属性。
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.path = DATA_DIR / "memory" / f"{_safe_name(user_id)}.json"
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---- 存储 ----
    def _load(self) -> list[str]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("facts", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, facts: list[str]) -> None:
        self.path.write_text(
            json.dumps({"user_id": self.user_id, "facts": facts}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def remember(self, fact: str) -> str:
        fact = (fact or "").strip()
        if not fact:
            return "空事实，未记录。"
        with self._lock:
            facts = self._load()
            if fact in facts:
                return f"已知晓：{fact}"
            facts.append(fact)
            self._save(facts[-MAX_FACTS:])
        return f"已记住：{fact}"

    def recall(self, query: str = "", top_k: int = 8) -> list[str]:
        facts = self._load()
        if not query:
            return facts[-top_k:]
        # 极简相关度：字符二元组重合数（生产换向量检索）
        q = re.sub(r"\s+", "", query)
        grams = {q[i : i + 2] for i in range(len(q) - 1)} or {q}
        scored = sorted(facts, key=lambda f: -sum(1 for g in grams if g in f))
        return [f for f in scored[:top_k] if any(g in f for g in grams)] or facts[-3:]

    # ---- AgentScope 中间件钩子（签名与 MiddlewareBase 一致）----
    # 注意：on_system_prompt 在 AgentScope 里是 async 钩子（内部 await mw.on_system_prompt(...)），
    # 写成同步方法会在 reply 时报 "object str can't be used in 'await' expression"
    async def on_system_prompt(self, agent: Any, current_prompt: str) -> str:
        facts = self.recall()
        if not facts:
            return current_prompt
        lines = "\n".join(f"- {f}" for f in facts)
        return (current_prompt +
                f"\n\n## 关于当前用户（{self.user_id}）的已知信息\n{lines}\n"
                "以上信息来自该用户此前的对话，与当前问题相关时才使用。")

    def as_tool(self, permission: Any | None = None):
        """包成 FunctionTool 交给模型自己调（agent_control）。

        permission 必须显式给 ALLOW——2.0.8 默认会停下来等人工确认，
        非交互的 SSE 请求里就变成「工具静默不执行、答案空手而归」。
        """
        from agentscope.tool import FunctionTool

        mw = self

        def remember_fact(fact: str) -> str:
            """把关于当前用户的长期事实记下来，跨会话生效。

            Args:
                fact: 一条简洁的事实，例如「用户喜欢简洁的回答」「用户在负责 P2 知识库」。
            """
            return mw.remember(fact)

        return FunctionTool(remember_fact, name="remember_fact", permission=permission)


def build_memory(user_id: str):
    """按 MEMORY 环境变量装配记忆中间件；返回 (middleware_or_None, extra_tools)。"""
    if MEMORY_MODE == "none":
        return None, []
    if MEMORY_MODE == "file":
        mw = FileMemoryMiddleware(user_id)
        return mw, [mw.as_tool()]
    if MEMORY_MODE == "mem0":
        try:
            from agentscope.embedding import DashScopeEmbeddingModel
            from agentscope.middleware import Mem0Middleware
            from agentscope.model import OpenAIChatModel

            from agent import _build_model
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"MEMORY=mem0 需要额外依赖（{exc}）。先 `pip install mem0ai`，"
                "并把模型 Key 配进 .env；或把 MEMORY 改回 file。"
            ) from exc
        mw = Mem0Middleware(
            user_id=user_id,
            chat_model=_build_model(),
            embedding_model=DashScopeEmbeddingModel(
                os.environ.get("DASHSCOPE_API_KEY", ""),
                "text-embedding-v4",
                1024,
            ),
            mode="both",
            top_k=5,
        )
        return mw, []
    raise RuntimeError(f"MEMORY 只能是 file / mem0 / none，当前是 {MEMORY_MODE!r}")
