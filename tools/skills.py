#!/usr/bin/env python3
"""shared/skills의 skill을 사용자 전역 skill 폴더에 연결하고 연결 상태를 확인한다.

check: 연결 상태, 중복, Hermes 설정을 출력한다. 파일을 바꾸지 않는다.
link:  빈 자리에 링크를 만들고, 원본이 없어진 shared 링크를 지운다.
       실제 폴더와 다른 곳을 가리키는 링크는 건드리지 않는다.
"""

from __future__ import annotations

import filecmp
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

SOURCE = (Path(__file__).resolve().parent.parent / "shared" / "skills").resolve()
HOME = Path.home()

# 링크를 만드는 폴더. (표시 이름, skill 폴더, 사용하는 도구)
LINK_DIRS = [
    ("Claude Code", HOME / ".claude" / "skills", "Claude Code"),
    (".agents", HOME / ".agents" / "skills", "Codex, Cursor, OpenClaw"),
]
# 링크를 만들지 않고 중복만 확인하는 폴더.
DUPLICATE_DIRS = [
    (".codex", HOME / ".codex" / "skills"),
    (".cursor", HOME / ".cursor" / "skills"),
]
HERMES_CONFIG = HOME / ".hermes" / "config.yaml"
HERMES_LINE = "skills:\n  external_dirs:\n    - ~/.agents/skills"


# 링크(symlink 또는 junction)인지 확인한다.
def is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


# 링크가 가리키는 실제 경로를 반환한다.
# 링크가 아니면 None이다.
def link_target(path: Path) -> Path | None:
    if not is_link(path):
        return None
    return Path(os.path.realpath(path))


# 두 폴더의 파일 구성과 내용이 모두 같은지 확인한다.
def same_tree(left: Path, right: Path) -> bool:
    cmp = filecmp.dircmp(left, right)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(left, right, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(left / name, right / name) for name in cmp.common_dirs)


# shared/skills에서 SKILL.md가 있는 폴더를 skill로 읽는다.
def read_skills() -> list[Path]:
    if not SOURCE.is_dir():
        raise SystemExit(f"{SOURCE}가 없습니다.")
    return sorted(p for p in SOURCE.iterdir() if (p / "SKILL.md").is_file())


# 한 자리의 상태를 판정한다.
def entry_state(entry: Path, skill: Path) -> str:
    target = link_target(entry)
    if target is not None:
        if target == skill.resolve():
            return "연결됨"
        # 저장소를 옮기기 전의 shared/skills/<같은 이름>을 가리키는 링크이다.
        if (
            not target.exists()
            and target.name == skill.name
            and target.parent.name == "skills"
            and target.parent.parent.name == "shared"
        ):
            return f"끊어진 링크 (예전 경로: {target})"
        return f"충돌 (다른 곳을 가리키는 링크: {target})"
    if entry.exists():
        same = "shared와 내용 같음" if entry.is_dir() and same_tree(entry, skill) else "shared와 내용 다름"
        return f"중복 (실제 폴더, {same})"
    return "없음"


# symlink를 먼저 시도하고, Windows에서 권한이 없으면 junction을 만든다.
def make_link(src: Path, dst: Path) -> str:
    try:
        dst.symlink_to(src, target_is_directory=True)
        return "symlink"
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi

        _winapi.CreateJunction(str(src), str(dst))
        return "junction"


# 링크 자체만 지운다.
# 링크가 가리키던 대상에는 손대지 않는다.
def remove_link(path: Path) -> None:
    if sys.platform == "win32":
        os.rmdir(path)
    else:
        os.unlink(path)


# shared/skills를 가리키지만 원본이 없어진 링크를 찾는다.
def stale_links(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    result = []
    for entry in folder.iterdir():
        target = link_target(entry)
        if target is not None and target.parent == SOURCE and not target.exists():
            result.append(entry)
    return result


# skill마다 연결 상태, 중복, Hermes 설정을 출력한다.
# 파일을 바꾸지 않는다.
# 모두 연결됨이면 0, 아니면 1을 반환한다.
def check() -> int:
    skills = read_skills()
    counts: dict[str, int] = {}

    def count(state: str) -> None:
        counts[state] = counts.get(state, 0) + 1

    for label, folder, tools in LINK_DIRS:
        print(f"[{label}] {folder}  ({tools})")
        if not folder.parent.is_dir():
            print("  미설치")
            continue
        for skill in skills:
            state = entry_state(folder / skill.name, skill)
            count("끊어진 링크" if state.startswith("끊어진 링크") else state.split(" ")[0])
            print(f"  {skill.name:<20} {state}")
        for entry in stale_links(folder):
            count("끊어진 링크")
            print(f"  {entry.name:<20} 끊어진 링크 (원본 없음)")

    for label, folder in DUPLICATE_DIRS:
        found = [s for s in skills if (folder / s.name).exists() or is_link(folder / s.name)]
        if not found:
            continue
        print(f"[{label}] {folder}")
        for skill in found:
            count("중복")
            print(f"  {skill.name:<20} {entry_state(folder / skill.name, skill)}")

    print(f"[Hermes] {HERMES_CONFIG}")
    if not HERMES_CONFIG.parent.is_dir():
        print("  미설치")
    else:
        text = HERMES_CONFIG.read_text(encoding="utf-8") if HERMES_CONFIG.is_file() else ""
        if "external_dirs" in text and ".agents/skills" in text:
            print("  external_dirs에 ~/.agents/skills 있음")
        else:
            count("Hermes 설정 없음")
            print("  external_dirs에 ~/.agents/skills 없음. config.yaml에 아래 내용을 추가한다.")
            print("    " + HERMES_LINE.replace("\n", "\n    "))

    print()
    for state, n in counts.items():
        print(f"{state}: {n}건")
    return 0 if set(counts) <= {"연결됨"} else 1


# 빈 자리에 링크를 만들고 원본이 없어진 링크를 정리한다.
# 중복·충돌 항목은 그대로 두고 충돌로 출력한다.
# 충돌이 없으면 0, 하나라도 있으면 1을 반환한다.
def link() -> int:
    skills = read_skills()
    conflicts = 0

    for label, folder, _ in LINK_DIRS:
        print(f"[{label}] {folder}")
        folder.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            dst = folder / skill.name
            state = entry_state(dst, skill)
            if state == "없음":
                kind = make_link(skill, dst)
                print(f"  {skill.name:<20} 생성 ({kind})")
            elif state == "연결됨":
                print(f"  {skill.name:<20} 유지")
            elif state.startswith("끊어진 링크"):
                remove_link(dst)
                kind = make_link(skill, dst)
                print(f"  {skill.name:<20} 재연결 ({kind})")
            else:
                conflicts += 1
                print(f"  {skill.name:<20} {state}. 그대로 둠")
        for entry in stale_links(folder):
            remove_link(entry)
            print(f"  {entry.name:<20} 정리 (원본 없는 링크 삭제)")

    print(f"\n충돌 {conflicts}건. 충돌 항목은 직접 확인 후 정리한다." if conflicts else "\n완료")
    return 1 if conflicts else 0


# 명령줄 인자로 check나 link를 실행한다.
# 인자가 잘못되면 사용법을 출력하고 2를 반환한다.
def main() -> int:
    commands = {"check": check, "link": link}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print("사용법: python tools/skills.py check|link", file=sys.stderr)
        return 2
    return commands[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
