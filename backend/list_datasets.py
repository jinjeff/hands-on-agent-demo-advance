#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出指定 RAGFlow 上所有知识库的名称和 id。

用法：
    python list_datasets.py
    python list_datasets.py --base-url http://127.0.0.1:9380 --api-key ragflow-xxxx
    python list_datasets.py --name 知识库构建

优先读命令行，其次读环境变量 RAGFLOW_BASE_URL / RAGFLOW_API_KEY
（可先 `set -a && source .env && set +a`）。
只依赖 Python 标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch(base_url: str, api_key: str, name: str | None) -> dict:
    q = {"page": "1", "page_size": "100"}
    if name:
        q["name"] = name
    url = f"{base_url.rstrip('/')}/api/v1/datasets?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rows_from(payload: dict) -> list[dict]:
    """兼容 RAGFlow 几种返回形状：data 是列表，或 data.kbs / data.datasets。"""
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("kbs", "datasets", "list"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def main() -> int:
    p = argparse.ArgumentParser(description="列出 RAGFlow 知识库名称和 id")
    p.add_argument("--base-url", default=os.environ.get("RAGFLOW_BASE_URL", "http://127.0.0.1:9380"),
                   help="RAGFlow API 地址，默认 http://127.0.0.1:9380")
    p.add_argument("--api-key", default=os.environ.get("RAGFLOW_API_KEY", ""),
                   help="控制台生成的 API Key（Bearer）")
    p.add_argument("--name", default="", help="按知识库名称筛选，可省略")
    args = p.parse_args()

    if not args.api_key:
        print("缺少 API Key。请在控制台（头像 → API Key → Create）生成后：", file=sys.stderr)
        print("  python list_datasets.py --api-key ragflow-xxxx", file=sys.stderr)
        print("或写入 .env 的 RAGFLOW_API_KEY 再 source。", file=sys.stderr)
        return 2

    print(f"→ {args.base_url.rstrip('/')}/api/v1/datasets")
    try:
        payload = fetch(args.base_url, args.api_key, args.name or None)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"连不上 {args.base_url}：{exc}", file=sys.stderr)
        print("确认 RAGFlow 已启动，端口与 SVR_HTTP_PORT 一致（默认 9380）。", file=sys.stderr)
        return 1

    if payload.get("code") not in (0, None):
        print("接口报错：", json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1

    rows = rows_from(payload)
    if not rows:
        print("没有知识库。先在 Web 控制台建一个，或检查 Key 是否属于当前用户。")
        return 0

    name_w = max(4, max(len(str(r.get("name") or "")) for r in rows))
    print(f"{'名称':<{name_w}}  id")
    print("-" * (name_w + 4 + 36))
    for r in rows:
        did = r.get("id") or r.get("kb_id") or ""
        name = r.get("name") or ""
        extra = ""
        nchunk = r.get("chunk_num", r.get("chunk_count"))
        if nchunk is not None:
            extra = f"  chunks={nchunk}"
        print(f"{name:<{name_w}}  {did}{extra}")

    print()
    print("把对应 id 填进 .env 的 RAGFLOW_DATASET_ID。检索时 dataset_ids 必须是非空数组。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
