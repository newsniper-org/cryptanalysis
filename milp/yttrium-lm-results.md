# yttrium-LM 실측 결과 — 영합 Lai-Massey + all-8 orthomorphism

> 가역화 갈래 확정 후(Farfalle 유지=가역 필수, Feistel 배제, F 비가역 재사용) 설계·검증.
> 도구: `yttrium_lm_invert.py`(가역), `yttrium_lm_subspace.py`(정확-LA), `yttrium_lm_diff.cu`(GPU best-DP).
> 설계 탐색은 워크플로(6 설계렌즈 + 18 적대검증 + 종합)로, **최종 GPU/LA 실측은 오케스트레이터 직접 수행**.

## 1. 라운드 (권고 = Proposal 1)

```
ε  = [+1,−1,+1,−1,+1,−1,+1,−1]   (Σε=0)
x'ᵢ = ROTL_8(xᵢ)
S   = Σᵢ εᵢ·x'ᵢ  (mod 2³²)            ← 영합 reduction (가역의 토대)
t   = F(S)                             F = AND-3term (고정·비가역 무방)
yᵢ  = ROTR_9(x'ᵢ ⊞ t)
yᵢ ← α^{kᵢ}·yᵢ   k=[1,2,3,5,7,11,13,17]  (GF(2³²) red 0x400007) ← all-8 σ
new = π(y),  P=[7,4,1,6,3,0,5,2]
```

## 2. 가역성 (`yttrium_lm_invert.py`) — 해결 ✓

영합 항등식 `Σεᵢ·y'ᵢ = S ⊞ (Σεᵢ)·t = S` (Σε=0) → 출력만으로 S 복원 → 라운드 전단사,
**F·결합기의 가역성과 무관**. 2³² 덧셈형 Horst 비치환(`yttrium-invertibility.md`)을 우회.

| 검사 | 결과 |
|---|---|
| n=3·w=8 = 2²⁴ 전수 전단사 | image **16777216/16777216** = bij ✓ |
| n=4·w=4 = 2¹⁶ 전수 전단사 | 65536/65536 = bij ✓ |
| roundtrip inv∘fwd (6라운드, RC 포함) | ✓ |
| **control: Σε≠0 (all +1)** | **49152/65536 = 비전단사 ✓** (영합 load-bearing) |
| **control: 비가역 garbage-F** | 65536/65536 = bij ✓ (F 가역성 무관) |
| α^k (k∈{1,2,3,5,7,11,13,17}) | perm ✓ · **XOR-orth ✓** · ADD-orth ✗ · α⁻ᵏ∘αᵏ=id ✓ |

가산-orthomorphism이 아니어도 충분: 가역은 영합이 담당, σ는 치환이면 됨(α^k는 치환).

## 3. inactive-subspace (`yttrium_lm_subspace.py`) — 정확-LA 두 척도

| 척도 | 권고(all-8) | baseline σ{0,4} | 비고 |
|---|---|---|---|
| (A) prob-1 MSB (정확) | **R\*=2** | R\*=2 | **σ 커버리지 무관**(framing 주역). all/even/{0,4}/empty 전부 R\*=2 |
| (B) GF(2)-선형 (정확) | R\*=**9** | R\*=8 | all-8이 *못 낮춤*(오히려 +1) |
| n=64(yhash-large) prob-1 | R\*=2 | — | 예비 |

**정직:** 두 정확 척도 모두 σ 커버리지를 변별하지 못한다. (B) R\*=9는 carry를 못 보는
GF(2)-선형 모델의 과대평가 artifact이며, 그 차분의 실제 가산 통과확률 ≈0.5(prob-1 아님).
변별은 §4의 best-DP에서만 나온다 — 이게 핵심 교훈.

## 4. best-DP σ-커버리지 비교 (`yttrium_lm_diff.cu`, GPU N=2³⁰) — 결정적

영합 같은-부호 **MSB-쌍 차분**(정확-LA가 못 본 고확률 차분)의 worst-δ best-DP @ (α,β)=(8,9):

| σ 커버리지 | R2 | R3 | R4 |
|---|---|---|---|
| **all-8 k=1,2,3,5,7,11,13,17 (권고)** | **2⁻¹⁵·⁴** | **2⁻²³·¹** | 2⁻²³·¹ |
| even-4 {0,2,4,6} | 2⁻²·⁰ | 2⁻¹⁰·⁶ | 2⁻²³·¹ |
| σ{0,4} (현행 ypsilenti식) | 2⁻²·⁰ | 2⁻²·⁶ | **2⁻³·¹** |
| empty (framing only) | 2⁻²·⁰ | 2⁻²·⁰ | 2⁻²·⁰ |

부분 σ는 σ 미접촉 레인으로 MSB-쌍을 R≈4까지 통과(현행 σ{0,4}는 R4=2⁻³·¹로 심각).
**all-8 σ만 R=2서 noise floor로 붕괴** → all-8은 선택이 아니라 **필수**.

all-8 σ (α,β) sweep: (8,9)=2⁻¹⁵·⁴, (8,3)=2⁻¹⁶·⁵, (9,10)=2⁻¹⁷·¹ (R3 floor 동일, 차이<2bit).

## 5. 한계 (정직)

- best-DP는 δ-부분집합 경험적 상한(증명 아님). floor~2⁻²⁵(N=2³⁰), worst-δ 최대화로 겉보기 ~2⁻²³.
- **절대 trail 경계 미확립**: full-width best-DP·rotational-XOR(부호가산 대칭)·boomerang·integral 미측정 → 라운드수 잠정.
- all-8 비용: Σk=59 α-step/round. distinct power 집합 최적화는 미탐(성능 튜닝).
- MSB-쌍은 δ 한 부류; all-8이 전체 δ-공간을 닫는지는 전수 아님.
- mixed-algebra(영합 ⊞ ↔ GF α^k) 정밀 분석 별도(SPEC §10-D).

## 6. 재현

```bash
cd milp
python3 yttrium_lm_invert.py        # 가역 + orthomorphism (GPU 불필요)
python3 yttrium_lm_subspace.py      # 정확-LA 두 척도 (GPU 불필요)
nvcc --std=c++14 -O3 -o yttrium_lm_diff yttrium_lm_diff.cu && ./yttrium_lm_diff   # σ-커버리지 best-DP
```
