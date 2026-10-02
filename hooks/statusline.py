#!/usr/bin/env python3
"""Claude Code status line에 현재 메인 에이전트 이름을 표시한다."""

from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# stdin 상태 JSON의 agent.name을 출력한다.
# 이름이 없으면 default를 출력한다.
def main() -> int:
    data = json.load(sys.stdin)
    name = (data.get("agent") or {}).get("name") or "default"
    print(f"Agent: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
