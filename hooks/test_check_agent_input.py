"""check_agent_input.py 동작 테스트"""
import json
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import check_agent_input as hook

STATE = "상태 문서: log/state/20261006-0555-x.md\n절: 요구사항 목록"
RESEARCH = "작업 종류: 조사\n조사 문서: log/state/20261006-0555-x-research.md"
INPUT = "입력 문서: log/state/20261006-0555-x-input.md"
REFUTE = "작업 종류: 반증\n주장: 1. 변경이 요구를 충족한다.\n증거: 코드 발췌\n출처: hooks/a.py:12\n판정 기준: 요구 충족\n원문 발췌: 확인할 원문"


def claude(target, prompt, sub=False):
    d = {"tool_name": "Agent", "tool_input": {"subagent_type": target, "prompt": prompt}}
    return {**d, "agent_id": "a1"} if sub else d


def codex(target, prompt):
    return {"tool_name": "spawn_agent", "tool_input": {"agent_type": target, "message": prompt}}


def run_utf8(hook, data, *args, cwd=None):
    env = {**os.environ, "PYTHONIOENCODING": "", "PYTHONUTF8": "0"}
    return subprocess.run([sys.executable, "-B", hook.__file__, *args], env=env, capture_output=True, check=True,
                          input=json.dumps(data, ensure_ascii=False).encode("utf-8"), cwd=cwd).stdout.decode("utf-8")


class AgentInput(unittest.TestCase):
    def test_free_text_denied(self):
        for runner, make in (("claude", claude), ("codex", codex)):
            with self.subTest(runner=runner):
                self.assertIsNotNone(hook.check(make("jelly", "이전 대화 요약: ..."), runner))
                self.assertIsNotNone(hook.check(make("jelly", INPUT + "\n추가 설명"), runner))
                self.assertIsNone(hook.check(make("jelly", INPUT), runner))
                self.assertIsNone(hook.check(make("nico", RESEARCH), runner))

    def test_worker_reviewer_take_input_doc_only(self):
        for target in ("jelly", "worker", "ricky", "reviewer"):
            self.assertIsNotNone(hook.check(claude(target, STATE), "claude"))
            self.assertIsNone(hook.check(claude(target, INPUT), "claude"))

    def test_researcher_takes_research_doc_only(self):
        self.assertIsNotNone(hook.check(claude("researcher", INPUT), "claude"))
        self.assertIsNotNone(hook.check(claude("researcher", STATE), "claude"))
        self.assertIsNotNone(hook.check(claude("researcher", RESEARCH + "\n추가 설명"), "claude"))
        self.assertIsNone(hook.check(claude("researcher", RESEARCH), "claude"))

    def test_documenter_record_request_left_to_other_hook(self):
        self.assertIsNone(hook.check(claude("pepper", "기록 문구"), "claude"))
        self.assertIsNotNone(hook.check(claude("pepper", INPUT), "claude"))

    def test_documenter_takes_state_and_input_doc(self):
        both = STATE + "\n" + INPUT
        self.assertIsNone(hook.check(claude("pepper", both), "claude"))
        self.assertIsNone(hook.check(claude("documenter", STATE), "claude"))
        self.assertIsNotNone(hook.check(claude("pepper", both + "\n입력 문서: log/state/a-input.md"), "claude"))
    def test_caller_detection(self):
        self.assertIsNone(hook.check(claude("jelly", "자유 문장", sub=True), "claude"))  # Claude 서브에이전트
        self.assertIsNotNone(hook.check(codex("nico", "자유 문장"), "codex"))  # director의 researcher 호출
        self.assertIsNotNone(hook.check(codex("jelly", "자유 문장"), "codex"))

    def test_other_tools_ignored(self):
        self.assertIsNone(hook.check({"tool_name": "Bash", "tool_input": {"command": "ls"}}, "claude"))

    def test_registered_roles_and_unrelated_agents(self):
        for runner, make in (("claude", claude), ("codex", codex)):
            for target in ("Explore", "general-purpose", "custom-agent", "director", "rio", "assistant", "buddy"):
                with self.subTest(runner=runner, target=target):
                    self.assertIsNone(hook.check(make(target, "자유 형식 입력"), runner))
            for target in hook.ROLES - hook.DOCUMENTER - hook.RESEARCHER:
                with self.subTest(runner=runner, target=target):
                    good = INPUT if target in hook.WORKER_REVIEWER else STATE
                    self.assertIsNone(hook.check(make(target, good), runner))
                    self.assertIsNotNone(hook.check(make(target, "자유 형식 입력"), runner))
            for target in hook.RESEARCHER:
                self.assertIsNone(hook.check(make(target, RESEARCH), runner))
                self.assertIsNotNone(hook.check(make(target, "자유 형식 입력"), runner))

    def test_root_and_subdirectory_have_same_decisions(self):
        root = Path(hook.__file__).resolve().parents[1]
        for runner, make in (("claude", claude), ("codex", codex)):
            for cwd in (root, root / "hooks"):
                for target, prompt, denied in (("jelly", INPUT, False), ("ricky", STATE, True),
                                               ("pepper", STATE, False), ("nico", RESEARCH, False),
                                               ("ricky", REFUTE, False), ("Explore", "자유 입력", False),
                                               ("director", "자유 입력", False), ("rio", "자유 입력", False),
                                               ("assistant", "자유 입력", False), ("buddy", "자유 입력", False)):
                    with self.subTest(runner=runner, cwd=cwd, target=target):
                        output = run_utf8(hook, make(target, prompt), "--runner", runner, cwd=cwd)
                        self.assertEqual(bool(output), denied)
                        if denied:
                            self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_reviewer_explicit_refutation_mode(self):
        invalid = (REFUTE + "\n작업 종류: 반증", REFUTE.replace("반증", "검수", 1),
                   REFUTE + "\n" + INPUT, REFUTE + "\n" + STATE,
                   REFUTE + "\n전체 대화: 이전 대화", REFUTE + "\n도구 출력: 로그",
                   REFUTE + "\n중간 설명: 작업 설명", REFUTE + "\n추론: 사고 과정",
                   REFUTE + "\n이전 대화 요약", REFUTE.replace("작업 종류: 반증\n", ""),
                   "작업 종류: 반증", "작업 종류: 반증\n주장: ")
        for runner, make in (("claude", claude), ("codex", codex)):
            for target in hook.REVIEWER:
                with self.subTest(runner=runner, target=target):
                    self.assertIsNone(hook.check(make(target, REFUTE), runner))
                    self.assertIsNone(hook.check(make(target, INPUT), runner))
                    for prompt in invalid:
                        self.assertIsNotNone(hook.check(make(target, prompt), runner), prompt)
        self.assertIsNone(hook.check(claude("ricky", REFUTE, sub=True), "claude"))
        self.assertIsNotNone(hook.check(claude("ricky", REFUTE + "\n전체 대화: 로그", sub=True), "claude"))

    def test_general_review_and_worker_allow_path_only(self):
        for runner, make in (("claude", claude), ("codex", codex)):
            for target in hook.WORKER_REVIEWER:
                for prompt in (INPUT + "\n절: 검수", INPUT + "\n항목: 1", REFUTE if target not in hook.REVIEWER else STATE):
                    self.assertIsNotNone(hook.check(make(target, prompt), runner))

    def test_deny_output_shape(self):
        out = hook.deny("x")["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))

    def test_stringio_main_preserves_protocol(self):
        data = codex("reviewer", REFUTE + "\n전체 대화: 로그")
        output = io.StringIO()
        with patch.object(sys, "argv", ["check_agent_input.py", "--runner", "codex"]), \
             patch.object(sys, "stdin", io.StringIO(json.dumps(data))), patch.object(sys, "stdout", output):
            self.assertEqual(hook.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_utf8_stdin_stdout(self):
        out = run_utf8(hook, claude("jelly", "이전 대화 요약"), "--runner", "claude")
        self.assertIn("입력 문서", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(run_utf8(hook, claude("jelly", INPUT), "--runner", "claude"), "")


if __name__ == "__main__":
    unittest.main()
