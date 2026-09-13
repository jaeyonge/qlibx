# First-run structural proof

- 목적: 첫 실행에서도 고유값 검사를 생략할 수 있는지 실제 사용자 전체 경로로 확인함
- 고정 조건: 실제 DW 자료, 2018-01-02~2026-07-20, 309종목, 일별 모델, 64개 위험 상황, 주별 롱숏 전략임
- 비교 기준: exp_253의 동일 조건 기존 측정과 현재 브랜치의 구조 증명 경로임
- 실행: `uv run python experiments/exp_251_first_run_structural_proof/run.py --mode full`
- 결과: `outputs/REPORT.md`에 기록함
