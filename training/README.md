# 학습

> 이 폴더에는 **데이터셋도 학습된 가중치도 들어 있지 않다.**
> 프로젝트 당시의 데이터셋(약 1,000프레임)과 `best.pt` 는 보존되어 있지 않고,
> 부트캠프 실습 이미지는 공개·재사용 허가를 확인할 수 없어 포함하지 않았다.
> 여기 있는 것은 같은 구조를 다시 만들기 위한 **틀과 절차**다.

## 당시의 조건 (사용자 진술 기준)

| 항목 | 값 | 확인 수준 |
|---|---|---|
| 모델 | YOLOv11 | 사용자 확정. 문서에 따라 v8 표기도 있었음 |
| 클래스 | normal / robotfix / humanfix | 문서 표기 기준. 최종 코드 문자열은 확인 불가 |
| 데이터 규모 | 약 1,000프레임 | 사용자 확정 |
| epoch | 100 | 사용자 진술 |
| 학습 환경 | 클라우드 GPU(Colab) | 사용자 진술 |
| 추론 환경 | Raspberry Pi 5 온보드 | 사용자 진술 |
| 성능 지표 | **없음** | 반복 정량 측정을 수행하지 않았음 |

성능 수치를 적지 않은 것은 겸양이 아니라, 측정하지 않았기 때문이다.

## 절차

1. `training/dataset_schema.yaml` 의 `_expected_layout` 대로 폴더를 만든다.
2. 조치 등급별 판별 대상을 준비하고, **주행 중인 차체 시점**에서 거리·각도를 바꿔 가며 촬영한다.
3. 3클래스로 라벨링하고 train / val / test 로 나눈다. 같은 촬영 세션이 양쪽에 섞이지 않게 한다.
4. 학습한다.

   ```bash
   python training/train_example.py --data training/dataset_schema.yaml
   ```

5. `best.pt` 를 엣지 보드로 옮기고 추론을 확인한다.

   ```bash
   python scripts/run_inference_example.py --weights runs/triage3/weights/best.pt --image <파일>
   ```

## 주의

- `configs/classes.yaml` 의 `class_names` 와 데이터셋 `names` 는 **반드시 같아야 한다.**
  다르면 모든 판정이 `UNKNOWN_CLASS` 로 떨어지고, 설계상 사람 쪽으로 넘어간다.
- 단일 조명·단일 배경에서만 촬영했다면 일반화를 검증한 것이 아니다. 정확도를 주장하지 말 것.
- 엣지 보드에서 학습하지 말 것. 학습은 GPU 환경에서, 추론만 보드에서 한다.
