# Claude Code 연결

Claude Code는 `.claude/agents/`를 재귀적으로 읽고 YAML frontmatter의 `name`으로 subagent를 식별한다.

## 공식 문서

- [Custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Settings](https://code.claude.com/docs/en/settings)
- [Permissions](https://code.claude.com/docs/en/permissions)
- [Status line](https://code.claude.com/docs/en/statusline)

## `CLAUDE.md` 연결

수정할 파일:

```text
<TARGET_REPO>/CLAUDE.md
```

없으면 만들고, 있으면 기존 내용을 지우지 말고 다음 한 줄을 추가한다.

```md
@AGENTS.md
```

이 줄은 공통 규칙 `AGENTS.md`를 Claude Code context에 넣는다.

## helper 절대경로 확인

확인할 파일:

```text
hooks/load-agent-context.py
hooks/statusline.py
```

Windows PowerShell:

```powershell
Resolve-Path .\hooks\load-agent-context.py
Resolve-Path .\hooks\statusline.py
```

두 명령은 파일을 수정하지 않고 실제 절대경로를 출력한다.

macOS/Linux/WSL:

```sh
realpath hooks/load-agent-context.py
realpath hooks/statusline.py
```

이 명령도 실제 절대경로만 출력한다.

## 설정 병합

예시 파일:

```text
.claude/settings.example.json
```

Claude Code가 실제 읽는 파일:

```text
.claude/settings.json
```

선택 사항: 프로젝트 밖의 문서 경로를 쓸 때만 `permissions.additionalDirectories` 키를 추가한다.
값에는 해당 문서 루트의 절대경로를 넣는다.
예시 파일에는 이 키가 없다.

바꿀 값:

| 파일                    | 키                                        | 넣을 값                                     |
| ----------------------- | ----------------------------------------- | ------------------------------------------- |
| `.claude/settings.json` | `hooks.SessionStart[*].hooks[*].command`  | `hooks/load-agent-context.py` 실제 절대경로 |
| `.claude/settings.json` | `hooks.SubagentStart[*].hooks[*].command` | 같은 실제 절대경로                          |
| `.claude/settings.json` | `statusLine.command`                      | `hooks/statusline.py` 실제 절대경로         |

예시의 기본 main agent 값:

```json
"agent": "buddy"
```

기본 폴더 세션은 `buddy`로 시작한다.
프로젝트 폴더에서는 `프로젝트 폴더 준비` 절에 따라 `rio`로 시작한다.

에이전트 목록은 README.md의 표를 따른다.
에이전트를 추가해도 이 설정은 바꾸지 않는다.

### subagent 중첩 호출 차단

subagent가 다시 subagent를 호출하지 못하게 막는 설정이다.
기본값에서는 메인 아래 3단계까지 중첩 호출된다(v2.1.219 이상).
값을 `1`로 두면 메인만 subagent를 호출한다.

`.claude/settings.json`의 최상위 `env`에 다음 키를 넣는다.
`env`가 이미 있으면 기존 키를 유지하고 이 키만 추가한다.

```json
"env": {
  "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"
}
```

- 적용 최소 버전: Claude Code v2.1.217
- 버전 확인: `claude --version`
- 공식 문서: https://code.claude.com/docs/en/sub-agents

### subagent 호출 승인

subagent 호출 전에 사용자 승인을 요청하는 설정이다.
`Agent` 도구 호출마다 PreToolUse 훅이 `ask`를 반환한다.

`.claude/settings.json`의 `hooks`에 예시의 `PreToolUse`를 넣는다.
`hooks`가 이미 있으면 기존 이벤트를 유지하고 이 키만 추가한다.
이 항목에는 바꿀 자리표시가 없다.

- [공식 문서](https://code.claude.com/docs/en/hooks)

## Claude Code 실행

현재 작업 저장소에서:

```sh
claude
```

이 명령은 해당 저장소에서 Claude Code 대화형 세션을 시작한다.

하단 status line에:

```text
Agent: buddy
```

가 보이면 기본 에이전트가 연결된 것이다.

### 하위 폴더 실행

settings.json 설정이 전역이 아닐 때 사용한다.
아래 방법은 설정 파일을 선택하는 방법이다.
실행 위치에 필요한 에이전트 구성 조건은 `프로젝트 폴더 준비` 절을 따른다.

#### `.bashrc` 생성

추천 방법이다.

```bash
claude --settings "/c/Users/<사용자명>/<커스텀경로>/.claude/settings.json"
```

- 커스텀 커맨드를 통해 Claude Code에서 제공하는 위 옵션을 실행할 수 있도록 한다.
- 생성할 .bashrc 파일은 사용자 홈 경로에 두는 전역 셸 설정 파일이다.

```bash
# C:\Users\<사용자명>\.bashrc
# agent 커맨드로 실행
agent() {
  claude --settings "/c/Users/<사용자명>/<커스텀경로>/.claude/settings.json" "$@"
}
```

#### 전역 심볼릭 링크

- 이 방식은 결국 권한을 전역으로 적용하게 됨에 유의한다.
- settings.json을 전역 심볼릭 링크로 연결하여 설정이 적용한다.
- 실행 전 반드시 사용자 홈 경로 .claude 폴더에 동일 파일이 있는지 확인한다.

```sh
# powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude"; New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\settings.json" -Target "C:\Users\<사용자명>\<커스텀경로>\.claude\settings.json"
```

```sh
# bash
mkdir -p "$HOME/.claude" &&
ln -s "$HOME/<커스텀경로>/.claude/settings.json" \
  "$HOME/.claude/settings.json"
```

## 에이전트 직접 호출

```text
@agent-nico 이 요구사항의 최선의 방법을 조사해.
@agent-jelly 승인된 범위만 구현해.
@agent-ricky 현재 구현을 검수해.
@agent-pepper 공용 상태 문서를 갱신해.
```

Claude Code 공식 문서상 local subagent는 `@agent-<name>`으로 직접 입력할 수 있다. `@` typeahead에서 `nico (agent)` 같은 항목을 선택해도 된다.

세션 전체를 특정 에이전트로 시작할 때만:

```sh
claude --agent jelly
```

이 명령은 한 번 `jelly`를 호출하는 것이 아니라 메인 세션 전체를 `jelly` 에이전트로 시작한다.

`--agent`는 세션 시작 시점에만 적용된다. 진행 중인 세션의 메인 에이전트는 바꿀 수 없다.

프로젝트 폴더의 `.claude/settings.json`은 사용자 폴더 설정보다 우선 적용된다([참고](https://code.claude.com/docs/en/settings)).

## 프로젝트 폴더 준비

현재 helper는 실행 위치부터 상위 디렉터리를 검색해 루트 `AGENTS.md`와 `.claude/agents/`가 함께 있는 구성 루트를 찾는다.
이 저장소나 그 하위 폴더에서 실행하면 현재 배치를 사용할 수 있다.
별도 작업 저장소에서는 해당 조건을 충족하는 구성과 `AGENTS.md`가 참조하는 공통 지침 파일을 준비해야 한다.
`--settings`로 외부 설정 파일의 절대경로를 지정하는 것만으로는 helper의 구성 루트나 custom agent 파일이 연결되지 않는다.

프로젝트 작업은 준비한 프로젝트 폴더에서 다음 명령으로 새 세션을 시작한다.

```sh
claude --agent rio
```

프로젝트의 `.claude/settings.json`에서 기본 main agent를 `"agent": "rio"`로 설정한 경우에는 `claude`로 시작한다.
예시 파일의 기본값은 `buddy`이므로 프로젝트용 설정을 준비하지 않은 상태에서 `claude`만 실행하면 `rio` 세션이 되지 않는다.
`CLAUDE.md`의 공통 지침 import와 역할·persona 주입을 실제 세션에서 확인한다.

## 긴 작업 시작

긴 프로젝트 작업은 준비한 프로젝트 폴더에서 새 세션으로 시작한다.

```sh
claude --agent rio
```

진행 중인 기본 세션에서 `rio`로 전환하지 않는다. 세션 시작 시 주입된 에이전트 컨텍스트는 해당 세션에서 제거되지 않는다.
