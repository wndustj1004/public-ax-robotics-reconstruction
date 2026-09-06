# EM 플레이트 Triage — 시나리오 기반 코드 재구성

배양 플레이트의 상태를 판별해 **조치 등급**으로 바꾸고, 등급에 따라 로봇 교체 스테이션
또는 사람 QC 스테이션으로 보내고, 조치가 끝났는지를 **다시 인식해서** 확인한 뒤에야
복귀하는 한 사이클. 그 의사결정 구조를 코드로 옮긴 교육용 저장소다.

---

## ⚠ 먼저 읽을 것 — 이 저장소의 성격

> **본 저장소의 코드는 프로젝트 당시 사용한 원본 코드가 아니다.**
>
> 프로젝트 당시의 최종 통합 코드는 보존되지 않았다. 이 저장소는 그 상황에서,
> 당시의 프로젝트 시나리오와 교육자료를 바탕으로 **구현 취지를 설명하기 위해
> 2026년 9월에 새로 작성한 교육용 예제**다. 실제 프로젝트 당시의 구현물 또는
> 당시 성능을 그대로 재현한다고 주장하지 않는다.

- 커밋 날짜는 전부 실제 작업일이다. 과거로 소급하지 않았다.
- 정확도·mAP·FPS·성공률·지연시간을 적지 않았다. **측정하지 않았기 때문이다.**
- 학습된 가중치와 데이터셋은 들어 있지 않다.
- 실물 로봇에서 실행한 적이 없다.

자세한 내용은 [RECONSTRUCTION_NOTICE.md](RECONSTRUCTION_NOTICE.md) 와
[NOTICE.md](NOTICE.md)(AI 활용 고지 포함).

---

## 배경

무균 주사제 제조소는 클린룸의 미생물 오염을 감시하기 위해 배양 플레이트를 상시로
깔고 회수해 판독한다. 개정 EU GMP Annex 1 이 노출 시간을 제한해 교체가 반복되는데,
클린룸에서 교체하려면 사람이 들어가야 하고 사람은 그 구역에서 관리 대상 1순위
오염원이다. 규제를 지키기 위한 행위가 규제가 막으려는 위험을 만든다.

상용 자동화 장비는 판독·교체·배양계수를 각각 자기 공정 안에서 처리한다.
**장비와 장비 사이의 연결 구간** — 판정하고, 목적지를 정하고, 옮기고, 인계하고,
완료를 확인하는 구간 — 이 비어 있다. 프로젝트는 이 구간을 대상으로 삼았다.

> 규제 조문의 조항 번호와 발효일은 공식 원문 재확인이 필요하다.
> 이 저장소는 규제 해석을 제공하지 않는다.

## 당시 프로젝트 시나리오

3인 팀 · 5일 과정 부트캠프의 최종 프로젝트 · 실제 구현 가용 시간 약 4시간.

| 클래스 | 필요한 조치 | 목적지 |
|---|---|---|
| `normal` | 통상 보관·기록. 이 시스템에서는 **교체 완료 확인 신호** | ZONE2 (확인용) |
| `robotfix` | 결함 플레이트 회수 후 정상 플레이트로 교체 | ZONE2 로봇 교체 스테이션 |
| `humanfix` | 격리 이송 후 자격자가 판독·조사 | ZONE3 사람 QC 스테이션 |

클래스를 '보이는 것'이 아니라 **'필요한 조치'에서 역산해** 정의했고, 클래스와 목적지를
1:1로 대응시켰다. 그래서 판정 뒤에 별도의 규칙 계층을 두지 않고, 사전에 정의한
대응표 한 장으로 경로가 결정된다.

전체 시나리오와 두 루트의 흐름은 [docs/scenario.md](docs/scenario.md).

## 이번 재구성의 목적

원본이 없는 상태에서 "당시 무엇을 만들었다"를 증명할 수는 없다.
대신 **지금 확인할 수 있는 것**을 확인 가능한 형태로 남기는 것이 목적이다.

- 시나리오를 소프트웨어 요구사항으로 옮기는 일
- 판정 결과와 후속 조치를 연결하는 구조를 설계·구현하는 일
- 상태 전이와 예외·안전 정지를 설계하는 일
- 하드웨어 없이 검증 가능한 부분을 분리해 테스트를 작성하는 일
- 확인된 것과 확인되지 않은 것을 구분해 문서화하는 일
- AI가 만든 코드 초안을 사람이 검토·확정하는 일

## 구조

```
├─ configs/classes.yaml          클래스 - 조치 - 목적지 대응표 (단일 진실 원천)
├─ src/
│  ├─ config.py                  설정 로드 + 규약 검증
│  ├─ decision_policy.py         판정 → 조치. 판정 불가는 전부 사람 쪽으로
│  ├─ state_machine.py           허용된 전이만. 실패는 전부 SAFE_STOP 으로
│  ├─ interfaces.py              하드웨어 경계 (Protocol)
│  ├─ inference.py               실제 추론 어댑터 (가중치 없으면 명확히 실패)
│  └─ simulation.py              하드웨어 대역
├─ scripts/
│  ├─ run_simulation.py          시나리오 7종을 끝까지 돌려 본다
│  └─ run_inference_example.py   가중치가 있을 때 한 장 판정
├─ training/                     데이터셋 스키마 + 학습 절차 (데이터·가중치 없음)
├─ tests/                        32개. 하드웨어 없이 도는 것만
└─ docs/                         시나리오 · 구조 · 역할 · 한계 · 증거 연결표
```

## 기능

- **대응표 기반 라우팅** — 경로를 신뢰도 순위로 정하지 않고 사전 정의된 표를 조회한다.
- **보수적 실패** — 신뢰도 미달 / 모르는 클래스 / 검출 없음은 전부 사람 쪽으로 간다.
  설정 로드 단계에서 `fallback.requires_human != true` 면 거부한다.
- **다수결 판정** — 한 프레임의 흔들림이 그대로 경로 결정이 되지 않게 한다.
  *(당시 코드에 있었다는 근거는 없다. 이번 재구성에서 넣은 설계다.)*
- **재인식 기반 완료 검증** — "끝났다는 신호"가 아니라 `normal` 재검출로 완료를 판정한다.
  시간이 지났다는 이유로 성공 처리하지 않는다.
- **상태 전이 강제** — 표에 없는 전이는 예외. 검증 단계를 건너뛸 수 없다.
- **안전 정지 수렴** — 정차 실패·타임아웃·예외가 전부 `SAFE_STOP` 으로 모이고,
  어떤 경로로 끝나든 `finally` 에서 구동계를 멈춘다.

## 설치

```bash
git clone <이 저장소 URL>
cd public-ax-robotics-reconstruction
python -m venv .venv
.venv\Scripts\activate        # Windows / macOS·Linux 는 source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.10 이상. 로직과 테스트에 필요한 것은 `PyYAML` 과 `pytest` 뿐이다.

## 실행

### simulation — 하드웨어 없이

```bash
python scripts/run_simulation.py
python scripts/run_simulation.py --case verify-timeout
```

시나리오 7종(정상 2루트 + 신뢰도 미달 + 미정의 클래스 + 검출 없음 +
재검출 타임아웃 + 정차 실패)의 대응표 조회 결과와 상태 전이를 출력한다.

```
=== robotfix ===
  입력  : robotfix conf=0.93
  대응표: TABLE_HIT -> ROBOT_REPLACE / ZONE2 (사람 판단 필요: 아니오)
  전이  : ACQUIRE -> TRIAGE -> ROUTE -> TRANSIT -> DOCK -> ROBOT_FIX -> VERIFY -> RETURN -> DONE
  결과  : DONE
```

### 실제 추론 — 가중치가 있을 때

```bash
python scripts/run_inference_example.py --weights runs/triage3/weights/best.pt --image <파일>
```

**이 저장소에는 가중치가 없다.** 그대로 실행하면 무엇이 없는지 알려 주고 종료한다
(exit code 3). "모델이 있는 척"을 만들지 않기 위해서다.

### 테스트

```bash
python -m pytest tests -q
python -m unittest discover -s tests     # pytest 없이도 된다
```

### Raspberry Pi 5

**검증하지 않았다.** 실물 보드가 없어 설치·실행을 확인하지 못했다.
아래는 예상 절차이며, 그대로 동작한다고 보장하지 않는다.

```bash
sudo apt-get update && sudo apt-get install -y python3-venv libgl1
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install ultralytics opencv-python     # AGPL-3.0 — 라이선스 조건 확인 후 사용
python scripts/run_simulation.py          # 먼저 로직만 확인
```

주의할 점: 학습은 보드에서 하지 않는다(GPU 환경에서 하고 가중치만 옮긴다).
추론을 외부 PC에 두지 않는다(통신 실패가 그대로 동작 실패가 된다).
한글 표시가 필요하면 한글 폰트를 따로 설치해야 한다.

## 수업자료를 활용한 부분

부트캠프 수업자료는 **공개·재사용 허가를 확인할 수 없어 저장소에 넣지 않았고,
원문을 복사하지도 않았다.** 어떤 주제가 어떤 설계로 이어졌는지만
[docs/course-material-references.md](docs/course-material-references.md) 에 적었다.

---

## 역할 구분

세 가지를 구분한다. 자세한 표는 [docs/role-boundaries.md](docs/role-boundaries.md).

### 🅐 프로젝트 당시 **본인이 수행한 것으로 확인된 것**

주도 — 산업 배경·규제 조사, 상용 자동화 벤치마킹, 문제 정의,
**3클래스 조치등급 설계**, **YOLO 학습 및 엣지 보드 탑재**, 기획서 집필, 발표자료·발표.

공동 — 데이터셋 구축(표준 이미지 설계·촬영 조건 수립), 카메라 캘리브레이션,
그리고 **사양 제안** 3건: 재인식 기반 완료 판정 / 대기 구간 화면 유지 / 거리 기반 마커 정차.
세 건 모두 **요구사항을 정의해 제안한 것이고, 코드는 팀원이 작성했다.**

### 🅑 프로젝트 당시 **팀원이 담당한 것**

라인트레이싱과 교차로 판정, 주행 튜닝, 이기종 로봇 간 파일 핸드셰이크,
통합 실행 루프, 모방학습(ACT) 데이터 수집과 정책 학습.

**이 저장소에 없다.** `src/interfaces.py` 에 경계면만 남겨 두었고 실물 구현은 없다.
본인 역량의 근거로 쓰지 않는다.

### 🅒 **이번 저장소에서 새로 재구성한 것** — 2026년 9월

`src/` 전체, `tests/` 전체, `training/` 의 틀, `configs/classes.yaml`, `docs/` 전체.
🅐의 설계 판단을 코드로 옮긴 것이지만, **코드 자체는 전부 이번에 새로 쓴 것이다.**

---

## 확인한 것

이 저장소에서 실제로 실행해 확인한 범위다. 실행하지 않은 것은 아래에 없다.

| 확인 내용 | 명령 | 결과 |
|---|---|---|
| 단위 테스트 | `python -m pytest tests -q` | **32 passed, 27 subtests passed** |
| 표준 러너 호환 | `python -m unittest discover -s tests` | **OK (32 tests)** |
| simulation 7종 | `python scripts/run_simulation.py` | 7종 전부 의도한 상태로 종료 |
| 가중치 없을 때의 동작 | `python scripts/run_inference_example.py --weights runs/best.pt --image x.jpg` | 안내 메시지 출력 후 exit 3 |
| 설정 규약 위반 거부 | 테스트에 포함 | 클래스 누락·fallback 오설정 모두 거부 |

실행 환경: Windows 11 / Python 3.14.4 / PyYAML 6.0.3 / pytest 9.1.1 (2026-09-06)

## 확인하지 않은 것

- **실제 추론 경로** — `ultralytics` 를 설치해 돌려 보지 않았다. 가중치가 없다.
- **실물 하드웨어** — Raspberry Pi 5, AMR, 매니퓰레이터 어느 것도 사용하지 않았다.
- **모델 성능** — 학습도 평가도 하지 않았다.
- **당시 코드와의 일치 여부** — 원본이 없어 대조할 대상이 없다.

## 한계

[docs/limitations.md](docs/limitations.md) 에 전부 적었다. 요약하면,

- 이 저장소는 **로직만** 검증했다. simulation 결과는 성능 지표가 아니다.
- 당시 프로젝트는 반복 정량 측정을 수행하지 않았다. 정확도·성공률을 주장하지 않는다.
- ROBOT FIX 루트에는 **사람의 개입이 설계에 포함되어 있다.** 완전 무인 사이클이 아니다.
- `configs/classes.yaml` 의 클래스 문자열과 신뢰도 임계값은 **확인되지 않은 값**이다.
  문서 표기와 이전 세대 팀 노트북의 표기가 서로 다르고, 최종본을 확인할 수 없다.
- 교육용 하드웨어를 전제한 개념검증이다. GMP 밸리데이션·LIMS 연동은 범위 밖이다.

## 라이선스와 출처

- 이 저장소의 코드·문서: [MIT](LICENSE)
- 저장소에 포함하지 않은 제3자 자료(수업자료, 팀원 코드, 제조사 문서)에는 적용되지 않는다.
- 생성형 AI 활용 범위와 사람이 한 판단의 구분: [NOTICE.md](NOTICE.md)
- `ultralytics` 를 실제 학습·추론에 쓸 경우 해당 패키지의 AGPL-3.0 조건을 직접 확인할 것.
