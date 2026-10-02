# Skill 링크 설정

- 직접 만든 skill의 원본은 `shared/skills/<skill>/SKILL.md`에 둔다.
- 각 도구는 사용자 전역 폴더의 링크로 원본을 읽는다.
- 전역 폴더이므로 어느 프로젝트에서 실행해도 skill이 적용된다.
- 링크가 원본을 가리키므로 `SKILL.md` 내용을 고치면 모든 도구에 바로 반영된다.

## 실행 시점

아래 경우에는 `check`로 상태를 확인하고 `link`를 실행한다.

- 새 PC에서 처음 설정할 때
- `shared/skills/`에 skill을 추가하거나, 삭제하거나, 이름을 바꿨을 때
- 저장소 폴더를 다른 경로로 옮겼을 때

```bash
python tools/skills.py check
python tools/skills.py link
```

## 요구사항

- Python 3.12 이상이 필요하다.

```bash
# bash
python --version || python3 --version
```

- Windows: [Python Install Manager](https://www.python.org/downloads/)
- macOS: [python.org/downloads/macos](https://www.python.org/downloads/macos/)
- Linux: `sudo apt install python3`
- macOS, Linux에서는 명령의 `python`을 `python3`로 바꿔 실행한다.

## 도구별 링크 위치

| 링크 위치                  | 읽는 도구                       |
| -------------------------- | ------------------------------- |
| `~/.claude/skills/<skill>` | Claude Code                     |
| `~/.agents/skills/<skill>` | Codex, Cursor, OpenClaw, Hermes |

- Orca는 skill을 직접 읽지 않는다. Orca에서 실행한 에이전트가 위 경로를 읽는다.

- Hermes는 `~/.agents/skills`를 기본으로 읽지 않는다. `~/.hermes/config.yaml`에 아래 설정을 추가한다.

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
```

## 링크 구조

- 링크는 심볼릭 링크(symlink)다. 원본 폴더를 가리키는 바로가기이며 파일을 복사하지 않는다.
- Windows에서 심볼릭 링크를 만들 권한이 없으면 junction을 만든다.
- junction은 권한 없이 만드는 Windows 전용 폴더 바로가기다.
- 링크를 지워도 원본은 남는다.
- 원본이나 저장소를 옮기면 링크가 끊어진다. `link`를 다시 실행하면 새 경로로 다시 연결한다.

```text
~/.claude/skills/search  ──링크──▶  <저장소>/shared/skills/search/
~/.agents/skills/search  ──링크──▶  <저장소>/shared/skills/search/
```

## 상태 확인

`shared/skills/`의 skill마다 연결 상태를 출력한다. 파일을 바꾸지 않는다.

```bash
python tools/skills.py check
```

- `~/.claude/skills`, `~/.agents/skills`에서 skill마다 아래 상태 중 하나를 출력한다.
  - `연결됨`: 원본을 가리키는 링크가 있다.
  - `없음`: 링크가 없다. `link`로 만든다.
  - `중복`: 같은 이름의 실제 폴더가 있다. 원본과 내용이 같은지 다른지 함께 표시한다.
  - `충돌`: 같은 이름의 링크가 다른 곳을 가리킨다.
  - `끊어진 링크`: 원본이 없어졌거나, 저장소를 옮겨서 예전 경로를 가리킨다. `link`로 정리한다.
- `~/.codex/skills`, `~/.cursor/skills`에 같은 이름의 skill이 있으면 `중복`으로 출력한다.
  - 같은 skill이 여러 경로에 있으면 도구가 여러 번 읽는다.
- Hermes는 설치되어 있으면 `external_dirs`에 `~/.agents/skills`가 있는지 확인한다.
  - 없으면 추가할 설정을 출력한다.
- 설치되지 않은 도구의 폴더는 `미설치`로 출력한다.
- 마지막에 상태별 건수를 출력한다.
- 모두 `연결됨`이면 종료 코드 0, 아니면 1을 반환한다.

## 링크 생성

빈 자리에 링크를 만들고 원본이 없어진 링크를 정리한다.

```bash
python tools/skills.py link
```

- `~/.claude/skills`, `~/.agents/skills`가 없으면 먼저 만든다.
- skill마다 링크 위치의 상태에 따라 아래처럼 처리한다.
  - `없음`: 링크를 만든다. symlink를 먼저 시도하고, Windows에서 권한이 없으면 junction을 만든다.
  - `연결됨`: 그대로 둔다.
  - `중복`, `충돌`: 그대로 두고 충돌로 출력한다. 기존 항목을 직접 정리한 뒤 다시 실행한다.
  - `끊어진 링크`: 원본이 없어졌으면 링크만 지우고, 저장소를 옮겼으면 새 경로로 다시 연결한다.
- 파일 복사, 덮어쓰기, 실제 폴더 삭제는 하지 않는다.
- Hermes 설정 파일은 수정하지 않는다.
- 여러 번 실행해도 실행 결과는 동일하다.
- 충돌이 없으면 종료 코드 0, 하나라도 있으면 1을 반환한다.

## 외부 skill 패키지

- 외부에서 설치하는 skill은 `shared/skills/`에 넣지 않는다.
- 설치 도구가 관리하는 위치에 설치한 뒤 `check`로 같은 이름의 skill이 겹치는지 확인한다.
