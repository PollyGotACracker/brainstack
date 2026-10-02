# 지식 저장소 원칙

## 작업 절차

### 경로 기준

- `raw/`, `wiki/`, `schema/`, 위키링크의 기준은 이 문서가 있는 `archive/`이다.
- 저장소 루트 기준 파일 경로에는 `archive/` 접두를 붙인다.
  - 위키링크 표기 유지
- 저장소 루트를 명시한 지침 및 `.github/` 템플릿 경로는 저장소 루트를 기준으로 한다.

### 처리 순서

1. 현재 작업에 선택된 schema의 원본 절차를 적용한다.
2. 해당 schema의 승인·결과 보고 절차에 따라 작업을 완료한다.

## 폴더

### 구성

- `raw/`에는 수집 자료의 원본을 그대로 보존한다.
- `wiki/entities/`에는 고유명사 1개당 1페이지를 배치한다.
- `wiki/concepts/`에는 개념·방법론·원리 1개당 1페이지를 배치한다.
- `wiki/sources/`에는 `raw/` 파일 1개당 요약 1페이지를 배치한다.
  생성 주체는 ingest이다.
- `wiki/INDEX.md`는 전체 목차이다.
- `schema/`에는 ingest·query·lint 절차를 배치한다.

### 배치 기준

`entities`, `concepts`, `sources` 페이지는 파일명의 주제순 정렬이 가능하도록 배치한다.

## 문서 서식

- 같은 종류의 기존 문서 서식을 확인해 우선 적용한다.
- 본문은 글머리 기호 목록으로 작성한다.
- 목록 들여쓰기는 탭 1개를 한 단계로 사용한다.
  예외로 YAML 프론트매터는 공백을 사용한다.
- 기존 문서에 없는 서식에는 루트 `AGENTS.md`의 `서식 및 문서 작성` 절을 적용한다.

## 파일명

- `wiki/INDEX.md`는 관리 파일명을 유지하고 아래 페이지 명명 규칙의 적용 대상에서 제외한다.
- 페이지 파일명은 영문 소문자·숫자·하이픈만으로 kebab-case로 구성한다.
- 대주제는 파일명의 첫 단어이며 파일명에는 대상을 구별하는 핵심 단어만 포함한다.
  같은 세부 주제의 페이지는 대주제의 이름순 정렬에서 함께 배치한다.
- 원문 제목 전체는 프론트매터 `title`에, 한글 이름은 `title`과 `aliases`에 기록한다.

```text
wiki/entities/ai-harness-codex.md
wiki/entities/ai-loop-claude-agent-sdk.md
wiki/concepts/ai-harness-engineering.md
wiki/concepts/ai-loop-ralph-wiggum.md
wiki/concepts/ai-prompt-caching.md
wiki/sources/ai-harness-long-running-agents.md
```

## 프론트매터

`wiki/INDEX.md`를 제외한 모든 위키 페이지에는 아래 프론트매터를 포함한다.

```yaml
---
aliases: []
title: 제목
date: YYYY-MM-DD
tags: [wiki, 분류]
description: ""
draft: false
related: [
    "[[wiki/concepts/ai-harness-engineering]]",
    "[[wiki/entities/ai-harness-codex]]",
  ] # 선택
---
```

- 페이지 작성·수정 시 `date`를 마지막 수정 날짜로 갱신한다.
- 선택 항목 `related` 사용 시 위키링크를 따옴표로 감싼다.
  목적은 Obsidian의 YAML 인식이다.

## 링크

### 기본 형식

- 위키링크는 항상 전체 경로로 작성하고 별칭은 필요한 경우 첨부한다.

```markdown
[[wiki/concepts/ai-harness-engineering|Harness engineering]]
[[wiki/concepts/ai-loop-ralph-wiggum|Ralph Wiggum loop]]
[[wiki/sources/ai-harness-long-running-agents|Long-running agents]]
```

### 외부 링크

- 외부 URL은 `[표시 이름](URL)` 형식의 마크다운 링크로 작성한다.
- 표시 이름은 서비스명 또는 `소유자/저장소`이다.
- 코드 블록 안의 원문 URL은 원문 보존을 위해 변환에서 제외한다.

```markdown
[TypeSafe](https://typesafe.ai/)
[fivetaku/awesome-jev-study](https://github.com/fivetaku/awesome-jev-study)
```

### 표 안 링크

- 표 안 링크는 별칭 구분자 `|`를 백슬래시 하나로 이스케이프해 한 셀로 표시한다.

```markdown
| [[wiki/concepts/ai-prompt-caching\|Prompt caching]] | 반복되는 프롬프트 앞부분을 캐시한다 |
```

## Branch

- 기본 브랜치는 `master`이다.
- 브랜치 생성 규칙은 `<타입>/이슈번호`이다.

## Commit

- 커밋 단위는 승인된 변경 세트이다.
- 메시지 형식은 `<타입>: <제목>`이다.
- 허용 타입은 `feat`, `fix`, `chore`, `docs`이다.
- 제목 언어는 한국어이다.
- 제목 길이는 40자 이내이다.
- 본문 규칙은 아래 형식을 따른다.

```text
<타입>: <제목> (제목은 40자 이내)

<본문> (한 줄 띄우고 작성. 72자 이내로 줄 바꿈)

Resolves: #<이슈번호>(생략 가능)
See also: #<이슈번호>(생략 가능)
```
