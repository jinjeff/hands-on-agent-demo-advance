"""P3 后端工具：RAGFlow 检索 + 违约金计算。

AgentScope 2.0.8 的 FunctionTool **只认 str / ToolChunk**，不认 ToolResponse。
返回普通字符串即可，框架会包成给模型看的工具结果。
"""

from __future__ import annotations

import datetime as _dt
import os

import requests


def search_contract_impl(
    question: str,
    *,
    api_key: str = "",
    base_url: str = "",
    dataset_id: str = "",
    top_k: int = 6,
) -> str:
    """检索采购合同知识库，返回与问题最相关的条款原文以及出处（文档名、页码）。

    当用户问到合同里的**具体条款**——付款期限、验收标准、违约金比例、金额、
    交付时间等——时调用本工具，拿到原文后再回答，并附上出处。不要凭记忆编造。

    Args:
        question (str): 用户的自然语言问题，例如「付款期限是多久」。
    """
    api_key = api_key or os.environ.get("RAGFLOW_API_KEY", "")
    base_url = (base_url or os.environ.get("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")).rstrip("/")
    dataset_id = dataset_id or os.environ.get("RAGFLOW_DATASET_ID", "")

    if not dataset_id:
        return "检索失败：未配置 dataset_id，请在 .env 里填 RAGFLOW_DATASET_ID。"

    try:
        resp = requests.post(
            f"{base_url}/api/v1/retrieval",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "question": question,
                "dataset_ids": [dataset_id],
                "top_k": top_k,
                "similarity_threshold": 0.2,
                "vector_similarity_weight": 0.3,
                "keyword": True,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout:
        return (
            f"检索超时：{base_url} 在 60 秒内没有返回。"
            "常见原因：RAGFlow 第一次检索要拉 Embedding 模型、或 9380 上的服务卡住。"
            "可在浏览器打开 http://localhost 试检索；不行就重启 ragflow-cpu。"
        )
    except Exception as exc:  # noqa: BLE001
        return f"检索请求出错：{exc}"

    if data.get("code") not in (0, None):
        return f"RAGFlow 返回错误：{data.get('message') or data}"

    chunks = (data.get("data") or {}).get("chunks") or []
    if not chunks:
        return f"知识库里没有检索到与「{question}」相关的条款。"

    lines = [f"检索到 {len(chunks)} 条相关内容：\n"]
    for i, ck in enumerate(chunks[:top_k], 1):
        text = (ck.get("content") or ck.get("content_with_weight") or "").strip()
        doc = ck.get("document_keyword") or ck.get("docnm_kwd") or "未知文档"
        page = ""
        positions = ck.get("positions") or ck.get("position_int") or []
        if positions:
            first = positions[0]
            if isinstance(first, (list, tuple)) and first:
                page = f" / 第 {first[0]} 页"
        lines.append(f"[{i}] 出处：{doc}{page}\n{text}\n")
    return "\n".join(lines)


def calc_penalty_impl(
    due_date: str,
    paid_date: str,
    total_amount: float,
    daily_rate: float = 0.0005,
) -> str:
    """计算逾期天数与违约金。用于「如果某天才付款，逾期几天、违约金多少」这类问题。

    通常在先用 search_contract 查到「付款期限」和「违约金比例」之后调用。

    Args:
        due_date (str): 应付款日期，格式 YYYY-MM-DD。
        paid_date (str): 实际付款日期，格式 YYYY-MM-DD。
        total_amount (float): 合同含税总价，单位元。
        daily_rate (float): 日违约金比例，默认 0.0005（每日万分之五）。
    """
    try:
        d1 = _dt.date.fromisoformat(due_date)
        d2 = _dt.date.fromisoformat(paid_date)
    except ValueError as exc:
        return f"日期格式应为 YYYY-MM-DD：{exc}"

    overdue = (d2 - d1).days
    if overdue <= 0:
        return f"应付 {due_date}，实付 {paid_date}，未逾期，无违约金。"

    penalty = round(total_amount * daily_rate * overdue, 2)
    return (
        f"应付款日：{due_date}，实际付款日：{paid_date}\n"
        f"逾期天数：{overdue} 天\n"
        f"违约金 = 含税总价 {total_amount:.2f} × 日比例 {daily_rate} × {overdue} 天 "
        f"= ￥{penalty:.2f}"
    )
