#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三问验收：打真实 RAGFlow 的 /api/v1/retrieval。

需要三个环境变量（先 cd backend && cp .env.example .env 并按第二部分 2.2 配好，再 source）：
    RAGFLOW_BASE_URL   默认 http://127.0.0.1:9380
    RAGFLOW_API_KEY    控制台头像 → API → Create 生成（只显示一次）
    RAGFLOW_DATASET_ID python list_datasets.py --api-key 你的Key 查到的 UUID
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("RAGFLOW_BASE_URL", "http://127.0.0.1:9380").rstrip("/")
KEY = os.environ.get("RAGFLOW_API_KEY", "")
DATASET = os.environ.get("RAGFLOW_DATASET_ID", "")

if not KEY or not DATASET:
    print("缺少 RAGFLOW_API_KEY / RAGFLOW_DATASET_ID。")
    print("步骤：cd backend && cp .env.example .env，按实战步骤第二部分 2.2 填好三项，然后：")
    print('  set -a && source backend/.env && set +a   # Windows 逐行 $env:KEY="值"')
    print("  python scripts/retrieve.py")
    sys.exit(2)

QUESTIONS = [
    "这份合同的付款期限是多久？",
    "含税总价是多少？",
    "铜版纸的数量和单价？",
]


def retrieve(question: str, top_k: int = 4) -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/v1/retrieval",
        data=json.dumps(
            {
                "question": question,
                "dataset_ids": [DATASET],
                "top_k": top_k,
                "similarity_threshold": 0.2,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def show(question: str) -> None:
    print("\nQ:", question)
    try:
        data = retrieve(question)
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code}：确认 RAGFlow 在 {BASE} 可达、API Key 正确、dataset id 已配置")
        sys.exit(1)
    except urllib.error.URLError as exc:
        print("  请求失败：", exc)
        print("  确认 RAGFlow API 在", BASE, "（本机 docker：控制台 80 / API 9380）")
        sys.exit(1)
    if data.get("code") not in (0, None):
        print("  接口报错：", data)
        return
    chunks = (data.get("data") or {}).get("chunks") or []
    if not chunks:
        print("  （没有召回）")
        return
    for i, ck in enumerate(chunks, 1):
        text = (ck.get("content") or ck.get("content_with_weight") or "").strip()
        doc = ck.get("document_keyword") or "未知文档"
        page = "?"
        pos = ck.get("positions") or ck.get("position_int") or []
        if pos and isinstance(pos[0], (list, tuple)) and pos[0]:
            page = pos[0][0]
        sim = ck.get("similarity", "")
        print(f"  [{i}] {doc} / 第 {page} 页  sim={sim}")
        for line in text.splitlines()[:4]:
            print("      ", line)


if __name__ == "__main__":
    qs = sys.argv[1:] or QUESTIONS
    print(f"→ {BASE}  dataset={DATASET}")
    for q in qs:
        show(q)
