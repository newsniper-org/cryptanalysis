# MILP 차분 트레일 분석 — YSC4-p / YSC5

> *META.md §7 Q3* — "p_b를 YSC4-p 라운드 8로 줄여도 PRF 환원의 wide-pipe 가정이 유지되나?"
>
> 본 디렉토리는 *워드-수준* 차분 트레일 활성 워드 수의 하한을 GLPK MILP로 추정한다.

## 모델

YSC4-p 한 라운드는 다음으로 구성:
- ι (state[r mod 16] ⊕= RC) — 차분 측면에서 무영향 (단일 워드 affine)
- F-reduce-broadcast — `T = F(⊕ᵢ s_i)`, `s_i ⊕= T`
- σ-층 — 4개 워드에 distinct α-거듭제곱 (선형 bijection, 차분 활성 보존)
- π — 워드 permutation (활성 위치만 이동)

### 워드-활성 변수
- $x^r_i ∈ {0, 1}$: 라운드 $r$ 시작 시 워드 $i$의 차분 활성 여부.

### 라운드 전이 제약
$T^r$ 의 활성 여부는 `⊕ᵢ x^r_i`의 *parity* (확률적 — 보수적으로 1이면 활성).

Broadcast 후:
$y^r_i = x^r_i ⊕ T^r$ (모든 워드 i)

σ는 활성 보존:
$z^r_i = y^r_i$ for σ-적용 branches {0, 4, 8, 12}, $z^r_i = y^r_i$ 그 외 (linear bijection 이라 동일).

π 적용:
$x^{r+1}_i = z^r_{P[i]}$

### MILP 목적함수
최소화: $sum_{r=0}^{R-1} \sum_{i=0}^{15} x^r_i$ (총 활성 워드 수)

제약: 초기에 적어도 한 워드 활성 (`sum_i x^0_i ≥ 1`).

## 실행

```bash
glpsol --math model.mod --output trail-R12.txt --tmlim 60
```

(`--tmlim 60` = 60초 시간 한계.)

## 산출물

| 파일 | 내용 |
|------|------|
| `model.mod` | MathProg MILP 모델 (R 라운드 파라미터화) |
| `trail-R8.txt` | R=8 결과 (있다면) |
| `trail-R12.txt` | R=12 결과 (있다면) |
| `analysis.md` | 결과 해석 + spec round 결정 시사 |

## 한계

본 모델은 **워드-수준** 활성 카운트만 추적. 실제 비트-수준 차분 확률은 더 복잡:
- F 함수의 차분 분포표 (DDT)
- 비-자명한 워드 내부 cancellation
- 다중 라운드 trail interference

따라서 본 분석은 **하한 추정**이지 정확한 trail 확률 계산이 아님. 정식 보안 평가는 별도의
*bit-level* MILP나 SAT 기반 도구가 필요.
