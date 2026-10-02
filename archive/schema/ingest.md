# ingest

이 문서는 `raw/` 파일의 위키 편입 절차이다.

## 입력

- `PATH`는 `raw/` 기준 파일 경로이다.

## 절차

### 자료 확인

1. 현재 날짜를 조회해 `YYYY-MM-DD` 형식으로 표기한다.
2. `raw/PATH` 파일을 확인한다.
3. `raw/PATH` 파일에서 아래 항목을 추출한다.
   - 주제
   - `entities` 대상(고유명사)
   - `concepts` 대상
   - 핵심 주장과 인용
4. 핵심어와 `entities`, `concepts` 대상 이름으로 `wiki/` 폴더를 검색한다.

### 페이지 작성

1. `wiki/sources/<topic>-<subtopic>-<name>.md` 페이지를 작성한다.
   `<topic>`은 대주제, `<subtopic>`은 세부 주제이다.
   `AGENTS.md`의 `폴더`, `파일명` 이름 규칙을 적용한다.
   - `AGENTS.md`의 프론트매터
   - `## 요약` 절의 요약 목록
   - `## entities` 절의 `wiki/entities/` 링크 목록
2. 추출한 `entities`, `concepts` 대상별로 아래 절차를 수행한다.
   1. 이름과 별칭으로 `wiki/entities/` 또는 `wiki/concepts/`를 검색한다.
   2. 페이지가 없으면 아래 경로 중 하나에 신규 작성한다.
      - `wiki/entities/<topic>-<subtopic>-<name>.md`
      - `wiki/concepts/<topic>-<subtopic>-<name>.md`
   3. 페이지가 있으면 끝에 아래 절을 추가하고 새 사실을 기록한다.
      프론트매터의 `date`를 1단계의 날짜로 갱신한다.

   ```markdown
   ## From [[wiki/sources/ai-harness-long-running-agents|Long-running agents]]

   - 사실
   ```

### 목차 갱신

1. `wiki/INDEX.md`의 해당 절에 새 페이지를 추가한다.

   ```markdown
   - [[wiki/concepts/ai-loop-ralph-wiggum|Ralph Wiggum loop]] | 요약
   ```

## 진행 방식

1. 단계별 결과를 확인한다.
2. 파일 작성 또는 수정 전 내용을 우선 제안한다.
