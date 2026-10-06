"""PreToolUse hook: director의 하위 에이전트 호출 승인과 역할별 쓰기 범위를 검사한다.

사용: python check_write_scope.py --runner <claude|codex>

하위 에이전트 호출 승인
- Claude: director가 Agent를 호출할 때 사용자 마지막 메시지가 승인 명령(APPROVAL)으로 끝나지 않으면 deny한다.
- Codex: spawn_agent에는 PreToolUse가 실행되지 않는다(openai/codex#49736).
  그래서 하위 thread의 도구 호출마다 부모(director) thread의 사용자 마지막 메시지를 확인해 deny한다.
- 예외: 하위 요청 첫 줄이 `작업 종류: 재작업`이고 입력 문서 `실행 승인 범위`의 `승인 상태`가 `승인`이면 허용한다.
- researcher가 reviewer를 부르는 하위 호출은 검사하지 않는다.

쓰기(Edit·Write·NotebookEdit·apply_patch·쓰기 패턴 Bash)
- director 메인 세션:
  - log/state/ 밖이면 deny한다. log/state/.active는 hook 전용이다.
  - Bash는 git 조회(status·log·show·diff·rev-parse·branch --show-current)와 date 단일 명령만 허용하고 나머지는 deny한다.
  - 승인 확인: `승인 상태: 승인` 줄을 새로 쓰려면 사용자 마지막 메시지가 승인 명령으로 끝나야 한다.
  - 조사 확인: 외부 조사가 필요한 작업에서 조사 문서 `최종 조사 원문`이 비어 있으면 `확정 결정` 변경을 deny한다.
  - 원문 보존: 조사 문서 `최종 조사 원문`과 `<n>회차 반증 요청`·`<n>회차 반증 원문` 블록 변경을 deny한다.
    새 조사 문서는 원문 칸이 비었거나 자리표시·`기록 없음`일 때만 허용한다.
- researcher·reviewer: deny (readonly)
- assistant 메인 세션: 사용자 마지막 메시지가 승인 명령으로 끝나지 않으면 쓰기를 deny한다.
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
from sub_session import read_session, turn

READONLY = {"researcher", "reviewer"}
DIRECTOR = ("log/state/",)
# 사용자 메시지의 마지막 줄이 승인 명령으로 끝날 때만 승인이다.
# 동사 바로 뒤에 어미가 와야 하므로 `진행 안 해`·`구현하지 마`는 승인이 아니다.
APPROVAL = re.compile(
    r"(?:^|\s)(?:승인|시작|진행|그래|응"
    r"|(?:시작|진행|구현|작성|검수|적용|실행|반영|수정)\s?(?:해|해줘|해 줘|해라|하세요|해 주세요|합니다))"
    r"\s*[.!~]*\s*$")
APPROVED = re.compile(r"^\s*-\s*승인 상태:\s*승인\s*$")
REWORK = "작업 종류: 재작업"
RAW = ("최종 조사 원문", "최종 반증 원문")
ROUND = re.compile(r"^### (\d+회차 반증 (?:요청|원문))\s*$", re.M)
RAW_EMPTY = re.compile(r"^(`{3,})[^\n]*\n\s*(?:기록 없음|<[^<>\n]*>)?\s*\n\1$")
# ponytail: Bash 쓰기 판정은 패턴 기반이다. 우회는 sandbox_mode·readonly가 2차로 막는다.
WRITE_BASH = re.compile(r"(^|[;&|]\s*)(rm|mv|cp|mkdir|touch|tee|Set-Content|Out-File|New-Item|Remove-Item)\b"
                        r"|\bsed\s+-i\b|(?<![0-9&>])>{1,2}\s*[^&\s>]")
# director Bash는 git 조회와 date 단일 명령만 허용한다.
# 연결·치환·리다이렉션 문자, 파일 출력·외부 실행 옵션이 있으면 deny한다.
DIRECTOR_BASH = re.compile(
    r"\s*(?!.*(?:--output|--ext-diff))"
    r"(?:git (?:status|log|show|diff|rev-parse)(?:\s[^;&|<>`$()\n]*)?"
    r"|git branch --show-current"
    r"|date(?:\s+[\"']?\+[^;&|<>`$()\n]*)?)\s*")
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


NEGATION = ("안", "못")


def approved(user: str) -> bool:
    """사용자 메시지의 비어 있지 않은 마지막 줄이 승인 명령이면 True이다. 부정어가 바로 앞에 오면 False이다."""
    lines = [line for line in user.splitlines() if line.strip()]
    if not lines:
        return False
    words = lines[-1].split()
    if len(words) >= 2 and words[-2] in NEGATION:
        return False
    return bool(APPROVAL.search(lines[-1]))


def approval_reason(user: str, prompt: str) -> str | None:
    if approved(user):
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
    user, _ = last_user(data.get("transcript_path"))
    for path in paths:
        added, new = added_lines(data, path)
        old = read(path)
        if any(APPROVED.match(l) for l in added) and not approved(user):
            return "사용자 마지막 메시지에 승인이 없습니다. 승인 상태를 승인으로 쓸 수 없습니다."
        if path.name.endswith("-research.md"):
            changed = [t for t in RAW if new is not None and section(new, t) != section(old, t)]
            if changed and not (not old and all(raw_empty(new, t) for t in changed)):
                return "조사 문서의 최종 원문 칸은 하네스만 씁니다."
            if new is not None and rounds(new) != rounds(old):
                return "조사 문서의 회차 반증 블록은 하네스만 씁니다."
            continue
        if not path.name.endswith("-input.md"):
            continue
        if new is not None and section(new, "확정 결정") != section(old, "확정 결정"):
            research = read(path.with_name(path.name.replace("-input.md", "-research.md")))
            if research and research_needed(research) and raw_empty(research, "최종 조사 원문"):
                return "조사 문서 최종 조사 원문이 비어 있어 확정 결정을 기록할 수 없습니다. 조사가 필요합니다."
    return None


def rounds(text: str) -> list[tuple[str, str]]:
    """회차 반증 블록의 (제목, 본문) 목록이다."""
    return [(t, section(text, t)) for t in ROUND.findall(text)]


def raw_empty(text: str, title: str) -> bool:
    """원문 칸이 비었거나 자리표시·`기록 없음`이면 True이다."""
    body = section(text, title).strip()
    return not body or bool(RAW_EMPTY.match(body))


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
    if role == "director" and data.get("tool_name") == "Bash":
        cmd = (data.get("tool_input") or {}).get("command")
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd or ""
        if not DIRECTOR_BASH.fullmatch(cmd):
            return "director Bash는 git 조회(status·log·show·diff·rev-parse·branch --show-current)와 date만 허용합니다."
    paths = targets(data)
    if paths is None:
        return None
    if role in READONLY:
        return f"{role}은 읽기 전용입니다. 결과는 반환하면 하네스가 저장합니다."
    if role == "director":
        return check_director_write(data, paths)
    if role == "assistant" and not data.get("agent_id"):
        user, _ = last_user(data.get("transcript_path"))
        if not approved(user):
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
