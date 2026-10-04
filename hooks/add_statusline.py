#!/usr/bin/env python3
"""에이전트 이름을 표시하고 Orca의 상태 정보 전송을 유지한다."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# Orca에서 실행할 때 같은 상태 입력을 기존 스크립트에 전달한다.
def forward_orca(payload: str) -> None:
    if not os.environ.get("ORCA_PANE_KEY"):
        return

    hook = Path.home() / ".orca" / "agent-hooks" / "claude-statusline.cmd"
    if os.name != "nt" or not hook.is_file():
        return

    try:
        subprocess.run(
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(hook)],
            input=payload,
            encoding="utf-8",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


# 상태 입력에서 에이전트 이름을 출력한다.
def main() -> int:
    payload = sys.stdin.read()
    data = json.loads(payload)
    name = (data.get("agent") or {}).get("name") or "default"
    print(f"Agent: {name}", flush=True)
    forward_orca(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())