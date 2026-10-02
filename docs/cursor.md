# Cursor 연결

Cursor는 project subagent 위치로 `.claude/agents/`를 Claude compatibility 경로로 지원한다.

## 공식 문서

- [Custom subagents](https://cursor.com/docs/subagents)

## 프로젝트 열기

이 구성이 들어 있는 저장소를 Cursor에서 연다. 별도 `.cursor/agents/` 복사본을 만들지 않는다.

## 직접 호출

Cursor Agent에서 `/`를 입력하고 README.md 표의 이름을 확인한다.

```text
/<name>
```

예:

```text
/nico 이 기능의 최선의 방법을 조사해.
/jelly 승인된 범위만 구현해.
/ricky 현재 변경을 검수해.
```

Cursor 공식 문서의 custom subagent explicit invocation은 `/name` 형식이다.

읽기 전용 여부는 각 에이전트의 `.claude/agents/<role>/AGENTS.md` frontmatter에 있는 `readonly` 값을 따른다.
`readonly`는 Cursor 공식 문서에 정의된 custom subagent 설정이다.

원본의 `tools`는 Claude Code 호환 정의에 포함된 도구 목록이다.
Cursor에서 이 필드가 도구 제한으로 강제되는지는 이 저장소에서 검증하지 않았다.
Claude Code의 `settings.json`과 hooks가 Cursor에 자동으로 적용되는 것으로 가정하지 않는다.
실제 세션에서 역할 지침과 persona 로딩, 읽기 전용 제한, 필요한 공통 Core 지침을 확인한다.
