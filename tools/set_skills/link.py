"""link 명령이다.
빈 자리에 링크를 만들고 원본이 없어진 shared 링크를 지운다.
"""
from __future__ import annotations

from sub_config import LINK_DIRS
from sub_symlink import make_link, remove_link, stale_links
from sub_status import entry_state, read_skills


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
