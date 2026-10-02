#!/usr/bin/env python3
"""지침 문서의 끊어진 경로·절 참조와 금지 패턴을 검사한다.

사용법: 저장소 루트나 다른 위치에서 실행한다.
    python tools/check-doc-rule.py

검사1: 백틱 안의 저장소 경로가 있는지 확인한다.
       `<...>` 자리표시자가 있는 경로는 건너뛴다.
검사2: "`<제목>` 절" 참조가 대상 파일의 제목과 일치하는지 확인한다.
       대상 파일은 같은 줄 앞쪽에 적힌 파일이다.
       적힌 파일이 없으면 현재 파일, SECTION_EXTRA_FILES, CORE_FILES, SCHEMA_PATTERN 파일에서 찾는다.
       제목은 코드 블록 밖에서 읽는다.
       SCHEMA_PATTERN 파일은 예시 코드 블록이 절 이름을 정의하므로 코드 블록 안에서도 읽는다.
검사3: discord/prompts 파일에서 ASCII 단어 경계의 Rule ID 패턴 [AHT]\\d{3}을 찾는다.
검사4: 부정형 표현(않는다|하지 마|금지)을 찾는다.
검사5: 첫 구간이 DIRECT_PATH_ROOTS에 속한 백틱 경로를 찾는다.
       공백으로 나눈 토큰마다 검사하므로 명령 안의 경로도 포함한다.
       PATH_LIST_FILE의 PATH_LIST_SECTION 안에서만 허용한다.
       SKILL.md에서는 첫 구간이 해당 Skill의 폴더이면 허용한다.

검사 대상 파일은 TARGET_PATTERNS로 찾는다.
결과는 파일별로 출력한다.
위반은 `파일:행` 형식으로 출력한다.
일치하는 파일이 없는 패턴은 `없음:`으로 출력한다.
위반이나 없는 대상 파일이 하나라도 있으면 종료 코드 1을 반환한다.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# 검사 대상 파일의 저장소 기준 glob 패턴.
TARGET_PATTERNS = [
    "AGENTS.md",
    "AGENTS.principle.md",
    "AGENTS.project.md",
    ".claude/agents/*/AGENTS.md",
    "discord/prompts/*.md",
    "log/schema/*.md",
    "shared/skills/*/SKILL.md",
]

# 검사5: 경로 목록 절에서만 적을 수 있는 경로의 첫 구간.
DIRECT_PATH_ROOTS = {"log", ".claude", "shared", "hooks", "tools", "discord", ".codex"}
PATH_LIST_FILE = "AGENTS.project.md"
PATH_LIST_SECTION = "경로 목록"

# 절 참조에 파일이 없을 때 현재 파일 다음으로 찾는 Core 파일.
CORE_FILES = ["AGENTS.md", "AGENTS.principle.md", "AGENTS.project.md"]
# 런타임에 다른 파일의 절을 합쳐 쓰는 파일과 그 절을 찾을 추가 파일.
# CHAT.md는 RUNTIME.md의 `Response control` 절을 붙여 프롬프트를 만든다.
SECTION_EXTRA_FILES = {"discord/prompts/CHAT.md": ["discord/prompts/RUNTIME.md"]}
# 절 참조에 파일이 없을 때 현재 파일과 CORE_FILES 다음으로 찾는 양식 파일의 glob 패턴.
SCHEMA_PATTERN = "log/schema/*.md"

RULE_ID_SCOPE = "discord/prompts/"
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

INLINE_CODE = re.compile(r"`([^`\n]+)`")
# "·"나 ","로 이은 하나 이상의 백틱 제목과 그 뒤의 "절".
SECTION_REF = re.compile(r"`[^`\n]+`(?:\s*[·,]\s*`[^`\n]+`)*\s*절")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
PATH_CHARS = re.compile(r"^[\w.\-/*?{},~]+$")
FILE_EXT = re.compile(r"\.([A-Za-z][A-Za-z0-9]{0,4})$")
# 저장소 파일로 보는 확장자.
# `node.js`, `www.example.com` 같은 토큰은 제외된다.
REPO_EXTS = {
    "md", "py", "toml", "txt", "json", "jsonl", "yaml", "yml", "ps1", "sh",
    "csv", "html", "css", "png", "jpg", "jpeg", "gif", "svg", "zip",
}
# :3, :3-5, :3,5, :3-5,9 같은 행 번호 접미사.
LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")
# 한국어 조사가 붙은 경우(A060를, H001은)도 찾도록 ASCII 단어 경계를 쓴다.
RULE_ID = re.compile(r"(?<![A-Za-z0-9_])[AHT]\d{3}(?![A-Za-z0-9_])")
NEGATIVE = re.compile(r"않는다|하지 마|금지")

KIND_PATH = "검사1 경로 없음"
KIND_SECTION = "검사2 절 제목 없음"
KIND_RULE_ID = "검사3 Rule ID"
KIND_NEGATIVE = "검사4 부정형"
KIND_DIRECT = "검사5 경로 직접 기재"
KINDS = (KIND_PATH, KIND_SECTION, KIND_RULE_ID, KIND_NEGATIVE, KIND_DIRECT)


# SKIP_DIRS를 뺀 저장소의 파일·폴더 이름을 소문자로 모은다.
def build_name_index() -> set[str]:
    names: set[str] = set()
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        names.add(path.name.lower())
    return names


# 중괄호 선택지(`{a,b}`)를 모든 조합의 패턴으로 펼친다.
def expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    results: list[str] = []
    for option in match.group(1).split(","):
        results.extend(expand_braces(head + option + tail))
    return results


# 구간에 비어 있지 않은 이름과 REPO_EXTS 확장자가 있는지 확인한다.
def has_repo_ext(segment: str) -> bool:
    match = FILE_EXT.search(segment)
    return bool(match) and match.start() > 0 and match.group(1).lower() in REPO_EXTS


# 정규화한 경로 후보를 반환한다.
# 토큰이 경로가 아니면 None이다.
# 슬래시 없는 이름은 저장소 파일 확장자가 있어야 한다(`AGENTS.md`).
# 슬래시 경로는 끝 슬래시, 저장소 파일 확장자, 저장소에 있는 첫 구간(`archive/raw`) 중 하나가 있어야 한다.
def as_repo_path(token: str, names: set[str]) -> str | None:
    token = LINE_SUFFIX.sub("", token.strip())
    if not token or "<" in token or ">" in token or "$" in token:
        return None
    if "://" in token or not PATH_CHARS.match(token):
        return None
    if "/" not in token:
        return token if has_repo_ext(token) else None
    if not re.search(r"[A-Za-z]", token):
        return None
    first = token.split("/", 1)[0]
    last = token.rstrip("/").rsplit("/", 1)[-1]
    if (
        token.endswith("/")
        or any(has_repo_ext(option) for option in expand_braces(last))
        or first in (".", "..")
        or first.lower() in names
    ):
        return token
    return None


# 토큰이 DIRECT_PATH_ROOTS 아래 경로이면 첫 구간을 반환한다.
# 자리표시자 경로(`log/state/<작업-id>.md`)도 포함한다.
def direct_path_root(token: str) -> str | None:
    token = LINE_SUFFIX.sub("", token.strip()).replace("\\", "/")
    while token.startswith("./"):
        token = token[2:]
    if "/" not in token or "://" in token:
        return None
    first = token.split("/", 1)[0]
    return first if first in DIRECT_PATH_ROOTS else None


# 패턴 하나가 저장소 루트나 문서 폴더 기준으로 있는지 확인한다.
def single_path_exists(pattern: str, base_dir: Path, names: set[str]) -> bool:
    pattern = pattern.rstrip("/") or pattern
    is_glob = any(c in pattern for c in "*?")
    if "/" not in pattern and not is_glob:
        # 슬래시 없는 파일 이름은 문서 옆이나 저장소 전체에서 찾는다.
        return (base_dir / pattern).exists() or pattern.lower() in names
    for base in (ROOT, base_dir):
        if is_glob and any(base.glob(pattern)):
            return True
        if not is_glob and (base / pattern).exists():
            return True
    return False


# 경로 후보가 있는지 확인한다.
# 중괄호 선택지는 모두 있어야 하고 glob은 하나 이상 일치해야 한다.
def path_exists(candidate: str, base_dir: Path, names: set[str]) -> bool:
    return all(
        single_path_exists(pattern, base_dir, names)
        for pattern in expand_braces(candidate)
    )


# 저장소 루트나 문서 폴더 기준으로 파일을 찾는다.
# 파일이 없으면 None이다.
def resolve_file(candidate: str, base_dir: Path) -> Path | None:
    for base in (ROOT, base_dir):
        path = base / candidate
        if path.is_file():
            return path
    return None


# 코드 블록 밖의 제목을 읽어 캐시에 두고 반환한다.
# 양식 파일(SCHEMA_PATTERN)은 코드 블록 안의 제목도 읽는다.
def read_headings(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        headings: set[str] = set()
        schema_files = {p.resolve() for p in ROOT.glob(SCHEMA_PATTERN)}
        read_in_fence = path.resolve() in schema_files
        in_fence = False
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            match = None if in_fence and not read_in_fence else HEADING.match(line)
            if match:
                title = match.group(2).strip()
                headings.add(title)
                headings.add(title.replace("`", ""))
        cache[path] = headings
    return cache[path]


# 절 제목을 찾을 파일 목록을 반환한다.
# 같은 줄에서 참조 앞의 가장 가까운 백틱 .md 경로를 우선한다.
# 그런 경로가 없으면 현재 파일, CORE_FILES, 양식 파일을 차례로 찾는다.
# 빈 목록은 적힌 파일을 찾을 수 없다는 뜻이다(자리표시자나 없는 파일).
def section_targets(
    line: str, ref_start: int, current: Path, names: set[str]
) -> list[Path]:
    target_token = None
    for match in INLINE_CODE.finditer(line[:ref_start]):
        token = LINE_SUFFIX.sub("", match.group(1).strip())
        if token.endswith(".md"):
            target_token = token
    if target_token is None:
        core = [ROOT / rel for rel in CORE_FILES if (ROOT / rel).is_file()]
        schema = sorted(p for p in ROOT.glob(SCHEMA_PATTERN) if p.is_file())
        rel = current.relative_to(ROOT).as_posix()
        extra = [ROOT / e for e in SECTION_EXTRA_FILES.get(rel, []) if (ROOT / e).is_file()]
        return [current] + [path for path in extra + core + schema if path != current]
    candidate = as_repo_path(target_token, names)
    resolved = resolve_file(candidate, current.parent) if candidate else None
    return [resolved] if resolved else []


# 파일 하나를 검사해 위반 목록을 반환한다.
def check_file(
    rel: str,
    names: set[str],
    heading_cache: dict[Path, set[str]],
) -> list[tuple[str, int, str, str]]:
    path = ROOT / rel
    violations: list[tuple[str, int, str, str]] = []
    in_fence = False
    check_rule_id = rel.startswith(RULE_ID_SCOPE)
    is_path_list_file = rel == PATH_LIST_FILE
    is_skill = path.name == "SKILL.md"
    # 열려 있는 경로 목록 제목의 수준.
    # 절 밖이면 None이다.
    path_list_level: int | None = None

    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            heading = HEADING.match(line) if is_path_list_file else None
            if heading:
                level = len(heading.group(1))
                if heading.group(2).strip() == PATH_LIST_SECTION:
                    path_list_level = level
                elif path_list_level is not None and level <= path_list_level:
                    path_list_level = None

            for match in INLINE_CODE.finditer(line):
                candidate = as_repo_path(match.group(1), names)
                if candidate and not path_exists(candidate, path.parent, names):
                    violations.append((rel, lineno, KIND_PATH, match.group(1)))

                # `python tools/skills.py link` 같은 명령은 어느 토큰에든 경로가 있을 수 있다.
                for token in match.group(1).split():
                    root = direct_path_root(token)
                    if (
                        root
                        and path_list_level is None
                        and not (is_skill and (path.parent / root).is_dir())
                    ):
                        violations.append((rel, lineno, KIND_DIRECT, token))

            for match in SECTION_REF.finditer(line):
                targets = section_targets(line, match.start(), path, names)
                if not targets:
                    continue
                for title in INLINE_CODE.findall(match.group(0)):
                    title = title.strip()
                    if any(title in read_headings(t, heading_cache) for t in targets):
                        continue
                    shown = ", ".join(t.relative_to(ROOT).as_posix() for t in targets)
                    violations.append((rel, lineno, KIND_SECTION, f"{title} -> {shown}"))

        if check_rule_id:
            for match in RULE_ID.finditer(line):
                violations.append((rel, lineno, KIND_RULE_ID, match.group(0)))

        for match in NEGATIVE.finditer(line):
            violations.append((rel, lineno, KIND_NEGATIVE, match.group(0)))

    return violations


# (검사 대상 파일, 일치하는 파일이 없는 패턴)을 반환한다.
# 파일은 패턴 순서를 유지한다.
def find_targets() -> tuple[list[str], list[str]]:
    targets: list[str] = []
    missing: list[str] = []
    for pattern in TARGET_PATTERNS:
        found = sorted(
            p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file()
        )
        if not found:
            missing.append(pattern)
        targets.extend(rel for rel in found if rel not in targets)
    return targets, missing


# 모든 대상 파일을 검사하고 파일별 결과와 합계를 출력한다.
def main() -> int:
    names = build_name_index()
    heading_cache: dict[Path, set[str]] = {}
    violations: list[tuple[str, int, str, str]] = []
    targets, missing = find_targets()

    for rel in targets:
        file_violations = check_file(rel, names, heading_cache)
        violations.extend(file_violations)
        print(f"== {rel}: 위반 {len(file_violations)}")
        for _, lineno, kind, detail in file_violations:
            print(f"{rel}:{lineno}: [{kind}] {detail}")

    print()
    for pattern in missing:
        print(f"없음: {pattern}")
    counts = Counter(kind for _, _, kind, _ in violations)
    for kind in KINDS:
        print(f"{kind}: {counts.get(kind, 0)}")
    print(f"대상 파일 없음: {len(missing)}")
    total = len(violations) + len(missing)
    print(f"검사 파일: {len(targets)}, 위반 합계: {total}")

    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
