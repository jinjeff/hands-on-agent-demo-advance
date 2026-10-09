"""离线 mock：没有 RAGFlow / 没有模型 Key 时，让前后端链路照样能跑通。

它模拟「合同问答助手」的两轮 ReAct：
- 问付款期限 → 走一次检索工具
- 问逾期违约金 → 先检索、再计算，两轮
返回的事件序列和真 Agent 一致（tool 调用 + 流式 token），
所以前端不用改任何代码。
"""

from __future__ import annotations

import datetime as _dt

# 固定的三条「检索切片」，出处沿用 P2 的采购合同案例
_CLAUSES = {
    "付款": {
        "doc": "采购合同.pdf",
        "page": 2,
        "text": "第六条 付款方式：买方应在货物验收合格之日起 30 日内付清全部合同价款。",
    },
    "违约": {
        "doc": "采购合同.pdf",
        "page": 3,
        "text": "第九条 违约责任：逾期付款的，每逾期一日，按合同总价的万分之五向卖方支付违约金。",
    },
    "总价": {
        "doc": "采购合同.pdf",
        "page": 1,
        "text": "合同含税总价为人民币 186,000.00 元（大写：壹拾捌万陆仟元整）。",
    },
}

TOTAL_AMOUNT = 186000.0
DAILY_RATE = 0.0005
DUE_FROM_ACCEPT_DAYS = 30


def _retrieve(keyword: str) -> dict:
    return _CLAUSES.get(keyword, _CLAUSES["付款"])


def plan(question: str) -> list[dict]:
    """把用户问题拆成一串事件：tool_call / tool_result / answer。

    返回的每个事件形如：
        {"type": "tool_call", "tool": "search_contract", "args": {...}}
        {"type": "tool_result", "tool": "search_contract", "text": "..."}
        {"type": "answer", "text": "..."}
    server.py 会把它们逐条转成 SSE，answer 再逐字吐。
    """
    q = question
    events: list[dict] = []

    wants_penalty = any(k in q for k in ["违约金", "逾期", "赔"])
    if wants_penalty:
        # 第一轮：检索条款（付款期限 + 违约金比例）
        c_pay = _retrieve("付款")
        c_fine = _retrieve("违约")
        events.append({"type": "tool_call", "tool": "search_contract",
                       "args": {"question": "付款期限与违约金比例"}})
        events.append({"type": "tool_result", "tool": "search_contract",
                       "text": f"[1] 出处：{c_pay['doc']} / 第 {c_pay['page']} 页\n{c_pay['text']}\n\n"
                               f"[2] 出处：{c_fine['doc']} / 第 {c_fine['page']} 页\n{c_fine['text']}"})
        # 从问题里粗略解析付款日期；解析不到就用示例
        paid = _guess_date(q) or "2024-11-20"
        # 验收日示例：2024-10-10，验收后 30 日应付 = 2024-11-09
        due = "2024-11-09"
        overdue = (_dt.date.fromisoformat(paid) - _dt.date.fromisoformat(due)).days
        overdue = max(overdue, 0)
        penalty = round(TOTAL_AMOUNT * DAILY_RATE * overdue, 2)
        # 第二轮：计算违约金
        events.append({"type": "tool_call", "tool": "calc_penalty",
                       "args": {"due_date": due, "paid_date": paid,
                                "total_amount": TOTAL_AMOUNT, "daily_rate": DAILY_RATE}})
        events.append({"type": "tool_result", "tool": "calc_penalty",
                       "text": f"逾期天数：{overdue} 天\n违约金 = 186000 × 0.0005 × {overdue} = ￥{penalty:.2f}"})
        events.append({"type": "answer",
                       "text": f"根据合同第六条，货物验收合格后 30 日内应付款（应付日 {due}）。"
                               f"若 {paid} 才付款，则逾期 {overdue} 天。"
                               f"依第九条按每日万分之五计，违约金为 ￥{penalty:.2f}。\n\n"
                               f"📎 出处：采购合同.pdf 第 2、3 页"})
        return events

    # 单轮：查一个条款就能答
    if "总价" in q or "金额" in q or "多少钱" in q:
        c = _retrieve("总价")
    else:
        c = _retrieve("付款")
    events.append({"type": "tool_call", "tool": "search_contract", "args": {"question": q}})
    events.append({"type": "tool_result", "tool": "search_contract",
                   "text": f"[1] 出处：{c['doc']} / 第 {c['page']} 页\n{c['text']}"})
    events.append({"type": "answer",
                   "text": f"{c['text']}\n\n📎 出处：{c['doc']} 第 {c['page']} 页"})
    return events


def _guess_date(q: str) -> str | None:
    """从「11 月 20 日」「2024-11-20」里粗略抓一个日期。抓不到返回 None。"""
    import re

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", q)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", q)
    if m:
        mo, d = map(int, m.groups())
        return f"2024-{mo:02d}-{d:02d}"
    return None
