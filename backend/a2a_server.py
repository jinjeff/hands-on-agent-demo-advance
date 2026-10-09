"""P4 A2A Server：合同合规审查子 Agent。

A2A v1.0 核心语义：
  - GET  /.well-known/agent.json   -> Agent Card（能力发现）
  - POST /tasks/send               -> 同步/短任务派发
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="P4 A2A Compliance Agent", version="1.0.0")

A2A_TOKEN = os.environ.get("A2A_TOKEN", "p4-a2a-demo-token")


class TaskInput(BaseModel):
    task_id: str | None = None
    input: str
    context: dict | None = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    artifacts: list[dict]


AGENT_CARD = {
    "name": "compliance_agent",
    "description": "合同合规审查员，识别逾期、赔偿、管辖等风险点。",
    "url": os.environ.get("A2A_SERVER_URL", "http://127.0.0.1:8001"),
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "authentication": {"schemes": ["Bearer"]},
    "skills": [
        {
            "id": "contract_risk_review",
            "name": "合同风险审查",
            "description": "基于合同条款识别付款、违约、管辖等潜在风险。",
            "tags": ["contract", "compliance", "risk"],
        }
    ],
}


def review_risks(user_input: str, context: dict | None) -> dict:
    clauses = (context or {}).get("clauses", "")
    text = f"{user_input}\n\n{clauses}"

    risks = []
    if not re.search(r"30\s*日|30\s*天|三十日", text):
        risks.append({
            "level": "中",
            "point": "付款期限约定不明或过长，建议补充具体天数并控制账期。",
            "clause": "付款方式相关条款",
        })
    if "违约金" not in text and "赔偿" not in text:
        risks.append({
            "level": "高",
            "point": "未明确违约金或赔偿条款，逾期追偿缺乏合同依据。",
            "clause": "违约责任相关条款",
        })
    if "仲裁" not in text and "法院" not in text and "管辖" not in text:
        risks.append({
            "level": "中",
            "point": "争议解决/管辖条款缺失，纠纷发生时维权成本高。",
            "clause": "争议解决条款",
        })

    if not risks:
        risks.append({
            "level": "低",
            "point": "基于简单规则未发现明显风险点（实际生产请接入大模型做深度审查）。",
            "clause": "—",
        })

    return {"risks": risks, "summary": f"共识别 {len(risks)} 项风险"}


@app.get("/.well-known/agent.json")
def agent_card() -> dict:
    return AGENT_CARD


@app.post("/tasks/send", response_model=TaskResponse)
def send_task(task: TaskInput, authorization: str | None = Header(default=None)):
    token = (authorization or "").replace("Bearer ", "")
    if token and token != A2A_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    task_id = task.task_id or f"task-{uuid.uuid4().hex[:8]}"
    try:
        result = review_risks(task.input, task.context)
        return TaskResponse(
            task_id=task_id,
            status="completed",
            artifacts=[{"type": "risk_report", "name": "合同风险审查报告", "content": result}],
        )
    except Exception as exc:  # noqa: BLE001
        return TaskResponse(
            task_id=task_id,
            status="failed",
            artifacts=[{"type": "error", "content": str(exc)}],
        )


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mode": "a2a", "agent": AGENT_CARD["name"]}


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("A2A_HOST", "127.0.0.1")
    port = int(os.environ.get("A2A_PORT", "8001"))
    print(f"启动 A2A Server：http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
