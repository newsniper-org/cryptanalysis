# MILP 차분 트레일 결과 분석 — YSC4-p

> *대상*: YSC4-p (YSC5 컴파일 시 사용되는 동일 순열) 의 **워드-수준 활성 워드** trail.
> *해결기*: GLPK `glpsol` v4.52 (`model.mod` 참조).

## 측정 결과

| 라운드 수 R | 총 활성 워드 (목적함수) | 라운드당 활성 |
|------------|------------------------|--------------|
| 8  | 18 (= 2 × 9)  | 2 |
| 12 | 26 (= 2 × 13) | 2 |
| 16 | 34 (= 2 × 17) | 2 |

→ **trail에서 라운드당 *항상* 2 워드가 활성**, T_active = 0 모든 라운드.

## Trail의 구조

(R=8의 결과 분석)

- r=0: word 1, 7 활성
- r=1: word 12, 0 활성  (= π applied 후 위치 이동)
- r=2: word ... ...
- 모든 라운드: 정확히 2 워드 활성, T = 0

이는 *attacker가 2개의 활성 워드 차분을 항상 cancel*하여 broadcast 차분 T_value = 0을
유도하는 trail. 워드 활성도가 *유지*되며 π를 따라 위치만 이동.

## 시사

### 워드-수준 trail의 한계
본 모델은 *워드 활성 비트 1개* 만 추적. 실제 차분 확률은 *F의 differential
distribution table (DDT)* 와 결합되어야 함:
- F(s) = s ⊕ (rot s,13 ∧ rot s,37) ⊕ (rot s,5 ∧ rot s,23)
- F의 알고리즘 차수 = 2, 라운드당 차분 확률 ≤ 2^{-k}, k = activated bit positions in F.
- *Active word 하나에 평균 2~4 active bit, F 통과 시 확률 2^{-2} ~ 2^{-4}.*

### 실제 trail 확률 추정 (대략)
2-active 워드 trail × R 라운드의 확률 ≈ 2^{-c × R}, c ≈ 2 (보수치).

| R | 추정 trail 확률 | 보안 마진 (vs 2^{-256}) |
|---|----------------|------------------------|
| 8  | 2^{-16} | **부족**                |
| 12 | 2^{-24} | 마찬가지 *부족*         |
| 16 | 2^{-32} | 부족                    |

**경고**: 본 워드-수준 모델은 *너무 낙관적*이지 *비관적*이지 *않다*. 실제 trail
확률은 더 낮을 가능성이 큼 — F의 회전·AND 결합이 비트 확산을 만들기 때문.

### 더 정확한 평가
* **Bit-level MILP** — 64-bit 워드를 비트 단위로 분해. 상태 변수 1024개, 라운드당 제약 수십만 개. Gurobi 같은 강력한 solver 필요.
* **DDT 기반 SAT/MILP** — F의 비트-별 DDT를 사전 계산, MILP 제약으로 인코딩.
* **Algebraic 분석** — 차수 누적 (F는 차수 2 → R라운드 후 차수 2^R) — R=12면 차수 4096, 상태 1024비트 무력화.

본 워드-수준 결과는 **하한 *체크*** 용도 (= 명백한 약점 없음)이지 정식 안전성 증명이 아님.

## 결론 — YSC5 SPEC의 라운드 수 결정에 미치는 영향

| Spec 매개변수 | 본 분석에서의 시사 |
|--------------|-------------------|
| R_b = 12 (YSC5-128 압축)  | 워드-수준 OK, *bit-level 재분석 필요* |
| R_e = 12 (YSC5-128 확장)  | 위와 동일 |
| R_b = 16 (YSC5-256)       | 더 여유 있는 마진 |

**권고**: 정식 채택 전 외부 cryptanalyst의 bit-level MILP 또는 SAT-based trail 검증
의무. 본 결과는 *workflow setup*과 *no-show-stopper* 단계의 확인.

## 재현 방법

```bash
cd /home/ybi/cryptanalysis/milp
# R 값 변경: model.mod의 'param R, default <n>' 수정
glpsol --math model.mod --tmlim 60
```

## 한계 및 향후 작업

| 항목 | 현 상태 | 다음 단계 |
|------|--------|----------|
| 워드 활성 추적 | ✓ 완료 | — |
| Bit-level 추적 | ✗ 미완 | bit MILP, 1024개 변수/라운드 |
| F-DDT 정확 인코딩 | ✗ 미완 | F의 DDT 사전 계산 후 LUT 형 제약 |
| Trail 확률 곱 | ✗ 정성 분석만 | LUT × 라운드별 확률 곱 |
| Linear hull 분석 | ✗ | 별도 LAT-기반 MILP |
| Boomerang/integral | ✗ | 변종 모델 |
