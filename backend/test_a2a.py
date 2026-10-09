"""测试 A2A Server。"""

from __future__ import annotations

import json

from a2a_client import A2AClient


def main() -> int:
    client = A2AClient()
    print("agent card:", json.dumps(client.get_agent_card(), ensure_ascii=False))
    print("---")
    print(json.dumps(
        client.send_task("帮我审一下合同风险", context={"clauses": "第六条：验收合格后付款。"}),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
