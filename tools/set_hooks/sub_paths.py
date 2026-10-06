"""저장소·전역 파일·설치 기록 경로이다.

ROOT는 이 저장소 폴더 최상위 경로이다.
HOME은 실행 환경의 사용자 폴더이다.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "AGENTS.md"
HOME = Path.home()

CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CLAUDE_MD = HOME / ".claude" / "CLAUDE.md"
CODEX_HOOKS = HOME / ".codex" / "hooks.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
CODEX_RULES = HOME / ".codex" / "rules" / "default.rules"
CODEX_AGENTS = HOME / ".codex" / "AGENTS.md"
CODEX_OVERRIDE = HOME / ".codex" / "AGENTS.override.md"
BASHRC = HOME / ".bashrc"

RECORD_DIR = HOME / ".brainstack"
RECORD = RECORD_DIR / "install-record.json"
