# Archive

Obsidian 기반 개인 지식 관리 구조이다.
Obsidian 관련 개인 설정 파일은 저장소에 포함하지 않는다.

## 폴더 구조

```text
archive/
├── AGENTS.md          # 에이전트 규칙(작업 절차, 폴더, 서식, 파일명, 프론트매터, 링크)
├── CLAUDE.md          # AGENTS.md를 불러온다
├── raw/               # 사람이 넣는 수집 자료(글, 강의 자료, 메모 등). 넣은 뒤 수정하지 않는다
├── schema/            # 사람이 작성하는 ingest, query, lint 절차. 작업 1개당 문서 1개
└── wiki/              # 에이전트가 ingest로 작성하는 위키
    ├── sources/       # raw/ 파일 1개의 요약
    ├── entities/      # 사람, 조직, 제품, 도구 같은 고유명사
    ├── concepts/      # 개념, 방법론, 원리
    └── INDEX.md       # 위키 전체 목차
```

예를 들어 AI 관련 프롬프트 개념은 `wiki/concepts/ai-prompt-<name>.md`에 둔다.

## 운영 절차

| 작업   | 용도                                  | 문서                       |
| ------ | ------------------------------------- | -------------------------- |
| ingest | `raw/` 자료를 위키에 편입한다.        | [ingest](schema/ingest.md) |
| query  | 위키를 검색해 인용과 함께 답한다.     | [query](schema/query.md)   |
| lint   | 위키 품질을 점검하고 정리를 제안한다. | [lint](schema/lint.md)     |

작업을 요청할 때는 "ingest.md에 따라 `raw/파일명`을 ingest해 줘"처럼 해당 문서를 지정한다.

## 참고 자료

- [Brian Wong의 Wiki Schema](http://brianwong.com/Wiki/Schema/)
- [Karpathy의 LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
