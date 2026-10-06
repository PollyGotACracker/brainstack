"""Claude 전역 설정과 Claude 전역 지침의 병합·재반영·제거이다."""
from __future__ import annotations

from sub_merge import (drop_value, dump_json, ensure, eol_of, get_path, load_json, prune, read_text, remove_hooks,
                    sync_hooks, sync_values, write_text)
from sub_paths import CLAUDE_MD, CLAUDE_SETTINGS

CONTAINERS = ("env", "permissions", "hooks")
EMPTY_RECORD = {"values": {}, "env": {}, "permissions": {}, "hooks": {}, "created": []}


# permissions 목록을 settings 원본에 맞추고 install이 소유한 규칙을 반환한다.
# 사용자 규칙은 기록하지 않고 보존한다.
def sync_permissions(data: dict, source: dict, owned: dict, created: list, preview: list[str]) -> dict:
    result: dict[str, list] = {}
    kinds = list(source) + [kind for kind in owned if kind not in source]
    if not kinds:
        return result
    permissions = ensure(data, "permissions", dict, created, ["permissions"]) if source else data.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}
    for kind in kinds:
        desired = source.get(kind, [])
        mine = owned.get(kind, [])
        if desired:
            array = ensure(permissions, kind, list, created, ["permissions", kind])
        else:
            array = permissions.get(kind) if isinstance(permissions.get(kind), list) else []
        kept = []
        for rule in mine:
            if rule in desired:
                if rule in array:
                    kept.append(rule)
            elif rule in array:
                array.remove(rule)
                preview.append(f"삭제 permissions.{kind}: {rule}")
        for rule in desired:
            if rule not in array:
                array.append(rule)
                kept.append(rule)
                preview.append(f"추가 permissions.{kind}: {rule}")
        if kept:
            result[kind] = kept
    return result


# Claude 전역 설정을 settings 원본에 맞추고 새 기록 항목을 반환한다.
# entry는 기존 설치 기록이며 install이 넣은 키·규칙·그룹과 만든 컨테이너를 이어받는다.
def sync_claude_settings(data: dict, source: dict, entry: dict | None, preview: list[str]) -> dict:
    old = {**EMPTY_RECORD, **(entry or {})}
    record: dict = {"values": {}, "env": {}, "permissions": {}, "hooks": {}, "created": list(old["created"])}
    created = record["created"]

    scalars = {key: value for key, value in source.items() if key not in CONTAINERS}
    record["values"] = sync_values(data, scalars, old["values"], "", preview)

    env_source = source.get("env", {})
    env = ensure(data, "env", dict, created, ["env"]) if env_source else data.get("env")
    if env_source or old["env"]:
        if not isinstance(env, dict):
            raise ValueError("env 형식이 dict가 아닙니다.")
        record["env"] = sync_values(env, env_source, old["env"], "env.", preview)

    record["permissions"] = sync_permissions(data, source.get("permissions", {}), old["permissions"], created, preview)
    record["hooks"] = sync_hooks(data, source.get("hooks", {}), old["hooks"], created, preview)

    prune(data, created)
    created[:] = [path for path in created if get_path(data, path) is not None]
    return record


# Claude 전역 지침의 import 줄을 settings 원본에 맞춘다.
# (새 내용 또는 None, 새 기록 항목 또는 None, 미리보기)를 반환한다.
# 기록된 줄이 바뀌었으면 같은 위치에서 교체하고, 없으면 끝에 추가한다.
# 기록 항목은 install이 넣은 줄(appended)과 파일 생성 여부(created)이다.
def sync_claude_import(text: str, line: str, entry: dict | None) -> tuple[str | None, dict | None, list[str]]:
    if entry is not None and entry["appended"] in text and entry["appended"].strip() != line:
        appended = entry["appended"]
        old_line = appended.strip()
        index = text.rfind(appended)
        new_appended = appended.replace(old_line, line)
        new = text[:index] + new_appended + text[index + len(appended):]
        return new, {"created": entry["created"], "appended": new_appended}, [f"교체 {old_line} -> {line}"]
    if line in (l.strip() for l in text.splitlines()):
        return None, None, []
    eol = eol_of(text)
    prefix = "" if not text or text.endswith("\n") else eol
    appended = prefix + line + eol
    record = {"created": not CLAUDE_MD.exists(), "appended": appended}
    return text + appended, record, [("생성 후 " if record["created"] else "") + f"추가 {line}"]


def uninstall_claude_settings(record: dict) -> None:
    data = load_json(CLAUDE_SETTINGS)
    for key in record["values"]:
        drop_value(data, key)
    for key in record["env"]:
        drop_value(data.get("env"), key)
    for kind, rules in record["permissions"].items():
        array = get_path(data, ["permissions", kind])
        if isinstance(array, list):
            for rule in rules:
                if rule in array:
                    array.remove(rule)
    remove_hooks(data, record["hooks"])
    prune(data, record["created"])
    write_text(CLAUDE_SETTINGS, dump_json(data))


def uninstall_claude_md(record: dict) -> None:
    if not CLAUDE_MD.is_file():
        return
    text = read_text(CLAUDE_MD)
    appended = record["appended"]
    index = text.rfind(appended)
    if index >= 0:
        text = text[:index] + text[index + len(appended):]
    if record["created"] and not text.strip():
        CLAUDE_MD.unlink()
    else:
        write_text(CLAUDE_MD, text)
