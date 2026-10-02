"""알림 도구를 구성하고 알림 스케줄러를 실행한다."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import discord
from claude_agent_sdk import create_sdk_mcp_server, tool

from config import HERE, WEEKDAY_NAMES, AgentConfig, RemindersConfig, log, tool_text

if TYPE_CHECKING:
    from bot import Runtime


# 알림 앞머리 문구가 붙어도 Discord 메시지 한도(2000자) 안에 들어가게 한다.
REMINDER_TEXT_MAX = 1500
REMINDERS_PATH = HERE / "reminders.json"
REMINDER_TOOL_NAMES = [
    "mcp__reminder__reminder_set",
    "mcp__reminder__reminder_repeat",
    "mcp__reminder__reminder_list",
    "mcp__reminder__reminder_cancel",
]


# 알림 설정 시간대의 현재 시각.
def reminder_now(reminders: RemindersConfig) -> datetime:
    return datetime.now(reminders.tz)


# 알림 목록을 파일에 원자적으로 저장한다.
def save_reminders(runtime: "Runtime") -> None:
    data = {"next_id": runtime.reminder_next_id, "reminders": runtime.reminders}
    tmp_path = REMINDERS_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    os.replace(tmp_path, REMINDERS_PATH)


# 저장된 알림 목록을 불러온다. 파일이 없거나 손상됐으면 빈 목록으로 시작한다.
def load_reminders(runtime: "Runtime") -> None:
    if not REMINDERS_PATH.is_file():
        return
    try:
        data = json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("알림 파일이 손상되어 건너뜁니다: %s", REMINDERS_PATH)
        return
    runtime.reminders = list(data.get("reminders", []))
    runtime.reminder_next_id = int(data.get("next_id", 1))


# '매일', '평일', '주말', '월,수,금' 같은 요일 표현을 요일 번호(월=0) 목록으로 바꾼다. 해석할 수 없으면 None이다.
def parse_reminder_days(raw: str) -> list[int] | None:
    raw = raw.strip()
    if raw == "매일":
        return list(range(7))
    if raw == "평일":
        return list(range(5))
    if raw == "주말":
        return [5, 6]
    days: set[int] = set()
    for part in re.split(r"[,\s]+", raw):
        if not part:
            continue
        name = part.removesuffix("요일")
        if len(name) != 1 or name not in WEEKDAY_NAMES:
            return None
        days.add(WEEKDAY_NAMES.index(name))
    return sorted(days) or None


# 'HH:MM' 형식의 시각을 검사하고 두 자리로 맞춘다. 잘못된 형식이면 None이다.
def parse_reminder_time(raw: str) -> str | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", raw.strip())
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


# 반복 요일 목록을 매일·매주 문구로 바꾼다.
def format_reminder_days(days: list[int]) -> str:
    if days == list(range(7)):
        return "매일"
    return "매주 " + ",".join(WEEKDAY_NAMES[day] for day in days)


# 알림 하나를 목록 표시 문구로 바꾼다.
def format_reminder(reminder: dict[str, Any]) -> str:
    if reminder["kind"] == "repeat":
        when = f"반복 {format_reminder_days(reminder['days'])} {reminder['time']}"
    else:
        at = datetime.fromisoformat(reminder["at"])
        when = f"한 번 {at:%Y-%m-%d} ({WEEKDAY_NAMES[at.weekday()]}) {at:%H:%M}"
    return f"#{reminder['id']} {when} {reminder['text']}"


# assistant 역할 전용 알림 도구를 만든다. 알림은 reminders.json에 저장되어 재시작해도 유지된다.
def build_reminder_server(
    channel: discord.abc.Messageable, runtime: "Runtime", agent: AgentConfig
) -> tuple[str, list[str], Any] | None:
    settings = runtime.config.reminders

    # 새 알림에 ID와 채널을 붙여 저장한다.
    def add_reminder(reminder: dict[str, Any]) -> dict[str, Any]:
        reminder = {"id": runtime.reminder_next_id, "channel_id": channel.id, "agent": agent.name, **reminder}
        runtime.reminder_next_id += 1
        runtime.reminders.append(reminder)
        save_reminders(runtime)
        return reminder

    # 알림 내용 길이를 검사하고 오류 문구를 반환한다.
    def check_text(text: str) -> str | None:
        if not text or len(text) > REMINDER_TEXT_MAX:
            return f"알림 내용은 1~{REMINDER_TEXT_MAX}자여야 합니다."
        return None

    # 몇 분 뒤 한 번 울릴 알림을 예약한다.
    @tool(
        "reminder_set",
        f"지정한 분 뒤에 채널로 알림을 한 번 보낸다. minutes는 1~{settings.max_minutes}이다.",
        {"minutes": int, "text": str},
    )
    async def reminder_set(args: dict[str, Any]) -> dict[str, Any]:
        minutes = args.get("minutes")
        text = str(args.get("text", "")).strip()
        if not isinstance(minutes, int) or not 1 <= minutes <= settings.max_minutes:
            return tool_text(f"minutes는 1~{settings.max_minutes}이어야 합니다.")
        error = check_text(text)
        if error:
            return tool_text(error)
        at = (reminder_now(settings) + timedelta(minutes=minutes)).replace(second=0, microsecond=0)
        reminder = add_reminder({"kind": "once", "at": at.isoformat(), "text": text})
        return tool_text(f"알림을 예약했습니다: {format_reminder(reminder)} ({settings.tz_label})")

    # 요일과 시각으로 반복 알림을 예약한다.
    @tool(
        "reminder_repeat",
        f"정해진 요일과 시각({settings.tz_label})마다 채널로 알림을 보낸다. "
        "days는 '매일', '평일', '주말' 또는 '월,수,금'처럼 쉼표로 구분한 요일이고, time은 'HH:MM'이다.",
        {"days": str, "time": str, "text": str},
    )
    async def reminder_repeat(args: dict[str, Any]) -> dict[str, Any]:
        days = parse_reminder_days(str(args.get("days", "")))
        if days is None:
            return tool_text("days는 '매일', '평일', '주말' 또는 '월,수,금' 형식이어야 합니다.")
        time_text = parse_reminder_time(str(args.get("time", "")))
        if time_text is None:
            return tool_text("time은 00:00~23:59 사이의 'HH:MM' 형식이어야 합니다.")
        text = str(args.get("text", "")).strip()
        error = check_text(text)
        if error:
            return tool_text(error)
        reminder = add_reminder(
            {"kind": "repeat", "days": days, "time": time_text, "text": text, "last_fired": None}
        )
        return tool_text(f"반복 알림을 예약했습니다: {format_reminder(reminder)} ({settings.tz_label})")

    # 현재 채널의 예약 알림을 보여 준다.
    @tool("reminder_list", "현재 시각과 현재 채널의 알림 목록을 보여 준다.", {})
    async def reminder_list(args: dict[str, Any]) -> dict[str, Any]:
        now = reminder_now(settings)
        lines = [f"현재 시각: {now:%Y-%m-%d} ({WEEKDAY_NAMES[now.weekday()]}) {now:%H:%M} ({settings.tz_label})"]
        items = [format_reminder(r) for r in runtime.reminders if r["channel_id"] == channel.id]
        lines += items or ["예약된 알림이 없습니다."]
        return tool_text("\n".join(lines))

    # 현재 채널의 알림 하나를 ID로 취소한다.
    @tool("reminder_cancel", "현재 채널의 알림을 번호로 취소한다.", {"id": int})
    async def reminder_cancel(args: dict[str, Any]) -> dict[str, Any]:
        reminder_id = args.get("id")
        for reminder in runtime.reminders:
            if reminder["id"] == reminder_id and reminder["channel_id"] == channel.id:
                runtime.reminders.remove(reminder)
                save_reminders(runtime)
                return tool_text(f"알림을 취소했습니다: {format_reminder(reminder)}")
        return tool_text(f"현재 채널에 #{reminder_id} 알림이 없습니다.")

    return "reminder", list(REMINDER_TOOL_NAMES), create_sdk_mcp_server(
        name="reminder",
        version="1.0.0",
        tools=[reminder_set, reminder_repeat, reminder_list, reminder_cancel],
    )


# 알림 하나를 등록한 봇 계정으로 채널에 보낸다. 허용 사용자를 멘션해 푸시 알림이 가게 한다.
async def send_reminder(runtime: Runtime, reminder: dict[str, Any], late_at: datetime | None) -> None:
    client = runtime.clients.get(reminder["agent"])
    if client is None:
        log.warning("reminder agent missing id=%s agent=%s", reminder["id"], reminder["agent"])
        return
    channel_id = reminder["channel_id"]
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            log.warning("reminder channel fetch failed id=%s channel=%s: %s", reminder["id"], channel_id, exc)
            return
    mention = " ".join(f"<@{user_id}>" for user_id in sorted(runtime.config.allowed_user_ids))
    prefix = f"{mention} " if mention else ""
    text = reminder["text"]
    if late_at is not None:
        body = f"⏰ 늦은 알림 (예정 {late_at:%m-%d %H:%M}): {text}"
    else:
        body = f"⏰ 알림: {text}"
    try:
        sent = await channel.send(prefix + body)
    except discord.HTTPException as exc:
        log.warning("reminder send failed id=%s agent=%s: %s", reminder["id"], reminder["agent"], exc)
        return
    runtime.append_chat(channel_id, reminder["agent"], f"(알림) {text}", sent.id)


# 지금 울릴 알림을 골라 보낸다. 중복 발송을 막으려고 보내기 전에 상태를 먼저 저장한다.
async def fire_due_reminders(runtime: Runtime, now: datetime) -> None:
    to_send: list[tuple[dict[str, Any], datetime | None]] = []
    for reminder in list(runtime.reminders):
        if reminder["kind"] == "once":
            at = datetime.fromisoformat(reminder["at"])
            if at > now:
                continue
            runtime.reminders.remove(reminder)
            late = now - at > timedelta(minutes=runtime.config.reminders.late_minutes)
            to_send.append((reminder, at if late else None))
            continue
        if now.weekday() not in reminder["days"]:
            continue
        hour, minute = map(int, reminder["time"].split(":"))
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # 봇이 꺼져 있어 유예 시간이 지난 회차는 건너뛰고 다음 회차를 기다린다.
        if not slot <= now < slot + timedelta(minutes=runtime.config.reminders.repeat_grace_minutes):
            continue
        if reminder.get("last_fired") == slot.isoformat():
            continue
        reminder["last_fired"] = slot.isoformat()
        to_send.append((reminder, None))

    if not to_send:
        return
    save_reminders(runtime)
    for reminder, late_at in to_send:
        await send_reminder(runtime, reminder, late_at)


# 알림 파일을 주기적으로 확인해 시각이 된 알림을 보낸다.
async def run_reminder_scheduler(runtime: Runtime) -> None:
    await runtime.ready.wait()

    while True:
        try:
            await fire_due_reminders(runtime, reminder_now(runtime.config.reminders))
        except Exception:
            log.exception("reminder check failed")
        await asyncio.sleep(runtime.config.reminders.check_seconds)
