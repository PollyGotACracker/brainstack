#!/usr/bin/env python3
"""brainstack 전역 설정을 사용자 전역 파일에 병합하고 반영 상태를 확인한다.

설정 원본은 tools/hooks/sub_settings.py이다.
원본의 <BRAINSTACK> 자리표시는 이 저장소의 실제 경로로 바꾼다.

install:           settings 원본을 전역 파일에 반영하고 설치 기록을 남긴다.
                   기존 설치도 settings 변경을 모든 관리 항목에 재반영한다.
                   변경 전 파일은 설치 기록 폴더에 백업하고, 실패하면 전체 원복한다.
install --dry-run: 전역 파일에 추가·교체·삭제할 내용만 출력한다. 파일을 바꾸지 않는다.
check:             전역 파일의 항목별 반영 여부를 출력한다. 파일을 바꾸지 않는다.
uninstall:         설치 기록에 있는 항목만 제거한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

# 같은 이름 폴더의 모듈을 불러온다.
sys.path.insert(0, str(Path(__file__).resolve().parent / "set_hooks"))

from check import check
from install import install, uninstall


# 명령줄 인자로 install, check, uninstall을 실행한다.
# 인자가 잘못되면 사용법을 출력하고 2를 반환한다.
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["install"]:
        return install(dry_run=False)
    if args == ["install", "--dry-run"]:
        return install(dry_run=True)
    if args == ["check"]:
        return check()
    if args == ["uninstall"]:
        return uninstall()
    print("사용법: python tools/set_hooks.py install [--dry-run]|check|uninstall", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
