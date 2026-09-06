# 구조

## 계층

```
        판정 대상
            │
   ┌────────▼─────────┐
   │  inference.py    │   프레임 → 클래스 + 신뢰도 (다수결)
   │  simulation.py   │   또는 미리 정해 둔 판정 결과
   └────────┬─────────┘
            │  Detection
   ┌────────▼─────────┐
   │ decision_policy  │   대응표 조회. 판정할 수 없으면 사람 쪽으로
   └────────┬─────────┘
            │  Decision(action, destination, requires_human, reason)
   ┌────────▼─────────┐
   │  state_machine   │   허용된 전이만. 실패는 전부 SAFE_STOP 으로
   └────────┬─────────┘
            │  Protocol 호출
   ┌────────▼─────────┐
   │  interfaces.py   │   DriveBase / Manipulator / Notifier / PerceptionSource
   └────────┬─────────┘
            │
   simulation.py  ←→  (실물 구현은 이 저장소에 없음)
```

## 왜 이렇게 나눴나

**판정과 조치를 분리한 이유.** 모델을 바꾸거나 클래스를 늘려도 바뀌는 것이
`configs/classes.yaml` 한 장이 되게 하려는 것이다. 경로를 신뢰도 순위나
if-else 사슬로 정하면, 클래스가 하나 늘 때마다 로직을 다시 읽어야 한다.

**상태 머신이 하드웨어를 모르게 한 이유.** 실물 로봇 없이 로직을 끝까지 돌려
검증할 수 있어야 하기 때문이다. 프로젝트 당시에도 구현 가능 시간이 짧아
"돌려 보고 고치는" 여유가 없었다.

**fallback 이 항상 사람 쪽인 이유.** 신뢰도 미달·모르는 클래스·검출 없음은
서로 다른 원인이지만, 자동으로 처분해서는 안 된다는 점에서 같다.
설정 검증 단계에서 `fallback.requires_human` 이 `true` 가 아니면 로드를 거부한다.

## 상태 전이표

| 현재 | 다음 |
|---|---|
| IDLE | ACQUIRE |
| ACQUIRE | TRIAGE |
| TRIAGE | ROUTE |
| ROUTE | TRANSIT |
| TRANSIT | DOCK |
| DOCK | ROBOT_FIX · HUMAN_HANDOFF |
| ROBOT_FIX | VERIFY |
| HUMAN_HANDOFF | RETURN |
| VERIFY | RETURN |
| RETURN | DONE |
| DONE · SAFE_STOP | (종료) |

`SAFE_STOP` 은 종료 상태를 제외한 어느 상태에서든 갈 수 있다.
표에 없는 전이는 `InvalidTransition` 으로 거부한다. `ROBOT_FIX → RETURN` 처럼
검증을 건너뛰는 경로가 실수로 생기지 않게 하려는 것이다.

## 실패 처리

| 상황 | 결과 |
|---|---|
| 마커 정차 실패 | SAFE_STOP. 매니퓰레이터를 부르지 않는다 |
| `normal` 재검출 타임아웃 | SAFE_STOP. **성공으로 넘기지 않는다** |
| 주행·통신 예외 | SAFE_STOP + `error` 에 원인 기록. 예외를 삼키지 않는다 |
| 어떤 경로로 끝나든 | `finally` 에서 구동계 정지 |
