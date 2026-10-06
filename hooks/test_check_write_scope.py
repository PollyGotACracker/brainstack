"""check_write_scope.py 동작 테스트"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_write_scope as hook
import sub_docs
import sub_role

RESEARCH = """# 조사 문서: t

## 조사 계획

- 외부 조사: 필요 (이유: 도구 선택)

## 조사·반증 루프

| 단계 | 회차 | 반증 건수 | 정지 여부 |
| ---- | ---- | --------- | --------- |

### 최종 조사 원문: 조사 단계

```
기록 없음
```

## 후보 비교

| 후보 | 비용 |
| ---- | ---- |
| A    | 낮음 |
"""

INPUT_APPROVED = """# t 입력

### 실행 승인 범위

- 승인 상태: 승인
"""


def claude_line(role: str, text: str) -> str:
    content = text if role == "user" else [{"type": "text", "text": text}]
    return json.dumps({"type": role, "message": {"content": content}}, ensure_ascii=False)


def codex_meta(**payload) -> str:
    return json.dumps({"type": "session_meta", "payload": payload}, ensure_ascii=False)


def codex_msg(role: str, text: str) -> str:
    return json.dumps({"type": "response_item", "payload": {"type": "message", "role": role,
                                                            "content": [{"type": "input_text", "text": text}]}},
                      ensure_ascii=False)


class WriteScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "log" / "state"
        self.state.mkdir(parents=True)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.patches = [patch.object(hook, "ROOT", self.root), patch.object(hook, "ACTIVE", self.state / ".active"),
                        patch.object(sub_docs, "STATE", self.state), patch.object(sub_role, "CODEX_SESSIONS", self.sessions)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def transcript(self, *pairs) -> str:
        path = self.root / "t.jsonl"
        path.write_text("\n".join(claude_line(r, t) for r, t in pairs) + "\n", encoding="utf-8")
        return str(path)

    def write(self, rel, content, role="rio", transcript=None):
        data = {"tool_name": "Write", "tool_input": {"file_path": str(self.root / rel), "content": content},
                "agent_type": role, "cwd": str(self.root),
                "transcript_path": transcript or self.transcript(("assistant", "보고"), ("user", "승인"))}
        return hook.check(data, "claude")

    # director 쓰기 범위
    def test_director_scope(self):
        self.assertIsNone(self.write("log/state/x.md", "- 진행"))
        self.assertIsNotNone(self.write("log/incident/a.md", "# 사건"))
        self.assertIsNotNone(self.write("hooks/a.py", "x"))
        self.assertIsNotNone(self.write("log/state/.active/a.json", "{}"))

    def test_director_bash_write_denied(self):
        data = {"tool_name": "Bash", "tool_input": {"command": "echo a > f.txt"}, "agent_type": "rio"}
        self.assertIsNotNone(hook.check(data, "claude"))
        data["tool_input"]["command"] = "git status"
        self.assertIsNone(hook.check(data, "claude"))

    def test_director_bash_allowlist(self):
        allowed = ("git status", "git log -1 --format=%h", "git diff HEAD~1", "git show HEAD:AGENTS.md",
                   "git branch --show-current", "date", 'date "+%Y-%m-%d %H:%M"')
        denied = ("ls", "cat AGENTS.md", "git log && rm x", "git log | head", "git log --output=a.txt",
                  "git branch -D x", "git -c core.pager=x log", "date -s 2020", "echo $(git log)", "git push")
        for cmd in allowed:
            data = {"tool_name": "Bash", "tool_input": {"command": cmd}, "agent_type": "rio"}
            self.assertIsNone(hook.check(data, "claude"), cmd)
        for cmd in denied:
            data = {"tool_name": "Bash", "tool_input": {"command": cmd}, "agent_type": "rio"}
            self.assertIsNotNone(hook.check(data, "claude"), cmd)

    def test_approval_status_needs_user_approval(self):
        doc = "### 실행 승인 범위\n\n- 승인 상태: 승인\n"
        no = self.transcript(("assistant", "계획"), ("user", "좋아 계속"))
        self.assertIsNotNone(self.write("log/state/t-input.md", doc, transcript=no))
        self.assertIsNone(self.write("log/state/t-input.md", doc))

    def test_raw_block_protected(self):
        (self.state / "t-research.md").write_text(RESEARCH, encoding="utf-8")
        self.assertIsNotNone(self.write("log/state/t-research.md", RESEARCH.replace("기록 없음", "고침")))
        self.assertIsNone(self.write("log/state/t-research.md", RESEARCH.replace("| A    | 낮음 |", "| A | 중간 |")))

    def test_round_blocks_protected(self):
        rounds = RESEARCH + "\n### 1회차 반증 원문\n\n```\n- 주장 1: 반증\n```\n"
        (self.state / "t-research.md").write_text(rounds, encoding="utf-8")
        self.assertIsNotNone(self.write("log/state/t-research.md", rounds.replace("반증\n```", "지지\n```")))
        self.assertIsNotNone(self.write("log/state/t-research.md", RESEARCH))
        self.assertIsNone(self.write("log/state/t-research.md", rounds.replace("| A    | 낮음 |", "| A | 중간 |")))
        self.assertIsNotNone(self.write("log/state/n-research.md", rounds))

    def test_new_research_doc_allows_empty_raw_only(self):
        self.assertIsNone(self.write("log/state/n-research.md", RESEARCH))
        self.assertIsNotNone(self.write("log/state/n-research.md", RESEARCH.replace("기록 없음", "가짜 결과")))

    def test_decision_needs_research_result(self):
        (self.state / "t-research.md").write_text(RESEARCH, encoding="utf-8")
        doc = "### 확정 결정\n\n1. A를 쓴다.\n"
        self.assertIsNotNone(self.write("log/state/t-input.md", doc))
        (self.state / "t-research.md").write_text(RESEARCH.replace("기록 없음", "결정 1 권고: A"), encoding="utf-8")
        self.assertIsNone(self.write("log/state/t-input.md", doc))

    # 읽기 전용
    def test_readonly_roles(self):
        self.assertIsNotNone(self.write("log/state/x.md", "x", role="nico"))
        self.assertIsNotNone(self.write("log/state/x.md", "x", role="ricky"))
        self.assertIsNone(self.write("src/a.py", "x", role="jelly"))

    # assistant 쓰기 승인
    def test_assistant_write_needs_approval(self):
        no = self.transcript(("assistant", "diff"), ("user", "고쳐"))
        self.assertIsNotNone(self.write("src/a.py", "x", role="buddy", transcript=no))
        self.assertIsNone(self.write("src/a.py", "x", role="buddy"))
        data = {"tool_name": "Write", "tool_input": {"file_path": str(self.root / "a.py"), "content": "x"},
                "agent_type": "buddy", "agent_id": "sub-1", "transcript_path": no}
        self.assertIsNone(hook.check(data, "claude"))

    # 하위 에이전트 호출 승인 (Claude)
    def agent(self, prompt, user, **extra):
        data = {"tool_name": "Agent", "tool_input": {"subagent_type": "jelly", "prompt": prompt},
                "agent_type": "rio", "session_id": "s1",
                "transcript_path": self.transcript(("assistant", "계획"), ("user", user)), **extra}
        return hook.check(data, "claude")

    def test_agent_call_needs_approval(self):
        prompt = "작업 종류: 구현\n입력 문서: log/state/t-input.md"
        self.assertIsNotNone(self.agent(prompt, "다시 생각해"))
        self.assertIsNone(self.agent(prompt, "승인"))
        self.assertIsNone(self.agent(prompt, "다시 생각해", agent_id="sub-1"))

    def test_approval_last_line_command(self):
        allowed = ("승인", "이번엔 테스트 빼고 구현해", "시작해.", "진행", "그래", "응",
                   "검수해 줘", "주의사항 1\n주의사항 2\n\n진행해!", "그거 안 해도 돼 진행해")
        denied = ("진행 안 해", "구현하지 마", "승인 안 함", "1", "그러든지.", "반응",
                  "진행해\n근데 잠깐", "", "안 그래", "안  그래", "못 해", "안 진행해")
        for text in allowed:
            self.assertTrue(hook.approved(text), text)
        for text in denied:
            self.assertFalse(hook.approved(text), text)

    def test_buddy_agent_call_not_checked(self):
        data = {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "prompt": "x"},
                "agent_type": "buddy", "transcript_path": self.transcript(("assistant", "a"), ("user", "b"))}
        self.assertIsNone(hook.check(data, "claude"))

    def test_rework_continues_without_new_approval(self):
        prompt = "작업 종류: 재작업\n입력 문서: log/state/t-input.md"
        self.assertIsNotNone(self.agent(prompt, "이 부분 고쳐"))
        (self.state / "t-input.md").write_text(INPUT_APPROVED, encoding="utf-8")
        self.assertIsNone(self.agent(prompt, "이 부분 고쳐"))

    # 하위 에이전트 호출 승인 (Codex 하위 thread)
    def test_codex_child_needs_parent_approval(self):
        parent = self.sessions / "rollout-1-P.jsonl"
        child = self.sessions / "rollout-1-C.jsonl"
        child.write_text("\n".join([
            codex_meta(agent_role="jelly", source={"subagent": {"thread_spawn": {"parent_thread_id": "P"}}}),
            codex_msg("user", "작업 종류: 구현\n입력 문서: log/state/t-input.md")]) + "\n", encoding="utf-8")
        data = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "transcript_path": str(child)}
        parent.write_text("\n".join([codex_meta(), codex_msg("user", "다시 생각해")]) + "\n", encoding="utf-8")
        self.assertIsNotNone(hook.check(data, "codex"))
        parent.write_text("\n".join([codex_meta(), codex_msg("user", "승인")]) + "\n", encoding="utf-8")
        self.assertIsNone(hook.check(data, "codex"))


if __name__ == "__main__":
    unittest.main()
