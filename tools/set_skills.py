#!/usr/bin/env python3
"""shared/skills의 skill을 사용자 전역 skill 폴더에 연결하고 연결 상태를 확인한다.

check: 연결 상태, 중복, Hermes 설정을 출력한다. 파일을 바꾸지 않는다.
link:  빈 자리에 링크를 만들고, 원본이 없어진 shared 링크를 지운다.
       실제 폴더와 다른 곳을 가리키는 링크는 건드리지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

# 같은 이름 폴더의 모듈을 불러온다.
sys.path.insert(0, str(Path(__file__).resolve().parent / "set_skills"))

from check import check
from link import link


# 명령줄 인자로 check나 link를 실행한다.
# 인자가 잘못되면 사용법을 출력하고 2를 반환한다.
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    commands = {"check": check, "link": link}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print("사용법: python tools/set_skills.py check|link", file=sys.stderr)
        return 2
    return commands[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
