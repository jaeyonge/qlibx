# 281 — 위험 점수 생성과 투자 전략 실행은 두 개의 이어진 run이다

| | |
|---|---|
| **작성 시각** | 2026-09-13 KST (+09:00) |
| **계획** | `.agent/plans/active/certified-risk-onboarding.md` |
| **설계 근거** | `docs/vqapr-prd.md` §2.3 · §2.4, shipped `make-datamodel` skill |
| **브랜치** | `codex/v016-certified-risk-onboarding` |
| **앞선 기록** | `280`(같은 위험 행렬의 안전 검사 재사용) |
| **깨지는 변화** | 없음. 설치되는 안내 확장 |

---

## 왜 이 변경이 있는가

빠른 행렬 풀이만 공개하면 처음 쓰는 사람은 그것을 어느 파일에 넣고, 데이터를 언제 등록하며,
DataModel 결과를 어떻게 StrategyModel에 연결하고, 첫 실행과 반복 실행을 어떻게 구분하는지 알 수
없음. 특히 비싼 계산과 매매를 한 단계로 섞으면 계산 결과를 여러 전략이 재사용하지 못하고, 생산자와
소비자를 같은 병렬 batch에 넣으면 현행 제품이 의도적으로 거절함.

## 무엇이 어떻게 바뀌었는가

- 설치되는 `make-datamodel` skill에 긴 위험 모델 전용 reference를 추가함.
- 환경 확인용 sample, 실제 PIT 데이터 등록, DataModel scaffold, 공개 solver 연결, DataModel의 최초 실행,
  `--force` 반복 실행, StrategyModel과 별도 run 생성, 결과 조회와 export를 한 순서로 적음.
- 처음 실행은 안전 검사를 포함하고, 반복 실행은 정확히 같은 행렬만 증명을 재사용한다고 구분함.
- 새 날짜나 값이 들어오면 그 행렬만 다시 검사하며, 캐시 삭제는 시간만 바꾼다고 명시함.
- 계산 결과의 수치 허용오차, 실제 종목·주문·체결·수익률 동일, 파일 바이트 동일을 서로 다른 검증으로
  구분함.
- `introduce-vqapr`의 작업 표에서 10분 이상 걸리는 공분산·시나리오 위험 모델을 이 경로로 보냄.
- 안내가 실제 공개 이름과 두 run의 순서를 계속 지키는 계약 테스트를 추가함.

## 대안과 판단

- 거대한 단일 pipeline skill을 만들지 않음. 데이터 의미는 `register-dataset`, 값 생성은
  `make-datamodel`, 포트폴리오는 `make-strategy`, 실행은 `run-backtest`, 해석은 `analyze-result`가
  계속 소유함.
- sample 성과를 투자 근거로 제시하지 않음. sample은 설치와 명령 경로만 확인함.
- DataModel을 주 1회로 바꾸지 않음. 계산 빈도는 연구 질문이 정하며, 주간 매매 주기는 전략 run에 둠.
- 병렬 실행을 필수로 권하지 않음. 생산자 DataModel을 먼저 끝내야 소비 전략이 실행될 수 있음.

## 검증

| 검사 | 결과 |
|---|---|
| shipped skill 구조·링크 계약 | 89개 관련 검사 통과 |
| 공개 solver 이름과 두 run 순서 계약 | 통과 |
| `vqapr new datamodel ...` 실제 출력 확인 | `risk_scores.py`, `risk_scores.yaml`, `risk-scores-run` 확인 |
| `vqapr new strategy ...` 실제 출력 확인 | `weekly_risk_momentum.py`, 등록 YAML 확인 |
| built wheel을 새 빈 프로젝트에 설치 | 성공, 새 reference가 두 agent target에 설치됨 |
| sample 온보딩 | 등록·check·run 성공, 1,468 events |
| DataModel 최초/반복 | 각 734 sessions · 6,898 rows, parquet SHA-256 동일 |
| 증명 캐시 | 최초 734개 증명, 반복 뒤 개수 동일 |
| 후속 주간 전략 | 129 decisions · 389 dealt fills · completed |
| 결과 전달 | nav · holdings · fills · weights · report export 성공 |
| 전체 저장소 검사 | 1,808 통과 · 6 skip · 122.22초 |
| final wheel 재설치 | 공개 solver import와 risk reference 설치 확인 |

이 작은 sample 여정은 공개 경로의 연결만 검증함. 속도 근거는 실제 DW 전체를 사용한 실험 253의
14분 42초 → 1분 52초~2분 5초 결과임.

## 남은 한계

- reference의 위험 계산 본문은 사용자의 전략과 데이터 의미에 따라 달라지므로 scaffold 전체를 대신하지
  않음. 실제 등록의 공개 시각과 필드 의미는 사용자가 확정해야 함.
- vqapr CLI는 한 줄 JSON을 소유하므로 DataModel callback에서 solver 통계를 출력하지 않게 안내함. 전체
  run은 외부 경과 시간과 캐시 항목 수로 최초/반복을 구분함.
- 실제 투자 성과는 sample이 아니라 사용자의 등록된 데이터와 별도 StrategyModel run에서만 판단함.
