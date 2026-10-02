# OpenClaw 연결

OpenClaw에서는 사용자-facing agent id를 README.md 표의 이름으로 사용하고, 각 agent의 workspace는 해당 에이전트의 원본 디렉터리를 가리킨다.

## 공식 문서

- [Per-agent entries](https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent)
- [Workspace / cwd](https://docs.openclaw.ai/gateway/config-agents/workspace-and-bootstrap)
- [Multi-agent](https://docs.openclaw.ai/concepts/multi-agent)

## 설정 파일

수정할 파일:

```text
~/.openclaw/openclaw.json
```

`OPENCLAW_CONFIG_PATH`를 사용 중이면 그 파일을 수정한다.

## agent 등록

`<AGENT_BUNDLE_ROOT>`는 이 구성의 `AGENTS.md`가 있는 절대경로, `<TARGET_REPO>`는 실제 작업 저장소 절대경로다.

```json5
{
  agents: {
    entries: {
      buddy: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/assistant",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
      rio: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/director",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
      nico: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/planner",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
      jelly: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/worker",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
      ricky: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/reviewer",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
      pepper: {
        workspace: "<AGENT_BUNDLE_ROOT>/.claude/agents/documenter",
        cwd: "<TARGET_REPO>",
        sandbox: { mode: "off" },
      },
    },
  },
}
```

OpenClaw 공식 문서상 `workspace`와 실제 coding `cwd`를 분리할 수 있으며, 서로 다른 경로를 쓸 때는 unsandboxed run이 필요하다.

위 예시는 agent 등록, workspace, 작업 위치와 sandbox 모드를 지정한다.
역할별 tool allow/deny 설정은 포함하지 않는다.
원본 `AGENTS.md` frontmatter의 `tools`와 `readonly`만으로 OpenClaw의 실행 권한이 제한되는 것으로 가정하지 않는다.
실제 운영 전에는 [OpenClaw의 에이전트별 도구 설정](https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent)으로 역할별 허용·금지 범위를 구성하고 동작을 확인한다.

각 workspace의 `AGENTS.md`는 역할 지침이다.
이 예시에는 구성 루트의 `AGENTS.principle.md`와 `AGENTS.project.md`를 자동으로 연결하는 설정이 없다.
공통 Core는 접근 가능한 실제 경로를 지정해 읽도록 요청하고, 세션에 적용되었는지 확인한다.

## 재시작과 확인

```sh
openclaw gateway restart
```

변경한 Gateway 설정을 다시 읽는다.

```sh
openclaw agents list --bindings
```

등록된 agent와 binding을 확인한다.
