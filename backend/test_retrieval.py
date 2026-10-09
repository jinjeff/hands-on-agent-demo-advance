#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接测试 RAGFlow retrieval 接口，复现后端调用时的网络/超时/参数问题。

用法（优先读取 .env，也接受命令行覆盖）：
    cd 实战/backend
    source .venv/bin/activate
    python test_retrieval.py
    python test_retrieval.py --question "付款期限多久" --timeout 120
    python test_retrieval.py --base-url http://192.168.1.5:9380 --timeout 180
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests


def _load_dotenv(path: Path) -> None:
    """简单 .env 解析，不把值里的等号切开。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _fmt_elapsed(t: float) -> str:
    if t < 1:
        return f"{t*1000:.1f} ms"
    return f"{t:.2f} s"


def _check_datasets(base_url: str, api_key: str) -> dict:
    """先测 /api/v1/datasets，确认网络通、Key 对。"""
    url = f"{base_url.rstrip('/')}/api/v1/datasets"
    print(f"\n[1/3] 测试连通性: GET {url}")
    t0 = time.time()
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    elapsed = time.time() - t0
    print(f"      status={resp.status_code}, 耗时={_fmt_elapsed(elapsed)}")
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:200]}
    if resp.status_code != 200 or data.get("code") not in (0, None):
        print(f"      失败响应: {json.dumps(data, ensure_ascii=False)[:400]}")
        raise RuntimeError("连 RAGFlow 基础接口失败，请检查地址和 API Key")
    return data


def _find_dataset(data: dict, dataset_id: str, name_hint: str) -> dict | None:
    """在 /datasets 返回里找目标库，确认 id 存在。"""
    rows = data if isinstance(data, list) else []
    if isinstance(data, dict):
        for key in ("data", "kbs", "datasets", "list"):
            val = data.get(key)
            if isinstance(val, list):
                rows = val
                break
            if isinstance(val, dict) and isinstance(val.get("list"), list):
                rows = val["list"]
                break

    for row in rows:
        if (row.get("id") or row.get("kb_id")) == dataset_id:
            return row
    return None


def _call_retrieval(
    base_url: str,
    api_key: str,
    dataset_id: str,
    question: str,
    timeout: int,
) -> None:
    """调用真正的 retrieval 接口，与 tools.py 参数保持一致。"""
    url = f"{base_url.rstrip('/')}/api/v1/retrieval"
    payload = {
        "question": question,
        "dataset_ids": [dataset_id],
        "top_k": 6,
        "similarity_threshold": 0.2,
        "vector_similarity_weight": 0.3,
        "keyword": True,
    }

    print(f"\n[2/3] 测试检索接口: POST {url}")
    print(f"      question={question!r}")
    print(f"      dataset_id={dataset_id}")
    print(f"      timeout={timeout}s")

    t0 = time.time()
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        elapsed = time.time() - t0
        print(f"      status={resp.status_code}, 耗时={_fmt_elapsed(elapsed)}")
        try:
            data = resp.json()
        except Exception:
            print(f"      非 JSON 响应: {resp.text[:500]}")
            return

        if data.get("code") not in (0, None):
            print(f"      业务失败: {json.dumps(data, ensure_ascii=False)[:500]}")
            return

        chunks = (data.get("data") or {}).get("chunks") or []
        print(f"      检索到 {len(chunks)} 条 chunk")
        for i, ck in enumerate(chunks[:3], 1):
            text = (ck.get("content") or ck.get("content_with_weight") or "").strip()
            doc = ck.get("document_keyword") or ck.get("docnm_kwd") or "未知文档"
            print(f"\n      --- chunk {i} ({doc}) ---")
            print(f"      {text[:300]}{'...' if len(text) > 300 else ''}")
        if not chunks:
            print("      提示：没 chunk 通常不是超时，是知识库未解析完或参数阈值过滤太严。")

    except requests.Timeout:
        elapsed = time.time() - t0
        print(f"      ❌ requests.Timeout（>{timeout}s，实际等待 {_fmt_elapsed(elapsed)}）")
        print("      常见原因：")
        print("        • RAGFlow 第一次检索在加载 Embedding 模型，CPU 环境可能很慢")
        print("        • 后端进程到 127.0.0.1:9380 不通（Docker/WSL/虚拟机常见）")
        print("        • RAGFlow 服务内部卡住，请看 docker logs")
    except requests.ConnectionError as exc:
        print(f"      ❌ 连接失败: {exc}")
        print("      请确认 RAGFlow 已启动，且端口与 .env 里的 RAGFLOW_BASE_URL 一致。")
    except Exception as exc:
        print(f"      ❌ 其他异常: {type(exc).__name__}: {exc}")


def main() -> int:
    _load_dotenv(Path(__file__).with_name(".env"))

    p = argparse.ArgumentParser(description="测试 RAGFlow retrieval 接口")
    p.add_argument("--base-url", default=os.environ.get("RAGFLOW_BASE_URL", "http://127.0.0.1:9380"))
    p.add_argument("--api-key", default=os.environ.get("RAGFLOW_API_KEY", ""))
    p.add_argument("--dataset-id", default=os.environ.get("RAGFLOW_DATASET_ID", ""))
    p.add_argument("--question", default="付款期限多久", help="测试问题")
    p.add_argument("--timeout", type=int, default=120, help="retrieval 超时秒数")
    args = p.parse_args()

    base_url = args.base_url.rstrip("/")
    api_key = args.api_key
    dataset_id = args.dataset_id

    if not api_key:
        print("❌ 未设置 RAGFLOW_API_KEY。请在 .env 里填写，或传 --api-key", file=sys.stderr)
        return 2
    if not dataset_id:
        print("❌ 未设置 RAGFLOW_DATASET_ID。请运行 python list_datasets.py 获取 UUID", file=sys.stderr)
        return 2

    print(f"RAGFlow 地址: {base_url}")
    print(f"测试问题: {args.question!r}")

    try:
        ds_data = _check_datasets(base_url, api_key)
        row = _find_dataset(ds_data, dataset_id, "")
        if row:
            print(f"[✓] dataset_id 在库列表中找到: name={row.get('name')}, chunk_num={row.get('chunk_num', row.get('chunk_count'))}")
        else:
            print(f"[!] 警告：在 /datasets 列表里没找到 id={dataset_id}，可能 Key 对应了其他用户/空间")
    except RuntimeError as exc:
        print(f"\n❌ {exc}", file=sys.stderr)
        return 1

    _call_retrieval(base_url, api_key, dataset_id, args.question, args.timeout)

    print("\n[3/3] 如果上面 retrieval 耗时 >60s，建议把 backend/tools.py 里的 timeout=60 改成 120/180")
    print("      如果连接失败，尝试把 .env 的 RAGFLOW_BASE_URL 改成宿主机 IP 或 host.docker.internal:9380")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
