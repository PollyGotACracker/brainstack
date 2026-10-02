# Codex 연결

Codex project custom agents는 `.codex/agents/*.toml`을 사용한다.

## 공식 문서

- [Custom subagents](https://developers.openai.com/codex/subagents)
- [AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Hooks](https://developers.openai.com/codex/hooks)
- [Config reference](https://developers.openai.com/codex/config-reference)

## custom agent 파일

에이전트별로 다음 파일이 있다.

```text
.codex/agents/<name>.toml
```

에이전트 목록은 README.md의 표를 따른다. 에이전트를 추가할 때 같은 이름의 TOML 하나만 추가한다.

에이전트 원문과 인격 원문을 TOML에 복사하지 않는다. hook이 `.claude/agents/<role>/AGENTS.md`와 `SOUL.md`를 시작 context에 넣는다.

쓰기 권한은 각 TOML의 `sandbox_mode` 값을 따른다.
현재 `buddy`, `jelly`, `pepper`는 `workspace-write`를 사용한다.
`rio`, `nico`, `ricky`는 `read-only`를 사용한다.
이는 파일에 선언된 기본값이다.
부모 세션에서 변경한 sandbox·승인 설정 등 실행 중 override는 하위 에이전트에도 적용되므로 실제 권한 모드를 함께 확인한다([공식 문서](https://learn.chatgpt.com/docs/agent-configuration/subagents)).

## 승인과 실행 정책

프로젝트의 `.codex/config.toml`에는 다음 설정이 있다.

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"

[features]
hooks = true
```

`.codex/rules/permissions.rules`는 명령 접두사별 실행 정책을 정의한다.

- `prompt`: `git checkout`, `git switch`, `git restore`, `git stash`, `git tag`, `rm`, `rmdir`이다.
- `forbidden`: `git commit`, `git push`, `git merge`, `git rebase`, `git reset`, `git revert`, `git cherry-pick`, `git clean`이다.

이 규칙은 Claude Code의 명령 승인·금지 항목을 대응시킨 실행 정책이다.
Claude Code의 파일 접근 등 모든 도구 권한을 재현하는 설정은 아니다.

## helper 절대경로 확인

Windows PowerShell:

```sh
Resolve-Path .\hooks\load-agent-context.py
```

macOS/Linux/WSL:

```sh
realpath hooks/load-agent-context.py
```

이 명령은 파일을 수정하지 않고 helper의 실제 절대경로를 출력한다.

## hooks 설정

예시:

```text
.codex/hooks.example.json
```

실제 파일:

```text
.codex/hooks.json
```

없으면 예시를 복사한다. 있으면 덮어쓰지 말고 `hooks.SessionStart`와 `hooks.SubagentStart`를 기존 `hooks` 객체에 병합한다.

그 뒤 `SessionStart`와 `SubagentStart`의 `command`, `commandWindows`에 있는 모든 `<LOAD_AGENT_CONTEXT_SCRIPT_PATH>`를 앞 단계에서 확인한 실제 절대경로로 바꾼다.
Windows에서는 `commandWindows`가 사용하는 `py`, 다른 환경에서는 `command`가 사용하는 `python3`를 실행할 수 있어야 한다.
예시의 `additionalContextLimit: 6000`은 hook의 추가 context에 적용하는 대략적인 토큰 한도이다([공식 문서](https://learn.chatgpt.com/docs/hooks)).

Codex는 변경된 non-managed hook을 실행하기 전에 trust 확인을 요구할 수 있다. `/hooks`에서 내용을 확인하고 신뢰 여부를 직접 결정한다.

## 실행

```sh
codex
```

현재 저장소에서 Codex CLI를 시작한다.

Codex 기본 세션은 custom agent로 시작할 수 없다. 기본 작업은 hook이 주입하는 `buddy` context로 진행하고, 프로젝트 작업은 `rio` agent를 요청한다.

특정 agent를 요청하는 예:

```text
Use the rio agent to run this project task.
Use the nico agent to investigate the best approach for this request.
Use the jelly agent to implement only the approved scope.
Use the ricky agent to review the current implementation.
```

agent thread를 확인하거나 전환할 때는 Codex의 agent UI/명령을 사용한다.

## 프로젝트 폴더 준비

Codex는 디렉터리마다 `AGENTS.override.md`, `AGENTS.md`, 설정한 fallback 파일명 순서로 지침을 찾고, 해당 디렉터리에서 최대 한 파일을 읽는다([공식 문서](https://learn.chatgpt.com/docs/agent-configuration/agents-md)).
이 저장소의 `AGENTS.md`에 있는 `@AGENTS.principle.md`, `@AGENTS.project.md`는 Codex가 자동으로 펼치는 import 구문이 아니다.

현재 hook은 역할별 `AGENTS.md`와 `SOUL.md`를 주입한다.
루트의 공통 Core 문서는 hook 주입 대상에 포함되지 않는다.
세션 시작 후 다음과 같이 공통 지침을 명시적으로 읽도록 요청한다.

```text
AGENTS.principle.md와 AGENTS.project.md를 읽고 현재 작업에 적용해.
```

helper는 hook 입력의 `cwd`부터 상위 디렉터리를 검색한다.
루트 `AGENTS.md`와 `.claude/agents/`가 함께 있는 디렉터리가 필요하다.
별도 저장소에 hook의 절대경로만 지정하면 이 구성 루트를 찾는 조건을 충족하지 않는다.
외부 저장소에서 사용할 때는 에이전트 구성과 공통 지침의 연결을 별도로 준비하고 실제 주입 결과를 확인한다.

## 긴 작업 시작

긴 프로젝트 작업은 준비한 프로젝트 폴더에서 새 세션으로 시작한다.

```sh
codex
```

진행 중인 기본 세션에서 `rio`로 전환하지 않는다. 세션 시작 시 주입된 에이전트 context는 해당 세션에서 제거되지 않는다.
