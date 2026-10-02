# BRAINSTACK

에이전트 기반 개발 환경과 관련된 지식 및 운영 자산을 관리하는 저장소이다.

- 에이전트 팀의 규칙 및 페르소나 파일
- Discord 봇 설정 및 스크립트 파일
- Obsidian 기반 지식 저장소
- 도구별 에이전트 설정 및 스킬 연동 문서
- 공용 스킬 파일

## 폴더 구조

```text
./
├── .claude/                       # Claude Code 설정
│   ├── agents/<role>/
│   │   ├── AGENTS.md              # 에이전트별 지침
│   │   └── SOUL.md                # 에이전트별 성향
│   ├── assets/                    # 에이전트 캐릭터 이미지 등 에셋
│   └── settings.example.json      # settings.json 예시
├── .codex/                        # Codex 설정
│   ├── agents/<name>.toml         # 에이전트별 설정
│   ├── config.toml                # 승인 및 hooks 활성화 설정
│   ├── rules/permissions.rules    # 명령별 실행 정책
│   └── hooks.example.json         # hooks.json 예시
├── .github/                       # Github 저장소 설정 및 workflow
├── archive/                       # Obsidian 기반 지식 저장소
│   ├── <folders>                  # 하위 폴더. archive/README.md 참고
│   ├── AGENTS.md                  # 지식 저장소 작업 지침 문서
│   ├── CLAUDE.md                  # archive/AGENTS.md를 불러오는 문서
│   └── README.md                  # 지식 저장소 구조 문서
├── discord/                       # Discord 봇
│   ├── bot/                       # 봇 스크립트
│   ├── prompts/                   # 봇 스크립트에 주입되는 프롬프트
│   ├── tests/                     # 봇 스크립트 테스트
│   └── config.example.json        # config.json 예시
├── docs/                          # 환경별 연결 문서
├── hooks/                         # 하네스가 실행하는 스크립트
├── log/                           # 작업 로그
│   ├── schema/                    # 작업 로그 작성 규칙
│   ├── state/                     # 작업 경과 로그
│   └── incident/                  # 작업 중 문제사항 로그
├── shared/
│   └── skills/<skill>/SKILL.md    # 공용 skill 원본
├── tools/                         # 직접 실행하는 스크립트
├── AGENTS.md                      # 지침 통합 문서
├── AGENTS.principle.md            # 모든 에이전트가 준수하는 공통 지침 문서
├── AGENTS.project.md              # 프로젝트 작업 흐름 지침 문서
├── CLAUDE.md                      # Claude Code 전용 지침 통합 문서
└── README.md                      # 저장소 정보 문서
```

## Agent

각 에이전트는 사용자를 `AGENTS.md`에 적힌 호칭으로 부른다.
에이전트가 서브에이전트 호출 시 사용자의 승인을 받으며, 토큰 소모를 막기 위해 1 depth로 제한한다.

| 에이전트   | 이름         | 역할                                             |
| ---------- | ------------ | ------------------------------------------------ |
| assistant  | buddy(버디)  | 기본 작업: 독립적인 웹 서치, 파일 변경 등        |
| director   | rio(리오)    | 프로젝트 작업: 사용자 판단, 실행 승인, 전체 흐름 |
| planner    | nico(니코)   | 프로젝트 작업: 조사, 비교, 계획                  |
| worker     | jelly(젤리)  | 프로젝트 작업: 구현                              |
| reviewer   | ricky(리키)  | 프로젝트 작업: 검증, 검수                        |
| documenter | pepper(페퍼) | 프로젝트 작업: 상태, 지식, 지침, 작업 중간 기록  |

- [에이전트 규약](/AGENTS.md)
- [에이전트 프로젝트 공통 규약](/AGENTS.project.md)
- [프로젝트 작업 흐름 명세](shared/skills/workflow/SKILL.md)

각 에이전트의 역할과 persona는 .claude/agents/ 폴더를 참고한다.

## Discord

### Agent

Discord 채널의 에이전트 봇 목록

| 에이전트   | 이름         | 역할                                          |
| ---------- | ------------ | --------------------------------------------- |
| assistant  | buddy(버디)  | 일회성 및 반복 알림 예약                      |
| director   | rio(리오)    | 대화 흐름 조정, 투표와 스레드 생성            |
| planner    | nico(니코)   | 새 정보 조사, 최신 정보 확인                  |
| worker     | jelly(젤리)  | 코드 조각, 글 초안, 정리, 계산 등 결과물 작성 |
| reviewer   | ricky(리키)  | 발언 검토, 인용 대조, 사실 검증               |
| documenter | pepper(페퍼) | 지식 저장소 조회, 기록, 삭제                  |

- [봇 권한 목록](docs/discord.md#discord-서버-추가)

Discord 채널의 웹훅 봇 목록

| 이름       | 역할                                                    |
| ---------- | ------------------------------------------------------- |
| Hugo(휴고) | 디스코드 webhook 봇: 현재 repository의 push 이벤트 알림 |

- [Github 웹훅 설정 방법](docs/discord-github-webhook.md)
- [긱뉴스 디스코드 봇](https://news.hada.io/discordbot)

## 환경별 연결

- Claude Code: [docs/claude-code.md](docs/claude-code.md)
- Codex: [docs/codex.md](docs/codex.md)
- Cursor: [docs/cursor.md](docs/cursor.md)
- Discord: [docs/discord.md](docs/discord.md)
  - GCP 배포: [docs/discord-gcp.md](docs/discord-gcp.md)
  - GCP 운영: [docs/discord-gcp-operations.md](docs/discord-gcp-operations.md)
  - 동작 명세: [docs/discord-spec.md](docs/discord-spec.md)
  - 디버그: [docs/discord-debug.md](docs/discord-debug.md)
- OpenClaw: [docs/openclaw.md](docs/openclaw.md)
- Hermes: [docs/hermes.md](docs/hermes.md)

## Skill 연결

- [docs/skill-link.md](docs/skill-link.md)
