"""SubagentStop hook: researcher 최종 결과와 reviewer 반증 결과를 조사 문서의 기존 칸에 원문 그대로 쓴다.

사용: python save_agent_result.py --runner <claude|codex>
- researcher: `최종 조사 원문` 코드 블록 내용을 교체한다.
- reviewer 반증: `최종 반증 원문` 코드 블록 내용을 교체하고 `조사·반증 루프` 표에 회차 행을 추가한다.
- reviewer 검수·계획 검수는 저장하지 않는다. 판정은 director가 상태 문서 `검수 결과`에 기록한다.
- 작업 ID는 하위 기록 첫 요청의 `입력 문서:`·`상태 문서:` 줄에서 읽는다.
  반증 요청처럼 문서 줄이 없으면 Claude는 ACTIVE의 researcher 값, Codex는 부모 thread 첫 요청에서 찾는다.
- 조사 문서가 없으면 아무것도 하지 않는다. 출력은 없다. 오류는 통과한다(fail-open).
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from check_agent_input import refute_mode
from check_refute_verdict import VERDICT
from sub_docs import ACTIVE, doc, task_id
from sub_role import codex_rollout, first_prompt, parent_thread, resolve_role

LOOP_ROW = re.compile(r"^\| *조사 *\| *(\d+) *\|", re.M)


def transcript(data: dict, runner: str) -> str:
    path = data.get("agent_transcript_path")
    if path:
        return path
    return codex_rollout(data.get("agent_id")) if runner == "codex" else ""


def find_task(data: dict, runner: str, path: str, prompt: str) -> str | None:
    tid = task_id(prompt)
    if tid:
        return tid
    if runner == "codex":
        return task_id(first_prompt(codex_rollout(parent_thread(path))))
    try:
        return json.loads((ACTIVE / f"{data.get('session_id')}.json").read_text(encoding="utf-8")).get("researcher")
    except (OSError, ValueError):
        return None


def replace_block(text: str, title: str, body: str) -> str:
    pattern = re.compile(rf"(^#{{2,3}} {re.escape(title)}[^\n]*\n+(`{{3,}})[^\n]*\n)(.*?)(\n\2[ \t]*$)", re.M | re.S)
    return pattern.sub(lambda m: m.group(1) + body + m.group(4), text, count=1)


def add_loop_row(text: str, message: str) -> str:
    n = len(LOOP_ROW.findall(text)) + 1
    refuted = sum(1 for line in message.splitlines() if (m := VERDICT.match(line)) and m.group(2) == "반증")
    stop = "정지(반증 0건)" if refuted == 0 else "정지(3회 도달)" if n >= 3 else "계속"
    row = f"| 조사 | {n} | {refuted} | {stop} |"
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "## 조사·반증 루프"), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    last = max((i for i in range(start, end) if lines[i].strip().startswith("|")), default=end - 1)
    lines.insert(last + 1, row)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def save(data: dict, runner: str) -> None:
    role = resolve_role(data)
    message = (data.get("last_assistant_message") or "").strip()
    if role not in ("researcher", "reviewer") or not message:
        return
    path = transcript(data, runner)
    prompt = first_prompt(path) or "\n".join(str(v) for v in (data.get("tool_input") or {}).values())
    refute = role == "reviewer" and refute_mode(prompt)
    if role == "reviewer" and not refute:
        return
    tid = find_task(data, runner, path, prompt)
    target = doc(tid, "research") if tid else None
    if not target or not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    text = replace_block(text, "최종 반증 원문" if refute else "최종 조사 원문", message)
    if refute:
        text = add_loop_row(text, message)
    target.write_text(text, encoding="utf-8")


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", choices=("claude", "codex"), required=True)
    runner = parser.parse_args().runner
    try:
        save(json.load(sys.stdin), runner)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
