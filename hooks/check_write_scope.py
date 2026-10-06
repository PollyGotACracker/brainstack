"""PreToolUse hook: director의 하위 에이전트 호출 승인과 역할별 쓰기 범위를 검사한다.

사용: python check_write_scope.py --runner <claude|codex>

하위 에이전트 호출 승인
- Claude: director가 Agent를 호출할 때 사용자 마지막 메시지에 `승인`이 없으면 deny한다.
- Codex: spawn_agent에는 PreToolUse가 실행되지 않는다(openai/codex#49736).
  그래서 하위 thread의 도구 호출마다 부모(director) thread의 사용자 마지막 메시지를 확인해 deny한다.
- 예외: 하위 요청 첫 줄이 `작업 종류: 재작업`이고 입력 문서 `실행 승인 범위`의 `승인 상태`가 `승인`이면 허용한다.
- researcher가 reviewer를 부르는 하위 호출은 검사하지 않는다.

쓰기(Edit·Write·NotebookEdit·apply_patch·쓰기 패턴 Bash)
- director 메인 세션:
  - log/state/ 밖이면 deny한다. log/state/.active는 hook 전용이다. Bash 쓰기는 deny한다.
  - 보고 = 기록: 입력 문서 `문제 정의`·`요구사항 목록`·`확정 결정`에 새로 들어가는 줄은 직전 응답에 있어야 한다.
  - 승인 확인: `승인 상태: 승인` 줄을 새로 쓰려면 사용자 마지막 메시지에 `승인`이 있어야 한다.
  - 후보 확인: 외부 조사가 필요한 작업에서 조사 문서 `후보 비교`가 2행 미만이면 `확정 결정` 변경을 deny한다.
  - 원문 보존: 조사 문서 `최종 조사 원문`·`최종 반증 원문` 내용 변경을 deny한다.
- researcher·reviewer: deny (readonly)
- assistant 메인 세션: 사용자 마지막 메시지에 `승인`이 없으면 쓰기를 deny한다.
- 그 외 역할과 역할 판별 실패: 통과

Claude Agent 호출은 대상 역할의 작업 ID를 ACTIVE/<session_id>.json에 남긴다(save_agent_result가 쓴다).
오류는 통과한다(fail-open).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from check_agent_input import call_info, deny
from sub_docs import ACTIVE, ROOT, doc, section, task_id
from sub_role import codex_rollout, first_line, first_prompt, parent_thread, resolve_role, to_role
from sub_session import norm, read_session, turn

READONLY = {"researcher", "reviewer"}
DIRECTOR = ("log/state/",)
APPROVAL_WORD = "승인"  # ponytail: 키워드 포함 판정이다. 오탐이 문제되면 정확한 승인 문구로 좁힌다.
APPROVED = re.compile(r"^\s*-\s*승인 상태:\s*승인\s*$")
REWORK = "작업 종류: 재작업"
PLACEHOLDER = re.compile(r"<[^<>\n]+>")
RAW = ("최종 조사 원문", "최종 반증 원문")
REPORTED = ("문제 정의", "요구사항 목록", "확정 결정")
# ponytail: Bash 쓰기 판정은 패턴 기반이다. 우회는 sandbox_mode·readonly가 2차로 막는다.
WRITE_BASH = re.compile(r"(^|[;&|]\s*)(rm|mv|cp|mkdir|touch|tee|Set-Content|Out-File|New-Item|Remove-Item)\b"
                        r"|\bsed\s+-i\b|(?<![0-9&>])>{1,2}\s*[^&\s>]")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.M)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def targets(data: dict) -> list[Path] | None:
    """쓰기 대상 경로를 반환한다. 쓰기가 아니면 None, 대상을 모르는 쓰기면 빈 목록이다."""
    name, tin = data.get("tool_name"), data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or ".")
    if name in ("Edit", "Write", "NotebookEdit"):
        return [cwd / (tin.get("file_path") or tin.get("notebook_path") or "")]
    if name == "apply_patch":
        return [cwd / (a or b).strip() for s in strings(tin) for a, b in PATCH_FILE.findall(s)]
    if name == "Bash":
        cmd = tin.get("command")
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd or ""
        return [] if WRITE_BASH.search(cmd) else None
    return None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return ""


def last_user(path: str | None) -> tuple[str, str]:
    """(사용자 마지막 메시지, 그 직전 assistant 응답)이다."""
    user, shown, _ = turn(read_session(path or ""))
    return user, shown


def executed_approved(task: str | None) -> bool:
    body = section(read(doc(task, "input")), "실행 승인 범위") if task else ""
    return any(APPROVED.match(line) for line in body.splitlines())


def approval_reason(user: str, prompt: str) -> str | None:
    if APPROVAL_WORD in user:
        return None
    first = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
    if first == REWORK and executed_approved(task_id(prompt)):
        return None
    return "사용자 마지막 메시지에 승인이 없습니다. 하위 에이전트 호출 전에 승인을 받으십시오."


def remember(data: dict, target_role: str, prompt: str) -> None:
    tid = task_id(prompt)
    if not tid:
        return
    path = ACTIVE / f"{data.get('session_id')}.json"
    ACTIVE.mkdir(parents=True, exist_ok=True)
    active = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    active[target_role] = tid  # ponytail: 역할당 작업 1개. 같은 역할 병렬 작업이 생기면 agent_id 키로 바꾼다.
    path.write_text(json.dumps(active, ensure_ascii=False), encoding="utf-8")


def check_agent_call(data: dict) -> str | None:
    """Claude Agent 호출 검사이다."""
    if data.get("agent_id") or resolve_role(data) != "director":
        return None
    target, prompt = call_info(data)
    role = to_role(target)
    if role:
        remember(data, role, prompt)
    user, _ = last_user(data.get("transcript_path"))
    return approval_reason(user, prompt)


def check_codex_child(data: dict) -> str | None:
    """Codex 하위 thread의 도구 호출에서 부모 director의 승인을 검사한다."""
    path = data.get("transcript_path")
    parent = codex_rollout(parent_thread(path))
    if not parent or first_line(parent).get("agent_role"):
        return None  # 부모가 director 메인 thread가 아니다(e.g. researcher가 부른 reviewer).
    user, _ = last_user(parent)
    return approval_reason(user, first_prompt(path))


def added_lines(data: dict, path: Path) -> tuple[list[str], str | None]:
    """(새로 들어가는 줄, 쓰기 후 전문 또는 None)이다."""
    tin = data.get("tool_input") or {}
    old = read(path)
    name = data.get("tool_name")
    if name == "Write":
        new = tin.get("content", "")
    elif name == "Edit":
        new = old.replace(tin.get("old_string", ""), tin.get("new_string", ""), -1 if tin.get("replace_all") else 1)
    else:
        # ponytail: apply_patch는 + 줄만 본다. 전문이 필요한 원문 보존 검사는 생략한다.
        plus = [l[1:] for s in strings(tin) for l in s.splitlines() if l.startswith("+") and not l.startswith("+++")]
        return plus, None
    old_lines = set(old.splitlines())
    return [l for l in new.splitlines() if l.strip() and l not in old_lines], new


def check_director_write(data: dict, paths: list[Path]) -> str | None:
    if not paths:
        return "director의 Bash 쓰기는 허용하지 않습니다. Write·Edit로 기록하십시오."
    for path in paths:
        r = rel(path)
        if not r.startswith(DIRECTOR) or r.startswith("log/state/.active"):
            return f"director 쓰기 범위는 상태·입력·조사 문서입니다: {r or path}"
    user, shown = last_user(data.get("transcript_path"))
    for path in paths:
        added, new = added_lines(data, path)
        old = read(path)
        if any(APPROVED.match(l) for l in added) and APPROVAL_WORD not in user:
            return "사용자 마지막 메시지에 승인이 없습니다. 승인 상태를 승인으로 쓸 수 없습니다."
        if path.name.endswith("-research.md"):
            if new is not None and any(section(new, t) != section(old, t) for t in RAW):
                return "조사 문서의 최종 원문 칸은 하네스만 씁니다."
            continue
        if not path.name.endswith("-input.md"):
            continue
        reported = set("\n".join(section(new, t) for t in REPORTED).splitlines()) if new is not None else set(added)
        for line in (l for l in added if l in reported):
            if HEADING_LINE.match(line) or PLACEHOLDER.search(line):
                continue
            if norm(line.strip(" -*0123456789.:")) not in norm(shown):
                return f"직전 응답에서 사용자에게 보여 주지 않은 문구입니다: {line.strip()[:60]}"
        if new is not None and section(new, "확정 결정") != section(old, "확정 결정"):
            research = read(path.with_name(path.name.replace("-input.md", "-research.md")))
            if research and research_needed(research) and candidate_rows(research) < 2:
                return "조사 문서 후보 비교가 2행 미만이라 확정 결정을 기록할 수 없습니다. 재조사가 필요합니다."
    return None


HEADING_LINE = re.compile(r"^\s*#")


def candidate_rows(research: str) -> int:
    rows = [l for l in section(research, "후보 비교").splitlines() if l.strip().startswith("|")]
    return max(len(rows) - 2, 0)  # 머리글·구분선 제외


def research_needed(research: str) -> bool:
    return "외부 조사: 필요" in section(research, "조사 계획")


def check(data: dict, runner: str) -> str | None:
    if data.get("tool_name") == "Agent":
        return check_agent_call(data)
    role = resolve_role(data)
    if runner == "codex" and role not in (None, "director", "assistant"):
        reason = check_codex_child(data)
        if reason:
            return reason
    paths = targets(data)
    if paths is None:
        return None
    if role in READONLY:
        return f"{role}은 읽기 전용입니다. 결과는 반환하면 하네스가 저장합니다."
    if role == "director":
        return check_director_write(data, paths)
    if role == "assistant" and not data.get("agent_id"):
        user, _ = last_user(data.get("transcript_path"))
        if APPROVAL_WORD not in user:
            return "사용자 마지막 메시지에 승인이 없습니다. 변경 diff를 먼저 제시하고 승인을 받으십시오."
    return None


def main() -> int:
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", choices=("claude", "codex"), required=True)
    runner = parser.parse_args().runner
    try:
        reason = check(json.load(sys.stdin), runner)
    except Exception:
        return 0
    if reason:
        json.dump(deny(reason), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
