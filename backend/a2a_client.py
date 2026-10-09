"""P4 A2A Client：调用 A2A Server 的轻量封装。"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

DEFAULT_A2A_URL = os.environ.get("A2A_SERVER_URL", "http://127.0.0.1:8001")


class A2AClient:
    """Minimal A2A HTTP Client."""

    def __init__(self, base_url: str = DEFAULT_A2A_URL, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("A2A_TOKEN", "p4-a2a-demo-token")

    def get_agent_card(self) -> dict:
        resp = requests.get(
            f"{self.base_url}/.well-known/agent.json",
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def send_task(self, user_input: str, context: dict | None = None) -> dict:
        resp = requests.post(
            f"{self.base_url}/tasks/send",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "input": user_input,
                "context": context or {},
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
