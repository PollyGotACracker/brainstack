"""첨부·링크·이미지 설명을 처리하고 Discord 메시지를 분할한다."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import discord
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

from config import AGENT_ROOT, DISCORD_LIMIT, Config, LinksConfig, log, log_sdk_stderr

IMAGE_ATTACHMENT_DIRNAME = ".discord_attachments"
IMAGE_CONTENT_TYPE_PREFIX = "image/"
ATTACHMENT_ROOT = (AGENT_ROOT / IMAGE_ATTACHMENT_DIRNAME).resolve()
TEXT_ATTACHMENT_EXTENSIONS = {
    ".md", ".txt", ".log", ".csv", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sh", ".sql",
}


# Read 도구가 이미지 첨부 폴더 밖을 읽지 못하게 막는 PreToolUse 훅 설정을 만든다.
# 작업 디렉터리 안의 읽기는 권한 규칙 없이 승인되므로 config.json 같은 설정 파일을 훅으로 막는다.
def read_hooks(agent_name: str) -> dict[str, list[HookMatcher]]:
    # Read 대상이 첨부 폴더 밖이면 거부 결정을 반환한다.
    async def restrict_read(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        raw = str(input_data.get("tool_input", {}).get("file_path", ""))
        path = Path(raw) if Path(raw).is_absolute() else AGENT_ROOT / raw
        try:
            if raw and path.resolve().is_relative_to(ATTACHMENT_ROOT):
                return {}
        except (OSError, RuntimeError):
            pass
        log.warning("read blocked agent=%s path=%s", agent_name, raw)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Read는 첨부 폴더 안에서만 쓸 수 있다.",
            }
        }

    return {"PreToolUse": [HookMatcher(matcher="Read", hooks=[restrict_read])]}


LINK_PATTERN = re.compile(r"https?://\S+")


# 메시지의 링크 미리보기(임베드)를 대화 기록에 붙일 텍스트로 만든다. 링크가 없으면 None을 반환한다.
# Discord는 미리보기를 메시지가 올라온 뒤 늦게 붙이기도 해서, 비어 있으면 잠시 기다렸다 다시 가져온다.
async def fetch_link_previews(message: discord.Message, links: LinksConfig) -> str | None:
    if not LINK_PATTERN.search(message.content):
        return None
    embeds = list(message.embeds)
    for _ in range(links.preview_retries):
        if embeds:
            break
        await asyncio.sleep(links.preview_retry_seconds)
        try:
            embeds = list((await message.channel.fetch_message(message.id)).embeds)
        except discord.HTTPException:
            return None

    lines = []
    for embed in embeds:
        parts = []
        if embed.title:
            parts.append(f"제목: {embed.title}")
        if embed.author and embed.author.name:
            parts.append(f"작성자: {embed.author.name}")
        if embed.description:
            parts.append(f"설명: {embed.description.strip()[:links.description_max_chars]}")
        if not parts:
            continue
        url_part = f" ({embed.url})" if embed.url else ""
        lines.append(f"[링크 미리보기] {' / '.join(parts)}{url_part}")
    return "\n".join(lines) or None


# 첨부가 텍스트 문서인지 형식과 확장자로 판정한다.
def is_text_attachment(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").split(";")[0].strip()
    if content_type.startswith("text/") or content_type == "application/json":
        return True
    return Path(attachment.filename).suffix.lower() in TEXT_ATTACHMENT_EXTENSIONS


# 저장한 첨부 문서 하나. 크기 초과로 저장하지 않았으면 path가 None이다.
@dataclass
class SavedDocument:
    name: str
    size: int
    path: Path | None


# 메시지에 첨부된 이미지와 텍스트 문서를 base_dir 하위에 저장하고, (이미지 경로, 문서 목록)을 반환한다.
# 크기 제한을 넘는 문서는 내려받지 않고 path 없이 목록에만 넣는다.
async def save_attachments(
    message: discord.Message, base_dir: Path, config: Config
) -> tuple[list[Path], list[SavedDocument]]:
    images = [a for a in message.attachments if (a.content_type or "").startswith(IMAGE_CONTENT_TYPE_PREFIX)]
    documents = [a for a in message.attachments if a not in images and is_text_attachment(a)]
    if not images and not documents:
        return [], []

    dest_dir = base_dir / IMAGE_ATTACHMENT_DIRNAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    prune_old_attachments(dest_dir, datetime.now().timestamp(), config.chat.history_hours * 3600)

    # 첨부 하나를 저장하고 저장 경로를 반환한다. 실패하면 None을 반환한다.
    async def save(attachment: discord.Attachment) -> Path | None:
        safe_name = Path(attachment.filename).name or "attachment"
        dest_path = dest_dir / f"{message.id}_{attachment.id}_{safe_name}"
        try:
            await attachment.save(dest_path)
        except discord.HTTPException:
            log.warning("failed to save attachment id=%s name=%s", attachment.id, attachment.filename)
            return None
        return dest_path

    image_paths = [path for path in [await save(a) for a in images] if path is not None]
    saved_documents: list[SavedDocument] = []
    for attachment in documents:
        if attachment.size > config.attachments.text_max_kb * 1024:
            saved_documents.append(SavedDocument(attachment.filename, attachment.size, None))
            continue
        path = await save(attachment)
        if path is not None:
            saved_documents.append(SavedDocument(attachment.filename, attachment.size, path))
    return image_paths, saved_documents


# 바이트 수를 B·KB 단위 문구로 바꾼다.
def format_bytes(size: int) -> str:
    return f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B"


# 첨부 문서를 대화 기록용 문구로 만든다. 앞부분만 넣고, 나머지는 Read로 열 경로를 적는다.
def build_document_trigger_text(documents: list[SavedDocument], preview_chars: int) -> str:
    parts = []
    for doc in documents:
        size = format_bytes(doc.size)
        if doc.path is None:
            parts.append(f"[첨부 문서 크기 초과] {doc.name} ({size})")
            continue
        try:
            body = doc.path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            parts.append(f"[첨부 문서 읽기 실패] {doc.name} ({size})")
            continue
        # 기록 길이 제한으로 뒤가 잘려도 경로가 남도록 경로를 머리줄에 둔다.
        if len(body) > preview_chars:
            header = f"[첨부 문서] {doc.name} ({size}) 앞 {preview_chars}자만 표시, 전체는 Read로 연다: {doc.path}"
            parts.append(f"{header}\n{body[:preview_chars]}\n…(이하 생략)")
        else:
            parts.append(f"[첨부 문서] {doc.name} ({size})\n{body}")
    return "\n".join(parts)


# 첨부 폴더에서 수정 시각이 ttl_seconds보다 오래된 파일을 지운다.
def prune_old_attachments(dest_dir: Path, now: float, ttl_seconds: int) -> None:
    for path in dest_dir.iterdir():
        try:
            if path.is_file() and now - path.stat().st_mtime > ttl_seconds:
                path.unlink()
        except OSError:
            log.warning("failed to prune attachment %s", path)


CAPTION_SYSTEM_PROMPT = (
    "너는 이미지 설명기다. 주어진 경로의 이미지를 Read 도구로 열어 보이는 내용을 한국어로 설명한다.\n"
    "- 등장 대상(사람, 동물의 종, 사물), 색, 옷차림, 배경, 이미지 속 글자를 사실대로 적는다.\n"
    "- 확실하지 않은 판별은 '~로 보인다'로 적는다.\n"
    "- 이미지가 여러 장이면 '이미지 1:', '이미지 2:'로 구분한다.\n"
    "- 이미지 한 장당 2~4문장으로 설명만 출력한다."
)


# 페르소나 없는 별도 호출로 이미지 설명을 한 번 만든다. 실패하면 None을 반환한다.
async def caption_images(paths: list[Path], model: str) -> str | None:
    lines = "\n".join(f"- {path}" for path in paths)
    options = ClaudeAgentOptions(
        system_prompt=CAPTION_SYSTEM_PROMPT,
        tools=["Read"],
        allowed_tools=["Read"],
        cwd=str(AGENT_ROOT),
        permission_mode="default",
        hooks=read_hooks("caption"),
        setting_sources=[],
        strict_mcp_config=True,
        max_turns=len(paths) + 2,
        model=model,
        stderr=log_sdk_stderr,
        max_buffer_size=10 * 1024 * 1024,
    )
    result = ""
    try:
        async for sdk_message in query(prompt=f"아래 이미지를 설명한다:\n{lines}", options=options):
            if isinstance(sdk_message, ResultMessage):
                result = getattr(sdk_message, "result", "") or ""
    except Exception:
        log.exception("image caption failed paths=%s", paths)
        return None
    return result.strip() or None


# 이미지가 있는 사용자 메시지를 대화 기록용 트리거 문구로 만든다.
# 설명을 맨 앞에 두어 기록 길이 제한으로 잘릴 때도 설명이 남게 한다.
def build_image_trigger_text(text: str, caption: str | None, paths: list[Path]) -> str:
    header = f"[이미지 설명] {caption}" if caption else "[이미지 설명 실패]"
    lines = "\n".join(f"- {path}" for path in paths)
    note = f"[첨부 이미지 경로] 세부 확인이 필요할 때만 Read로 연다:\n{lines}"
    return "\n".join(part for part in (header, text, note) if part)


# 긴 본문을 Discord 한도에 맞게 나눈다.
def split_message(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
    """조각 경계에서 fenced code block을 닫고 다시 열며 본문을 나눈다."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    fence: str | None = None

    # 지금까지 모은 조각을 코드 블록을 닫아 결과에 넣는다.
    def flush() -> None:
        nonlocal current
        if not current:
            return
        body = current.rstrip()
        if fence and not body.endswith("```"):
            body += "\n```"
        chunks.append(body)
        current = (fence + "\n") if fence else ""

    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.lstrip()
        fence_line = stripped.startswith("```")

        reserve = 4 if fence else 0
        if len(current) + len(raw_line) + reserve > limit:
            flush()

        if len(raw_line) > limit - 8:
            remaining = raw_line
            while remaining:
                room = max(1, limit - len(current) - (4 if fence else 0))
                current += remaining[:room]
                remaining = remaining[room:]
                if remaining:
                    flush()
        else:
            current += raw_line

        if fence_line:
            token = stripped.rstrip("\r\n")
            if fence is None:
                fence = token
            else:
                fence = None

    if current.strip():
        body = current.rstrip()
        if fence and not body.endswith("```"):
            body += "\n```"
        chunks.append(body)

    return [chunk for chunk in chunks if chunk]
