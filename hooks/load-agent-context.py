#!/usr/bin/env python3
"""에이전트 지침·성향 원본 Markdown을 Claude Code나 Codex hook context에 넣는다.

hook 입력 JSON을 stdin으로 받고 hookSpecificOutput JSON을 stdout으로 출력한다.
입력의 agent_type을 에이전트 이름이나 역할로 보고 해당 SOUL.md를 넣는다.

--include-role: 역할 지침 AGENTS.md도 SOUL.md 앞에 함께 넣는다.
--default-role: 입력에 agent_type이 없을 때 쓸 에이전트 이름이나 역할이다.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# AGENTS.md frontmatter의 name 값을 읽는다.
# 값이 없으면 None이다.
def read_agent_name(agents_file: Path) -> str | None:
    text = agents_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) != 3:
        return None
    for line in parts[1].splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip() or None
    return None


# .claude/agents 아래 역할 폴더마다 {역할: 에이전트 이름}을 만든다.
def discover_agents(root: Path) -> dict[str, str]:
    agents: dict[str, str] = {}
    for role_dir in sorted((root / ".claude" / "agents").iterdir()):
        agents_file = role_dir / "AGENTS.md"
        if not role_dir.is_dir() or not agents_file.is_file():
            continue
        agents[role_dir.name] = read_agent_name(agents_file) or role_dir.name
    return agents


# frontmatter를 뺀 본문을 반환한다.
def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text.strip()
    parts = text.split("---", 2)
    return parts[2].lstrip().strip() if len(parts) == 3 else text.strip()


# cwd부터 상위로 올라가며 AGENTS.md와 .claude/agents가 있는 폴더를 찾는다.
def find_bundle_root(cwd: Path) -> Path:
    current = cwd.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / ".claude" / "agents").is_dir():
            return candidate
    raise FileNotFoundError(
        "AGENTS.md와 .claude/agents가 있는 에이전트 구성 루트를 찾지 못했습니다."
    )


# 요청한 에이전트의 문서를 읽어 hook 출력 JSON을 쓴다.
# 알 수 없는 에이전트이면 아무것도 출력하지 않는다.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-role", action="store_true")
    parser.add_argument("--default-role")
    args = parser.parse_args()

    payload = json.load(sys.stdin)
    cwd = Path(payload.get("cwd") or ".")
    requested = payload.get("agent_type") or args.default_role
    event = payload.get("hook_event_name") or "SessionStart"

    root = find_bundle_root(cwd)
    role_to_name = discover_agents(root)
    name_to_role = {name: role for role, name in role_to_name.items()}

    role = name_to_role.get(requested, requested)
    if role not in role_to_name:
        return 0

    role_dir = root / ".claude" / "agents" / role
    role_file = role_dir / "AGENTS.md"
    soul_file = role_dir / "SOUL.md"
    if not role_file.is_file() or not soul_file.is_file():
        raise FileNotFoundError(f"에이전트 문서가 없습니다: {role_dir}")

    sections: list[str] = []
    if args.include_role:
        sections.append("# Role\n\n" + strip_frontmatter(role_file.read_text(encoding="utf-8")))
    sections.append("# Persona\n\n" + soul_file.read_text(encoding="utf-8").strip())

    json.dump({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n\n---\n\n".join(sections),
        }
    }, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"load-agent-context.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
