"""Codex hooks·config·전역 지침 연결이다."""
from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from sub_merge import dump_json, eol_of, load_json, prune, read_text, remove_hooks, sync_hooks, write_text
from sub_paths import CODEX_AGENTS, CODEX_CONFIG, CODEX_HOOKS, PRINCIPLE

FEATURES_HEADER = re.compile(r"^\s*\[features\]\s*(#.*)?$")
TABLE_HEADER = re.compile(r"^\s*\[")
HOOKS_TRUE = re.compile(r"^\s*hooks\s*=\s*true\s*(#.*)?$")


# ~/.codex/hooks.json 내용을 settings 원본에 맞추고 새 기록 항목을 반환한다.
def sync_codex_hooks(data: dict, source: dict, entry: dict | None, preview: list[str]) -> dict:
    entry = entry or {"hooks": {}, "created": []}
    created = list(entry.get("created", []))
    hooks = sync_hooks(data, source["hooks"], entry.get("hooks", {}), created, preview)
    return {"hooks": hooks, "created": created}


def uninstall_codex_hooks(record: dict) -> None:
    data = load_json(CODEX_HOOKS)
    remove_hooks(data, record["hooks"])
    prune(data, record["created"])
    write_text(CODEX_HOOKS, dump_json(data))


# ---------------------------------------------------------------- config.toml


# config.toml의 [features] hooks 값을 반환한다.
def features_hooks(text: str):
    return tomllib.loads(text).get("features", {}).get("hooks")


# [features]에 hooks = true를 넣은 새 내용과 기록을 반환한다.
# hooks 키가 이미 있으면 값과 관계없이 None이다.
def add_features_hooks(text: str) -> tuple[str, dict] | None:
    if features_hooks(text) is not None:
        return None
    eol = eol_of(text)
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if FEATURES_HEADER.match(line.rstrip("\r\n")):
            lines.insert(index + 1, "hooks = true" + eol)
            new = "".join(lines)
            record = {"mode": "insert", "added": "hooks = true" + eol}
            break
    else:
        prefix = "" if not text else (eol if text.endswith("\n") else eol + eol)
        added = prefix + "[features]" + eol + "hooks = true" + eol
        new = text + added
        record = {"mode": "append", "added": added}
    return new, record


# config.toml에 [features] hooks 키가 없을 때만 hooks = true를 추가한다.
def sync_codex_config(text: str) -> tuple[str | None, dict | None, list[str]]:
    result = add_features_hooks(text)
    if result is None:
        return None, None, []
    return result[0], result[1], [f"추가 [features] hooks = true ({result[1]['mode']})"]


# install이 넣은 [features] hooks = true를 지운다.
def remove_features_hooks(text: str, record: dict) -> str:
    if record["mode"] == "append" and text.endswith(record["added"]):
        return text[: len(text) - len(record["added"])]
    lines = text.splitlines(keepends=True)
    in_features = False
    for index, line in enumerate(lines):
        bare = line.rstrip("\r\n")
        if TABLE_HEADER.match(bare):
            in_features = bool(FEATURES_HEADER.match(bare))
            continue
        if in_features and HOOKS_TRUE.match(bare):
            del lines[index]
            break
    return "".join(lines)


def uninstall_codex_config(record: dict) -> None:
    write_text(CODEX_CONFIG, remove_features_hooks(read_text(CODEX_CONFIG), record))


# ---------------------------------------------------------------- AGENTS.md 연결


# ~/.codex/AGENTS.md가 AGENTS.principle.md에 연결된 방식을 반환한다.
# 연결이 아니면 None이다.
def agents_link_state() -> str | None:
    if CODEX_AGENTS.is_symlink():
        target = Path(os.path.realpath(CODEX_AGENTS))
        return "symlink" if target == PRINCIPLE.resolve() else None
    if CODEX_AGENTS.is_file() and os.path.samefile(CODEX_AGENTS, PRINCIPLE):
        return "hardlink"
    return None


# ~/.codex/AGENTS.md를 symlink로, 실패하면 hardlink로 연결한다.
# 둘 다 실패하면 예외를 낸다.
def make_agents_link() -> str:
    CODEX_AGENTS.parent.mkdir(parents=True, exist_ok=True)
    if CODEX_AGENTS.is_symlink() or CODEX_AGENTS.exists():
        CODEX_AGENTS.unlink()
    try:
        CODEX_AGENTS.symlink_to(PRINCIPLE)
        return "symlink"
    except OSError as symlink_error:
        try:
            os.link(PRINCIPLE, CODEX_AGENTS)
            return "hardlink"
        except OSError as hardlink_error:
            raise RuntimeError(
                f"{CODEX_AGENTS} 연결 실패: symlink({symlink_error}), hardlink({hardlink_error})"
            ) from hardlink_error


# 연결할 계획을 반환한다.
# 이미 연결돼 있으면 None이다.
def sync_codex_agents() -> tuple[str | None, dict | None, list[str]]:
    if agents_link_state() is not None:
        return None, None, []
    exists = CODEX_AGENTS.exists() or CODEX_AGENTS.is_symlink()
    preview = [
        ("기존 파일 백업 후 " if exists else "") + f"연결 -> {PRINCIPLE}",
        "      symlink 시도, 실패하면 hardlink",
    ]
    return "link", {}, preview


# install이 만든 연결을 지운다.
def uninstall_codex_agents(record: dict) -> None:
    if CODEX_AGENTS.is_symlink() or CODEX_AGENTS.exists():
        CODEX_AGENTS.unlink()
