"""응답 제어 계약과 Discord 전송 전 형식 오류 처리를 확인한다."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


DISCORD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DISCORD_ROOT / "bot"))
bot = importlib.import_module("bot")
config_module = importlib.import_module("config")
prompts_module = importlib.import_module("prompts")


class ChatResponseControlTests(unittest.TestCase):
    def test_valid_responses(self) -> None:
        cases = [
            ("안녕하세요.\n[[next:rio]]", ("안녕하세요.", "rio", None)),
            ("[[react:👍]]\n[[next:stop]]", ("", "stop", "👍")),
            ("좋습니다.\n[[react:👍]]\n[[next:jelly]]", ("좋습니다.", "jelly", "👍")),
            ("첫 줄\n둘째 줄\n[[next:stop]]", ("첫 줄\n둘째 줄", "stop", None)),
            ("  본문\r\n[[REACT: 👍 ]]\r\n[[NEXT:RIO]]\r\n", ("본문", "rio", "👍")),
            ("[[next:stop]]", ("", "stop", None)),
            ("[[react:<:custom:123>]]\n[[next:rio]]", ("", "rio", "<:custom:123>")),
            # 마지막 next 줄이 빠진 응답은 전체를 본문으로 보고 stop으로 끝낸다.
            ("", ("", "stop", None)),
            ("본문", ("본문", "stop", None)),
        ]
        for response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(prompts_module.parse_chat_result(response), expected)

    def test_wait_and_react_without_next(self) -> None:
        cases = [
            ("본문\n[[wait:user]]", ("본문", "stop", None, True)),
            ("본문\n[[react:👍]]", ("본문", "stop", "👍", False)),
            ("본문\n[[react:👍]]\n[[wait:user]]", ("본문", "stop", "👍", True)),
            ("[[react:👍]]", ("", "stop", "👍", False)),
        ]
        for response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(prompts_module.parse_chat_controls(response), expected)

    def test_invalid_responses(self) -> None:
        cases = [
            "[[next:rio]]\n[[next:stop]]",
            "[[next:rio]]\n본문",
            "본문 [[next:stop]]",
            "[[next:stop]]\n[[react:👍]]",
            "[[react:👍]]\n[[react:🎉]]\n[[next:stop]]",
            "[[react:👍]]\n본문\n[[next:stop]]",
            "본문 [[react:👍]]\n[[next:stop]]",
            "[[react:👍]]\n\n[[next:stop]]",
            "[[next:]]", "[[next:two names]]", "[[next:stop]",
            "[[react:]]\n[[next:stop]]",
            "[[react:   ]]\n[[next:stop]]",
            "[[react:👍]\n[[next:stop]]",
            "[[NEXT:rio]]\n본문\n[[next:stop]]",
            "[[ react:👍]]\n[[next:stop]]",
        ]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    prompts_module.parse_chat_result(response)


class ChatResponseDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def run_turn(
        self, response: str, *, reaction_trigger: bool = True, chat_config=None,
        turn_index: int = 1, turn_limit: int = 1, autonomous: bool = False,
    ):
        channel = SimpleNamespace(
            id=123, name="test", guild=SimpleNamespace(name="test"),
            typing=Mock(return_value=AsyncMock()),
            send=AsyncMock(return_value=SimpleNamespace(id=456)),
            get_partial_message=Mock(return_value=SimpleNamespace(add_reaction=AsyncMock())),
        )
        runtime = SimpleNamespace(
            ready=SimpleNamespace(wait=AsyncMock()),
            render_chat_history=Mock(return_value=""),
            chat_last_message={123: SimpleNamespace(id=789, author=SimpleNamespace(id=2))},
            chat_pending={}, append_chat=Mock(), chat_last_user_id={},
            config=SimpleNamespace(chat_model_for=Mock(return_value=("test", "low")),
                                   chat=chat_config if chat_config is not None else SimpleNamespace(sdk_max_turns=1),
                                   chat_topics={}, chat_channels=set()),
        )
        client = SimpleNamespace(
            runtime=runtime, _refresh_request_prompt=Mock(), get_channel=Mock(return_value=channel),
            _react_target_label=Mock(return_value="사용자 메시지"),
            _react_target_author=Mock(return_value="사용자"),
            agent=SimpleNamespace(name="jelly", role="worker", tools=[]),
            user=SimpleNamespace(id=1), _request_prompt="test",
        )
        prompts = []
        options_factory = Mock()

        async def fake_query(*, prompt, options):
            prompts.append(prompt)
            yield SimpleNamespace(result=response, subtype="success", num_turns=1)

        with (
            patch.object(bot, "query", fake_query),
            patch.object(bot, "ResultMessage", SimpleNamespace),
            patch.object(bot, "ClaudeAgentOptions", options_factory),
            patch.object(bot, "read_hooks", return_value={}),
            patch.object(bot, "build_server_channels_server", return_value=None),
            patch.object(bot, "ROLE_TOOL_BUILDERS", {}),
        ):
            next_name = await bot.AgentBot._handle_chat_turn(
                client, 123, turn_index=turn_index, turn_limit=turn_limit,
                autonomous=autonomous, reaction_trigger=reaction_trigger,
            )
        runtime.sdk_options = options_factory.call_args.kwargs
        return next_name, channel, runtime, prompts[0]

    async def test_loaded_sdk_turn_limit_reaches_options(self) -> None:
        for value in (None, 4):
            with self.subTest(value=value):
                raw = json.loads((DISCORD_ROOT / "config.example.json").read_text(encoding="utf-8"))
                if value is None:
                    del raw["chat"]["sdk_max_turns"]
                else:
                    raw["chat"]["sdk_max_turns"] = value
                chat_config = config_module.load_settings_sections(raw)["chat"]
                _, _, runtime, _ = await self.run_turn("[[next:stop]]", chat_config=chat_config)
                self.assertIn("max_turns", runtime.sdk_options)
                self.assertEqual(runtime.sdk_options["max_turns"], value)

    async def test_invalid_control_never_reaches_discord(self) -> None:
        for response in (
            "본문\n[[next:rio]]\n[[next:stop]]",
            "[[react:👍]]\n본문\n[[next:stop]]",
        ):
            with self.subTest(response=response):
                next_name, channel, runtime, _ = await self.run_turn(response)
                self.assertIsNone(next_name)
                channel.send.assert_not_awaited()
                channel.get_partial_message.assert_not_called()
                runtime.append_chat.assert_not_called()

    async def test_reaction_only_and_prompt_contract(self) -> None:
        next_name, channel, runtime, prompt = await self.run_turn("[[react:👍]]\n[[next:stop]]")
        self.assertEqual(next_name, "stop")
        channel.send.assert_not_awaited()
        channel.get_partial_message.return_value.add_reaction.assert_awaited_once_with("👍")
        runtime.append_chat.assert_called_once()
        self.assertNotIn("리액션만 할 때도 next는 필요하다", prompt)
        self.assertNotIn("next는 정확히 하나, react는 최대 하나", prompt)
        runtime_prompt = (DISCORD_ROOT / "prompts" / "RUNTIME.md").read_text(encoding="utf-8")
        self.assertIn("next는 정확히 하나, react는 최대 하나", runtime_prompt)
        self.assertIn("다음 줄에 필수 `[[next:...]]`", runtime_prompt)

    async def test_only_body_is_sent(self) -> None:
        next_name, channel, runtime, _ = await self.run_turn("본문\n[[react:👍]]\n[[next:rio]]")
        self.assertEqual(next_name, "rio")
        channel.send.assert_awaited_once_with("본문")
        channel.get_partial_message.return_value.add_reaction.assert_awaited_once_with("👍")
        self.assertNotIn("[[", runtime.append_chat.call_args.args[2])

    async def test_body_without_next_is_sent_and_stops(self) -> None:
        next_name, channel, runtime, _ = await self.run_turn("본문", reaction_trigger=False)
        self.assertEqual(next_name, "stop")
        channel.send.assert_awaited_once_with("본문")
        runtime.append_chat.assert_called_once()

    async def test_user_request_scope_and_unfinished_answers(self) -> None:
        _, _, _, prompt = await self.run_turn("본문\n[[next:stop]]", reaction_trigger=False)
        # 턴 지시문과 다음 화자 기준 문장은 프롬프트에서 제거됐다.
        for removed in (
            "현재 대화의 주제를 먼저 확인하고",
            "질문·요청·교정이 있으면 그 내용을 기준으로 답한다",
            "작업 요청에서는 사용자 의도에 맞는 직전 발언만 이어받는다",
            "질문이나 요청이 없는 채팅이면 화제에 대한 캐릭터의 반응으로 답한다",
            "작업 요청이면 현재 요청에서 답할 내용이나 응답 차례가 남은 캐릭터를 고른다",
            "작업 요청에서 이번 발언이 다른 캐릭터의 주장을 반박하거나 정정했으면 그 캐릭터를 고른다",
            "채팅이면 Response control 절의 사용자가 시작한 채팅 기준으로 고른다",
            "캐릭터가 사용자에게 질문하거나 확인을 요청하면 stop을 고른다",
        ):
            self.assertNotIn(removed, prompt)
        self.assertNotIn("담당 역할 연결", prompt)
        self.assertNotIn("질문, 요청, 교정을 기준으로 말한다", prompt)
        self.assertNotIn("단순 질문을 별도 조사·검색·요약 과제로 확대하지 않는다", prompt)
        self.assertNotIn("마무리됐", prompt)
        self.assertNotIn("사용자의 답을 기다리", prompt)
        self.assertNotIn("최소", prompt)
        runtime_prompt = (DISCORD_ROOT / "prompts" / "RUNTIME.md").read_text(encoding="utf-8")
        for removed in (
            "현재 대화의 주제를 먼저 확인하고 그 주제를 기준으로 답한다",
            "작업 요청에서는 사용자가 꺼낸 주제를 기준으로 답한다",
            "채팅에서는 대화 소재로 새 화제를 꺼내도 된다",
            "사용자가 논점 이탈을 지적하면 교정된 질문에 바로 답한다",
            "다음 캐릭터는 작업 요청에서 답할 내용이나 지정된 응답 차례가 남으면 이어 말한다",
            "채팅의 이어 말하기는 `Response control` 절의 채팅 기준을 따른다",
            "사용자가 시작한 작업 요청에서 다음 화자는 남은 답변이나 지정된 응답 차례를 맡을 캐릭터로 고른다",
            "사용자가 시작한 채팅에서 다음 화자는",
            "캐릭터가 사용자에게 질문하거나 확인을 요청하면 `[[next:stop]]`을 출력한다",
        ):
            self.assertNotIn(removed, runtime_prompt)
        self.assertNotIn("단순 질문을 별도 조사·검색·요약 과제로 확대하지 않는다", runtime_prompt)
        self.assertNotIn("마무리됐", runtime_prompt)
        self.assertNotIn("사용자의 답을 기다리", runtime_prompt)
        self.assertNotIn("현재 사용자 요청 안에서 답할 내용", runtime_prompt)
        _, _, _, auto_prompt = await self.run_turn(
            "본문\n[[next:stop]]", reaction_trigger=False, turn_index=2, turn_limit=3, autonomous=True,
        )
        self.assertNotIn("마무리됐", auto_prompt)

    async def test_no_closing_instruction(self) -> None:
        # 턴 한도는 chat_loop가 강제하므로 마지막 턴 안내를 넣지 않는다.
        closing = "이번 발언이 이 대화의 마지막 발언이다"
        for autonomous in (False, True):
            with self.subTest(autonomous=autonomous, turn="last"):
                _, _, _, prompt = await self.run_turn(
                    "본문\n[[next:stop]]", reaction_trigger=False,
                    turn_index=3, turn_limit=3, autonomous=autonomous,
                )
                self.assertNotIn(closing, prompt)
                self.assertNotIn("화제를 마무리하는 말로 끝내고 [[next:stop]]을 출력한다", prompt)
            with self.subTest(autonomous=autonomous, turn="before_last"):
                _, _, _, prompt = await self.run_turn(
                    "본문\n[[next:stop]]", reaction_trigger=False,
                    turn_index=2, turn_limit=3, autonomous=autonomous,
                )
                self.assertNotIn(closing, prompt)
        with self.subTest(turn="reaction"):
            _, _, _, prompt = await self.run_turn(
                "[[react:👍]]\n[[next:stop]]", reaction_trigger=True, turn_index=1, turn_limit=1,
            )
            self.assertNotIn(closing, prompt)

    async def test_handoff_instruction_only_on_user_first_turn(self) -> None:
        handoff = "사용자 발언이 다른 캐릭터에게 한 말이면 본문 없이 그 캐릭터의 [[next:<내부 ID>]] 줄만 출력한다."
        cases = [
            ("user_first", dict(turn_index=1, turn_limit=6, autonomous=False, reaction_trigger=False), True),
            ("user_second", dict(turn_index=2, turn_limit=6, autonomous=False, reaction_trigger=False), False),
            ("auto_first", dict(turn_index=1, turn_limit=6, autonomous=True, reaction_trigger=False), False),
            ("auto_second", dict(turn_index=2, turn_limit=6, autonomous=True, reaction_trigger=False), False),
            ("reaction", dict(turn_index=1, turn_limit=1, autonomous=False, reaction_trigger=True), False),
        ]
        for name, kwargs, expected in cases:
            with self.subTest(turn=name):
                _, _, _, prompt = await self.run_turn("[[next:stop]]", **kwargs)
                self.assertNotIn(handoff, prompt)

    async def test_reaction_turn_instruction(self) -> None:
        _, _, _, prompt = await self.run_turn("[[next:stop]]", reaction_trigger=True)
        self.assertIn("이번 턴은 리액션이 트리거다. ", prompt)
        self.assertIn("할 말이 있으면 캐릭터의 말로 짧게 반응한다. ", prompt)
        self.assertIn(
            "다른 사람 메시지에 이모지로만 반응하려면 [[react:<이모지>]] 줄과 [[next:stop]] 줄만 출력한다. ",
            prompt,
        )
        self.assertIn("반응할 것이 없으면 [[next:stop]] 한 줄만 출력한다.", prompt)
        self.assertNotIn("출력해도 된다", prompt)

    async def test_handoff_without_body_is_not_sent(self) -> None:
        next_name, channel, runtime, _ = await self.run_turn(
            "[[next:jelly]]", reaction_trigger=False, turn_index=1, turn_limit=6,
        )
        self.assertEqual(next_name, "jelly")
        channel.send.assert_not_awaited()
        channel.get_partial_message.assert_not_called()
        runtime.append_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
