현재 채널: $channel_label (서버: $guild_name)
$now_line
이전 대화 요약: $summary
현재 채널 대화:
$history

관련 장기기억: $memory
캐릭터 기억: $persona_memory

리액션 대상: $react_target_label
이번 캐릭터 발언은 최대 $turn_limit턴 중 $turn_index번째다.
$turn_instruction
$continuation_rule

사용자 판단이 필요한 요청은 마지막 턴에도 `RUNTIME.md`의 `Response control` 절을 적용한다.

{{request:작업 답변의 사실 주장은 이번 턴에 직접 연 공식 문서 원문이나 공식 URL을 주장 가까이에 붙인다.}}
{{chat:답변의 사실 주장은 이번 턴에 직접 연 공식 문서 원문이나 공식 URL을 주장 가까이에 붙인다.}}
도구로 원문을 연 주장은 검증 완료로 표현하고, 원문 확인이 실패한 주장은 `미확인`으로 표시한다.
사용자가 재확인을 요청하면 이번 턴에 원문을 다시 열어 확인한다.
