# R2 — bit-level 차분 분석 (YHash 패밀리 σ-GLM 순열)

> 기존 `analysis.md`/`model.mod`는 *워드 수준* 활성 카운트(보수적, 라운드당 ≥2 활성
> 워드)만 제공했다. 본 문서는 **비트 수준 정확 분석**으로 라운드 수 정당화를 다룬다.
> 재현: `python3 milp/trail_fweight.py`, `python3 milp/inactive_subspace.py`,
> `python3 milp/trail_smt.py <cipher> <R> <Kmax>` (z3 필요).

## 0. 구조적 관찰 — 비선형은 라운드당 F 1회뿐

σ-GLM 라운드: ι(상수) → `S = ⊕ᵢ stateᵢ` → `t = F(S)` → broadcast `stateᵢ ⊕= t`
→ σ(α-곱, GF-선형) → π(워드 순열). **유일한 비선형은 단어 S에 적용되는 F.**
나머지(XOR-축약·broadcast·σ·π)는 전부 GF(2)-선형이며 차분을 *결정적으로* 전파.

## 1. F의 차분 weight = rank(L_δ) (정확, 휴리스틱 아님)

`F(s) = s ⊕ (s⋘a ∧ s⋘b) ⊕ (s⋘c ∧ s⋘d)`. 입력차분 δ에 대해
```
F(s) ⊕ F(s⊕δ) = const(δ) ⊕ L_δ(s),     L_δ 는 s에 대한 GF(2)-선형 사상
```
(AND항 전개에서 `Δu∧Δv`만 상수, `u∧Δv ⊕ Δu∧v`는 s에 선형.) 따라서 출력차분은
affine coset `const(δ) ⊕ Im(L_δ)` 위에 **균등 분포** →
```
DP_F(δ → out) = 2^(-rank(L_δ))   (out ∈ coset),   weight(δ) = rank(L_δ)
```
이는 *정확값*이다 (보통 MILP의 독립-AND 휴리스틱과 달리).

`trail_fweight.py` (HW≤3 전수 + 200k 랜덤):

| 순열 | 회전 (a,b,c,d) | min nonzero weight | 활성 라운드당 max DP |
|------|---------------|-------------------:|--------------------:|
| ypsilenti (n=32) | (7,17,3,13) | **2** | 2⁻² |
| yhash/ysc4 (n=64) | (13,37,5,23) | **4** | 2⁻⁴ |

관찰: ypsilenti는 17−7 = 13−3 = **10**으로 두 AND항이 같은 변수쌍 {s_{i±10}}을
강화 → 단일비트 δ에서 rank 2. yhash는 37−13=24 ≠ 23−5=18 → 서로 다른 변수 →
rank 4. **ypsilenti F의 회전 선택이 차분 측면에서 yhash보다 약하다**(라운드당 2 vs 4).

## 2. 확률-1 선형 차분의 정확한 임계값 R* (선형대수, SMT 불필요)

비활성 라운드(ΔS=0)는 t=0 → 라운드가 순수 선형 `Lin = π∘σ`. R 라운드 내내 F를
회피하는 차분 집합 `V_R = {v≠0 : XORsum(Linʳ v)=0, r<R}` 는 정확한 선형 부분공간.
`inactive_subspace.py` 결과 — **dim V_R 가 라운드당 정확히 −n 감소**:

| R | ypsi dim V_R | yhash dim V_R |
|---|---:|---:|
| 1 | 224 | 960 |
| 2 | 192 | 896 |
| 4 | **128** | 768 |
| 6 | 64 | 640 |
| 7 | 32 | 576 |
| 8 | **0 (R\*)** | 512 |
| 12 | — | 256 |
| 15 | — | 64 |
| 16 | — | **0 (R\*)** |

→ **R\* = w (상태 워드 수): ypsilenti 8, yhash 16.** 구조적 결과: XORsum=0 제약이
라운드당 n개씩 *독립적으로* 누적되어 w 라운드에 상태 전체(w·n)를 소진. σ-층이 2개
(ypsi)/4개(yhash) 레인만 건드려 확산이 정확히 이 속도다.

## 3. 채택 라운드 수와의 대조 (핵심)

차분은 **마스크 XOR에 투명**하므로(입력차분에서 mask가 상쇄), 단일 블록 keyed 해시는
compress(R_b) → (⊕mm) → finalize(R_c) 를 **연속 R_b+R_c 라운드**로 통과한다.

| | R_b | R_c | R_b+R_c | R\* | 확률-1 차분? | 마진 |
|---|---:|---:|---:|---:|---|---:|
| ypsilenti | 4 | 6 | **10** | 8 | 차단 (10 ≥ 8) | **2** |
| yhash | 8 | 12 | **20** | 16 | 차단 (20 ≥ 16) | **4** |

- **단일 stage는 R\* 미만**: ypsi compress R_b=4 < 8, finalize R_c=6 < 8;
  yhash compress R_b=8 < 16, finalize R_c=12 < 16. → *bare 순열* 차원에선 각 stage가
  확률-1 선형 차분(dim 128/512 — 상태의 절반!)을 가진다.
- **조합(R_b+R_c)은 R\* 초과** → 단일 블록 prob-1 차분은 **차단**. 단 마진이 2/4
  라운드로 얇다.
- mask-derive: ypsi R_mask=8 = R*(임계 정확), yhash R_mask=24 > 16(여유).

## 4. 미해결 — 채택 라운드에서의 best trail DP (SMT timeout)

prob-1은 배제됐지만, R_b+R_c 라운드에서 **최소 활성 라운드 수**(→ best trail DP =
2^(−w_min·활성수))는 미해결이다. z3 모델(`trail_smt.py`)은 bilinear F-차분 제약으로
**R≈6에서 timeout** (ypsi R≤5는 A(R)=0 확인, R=6 undetermined).

함의: w_min이 2(ypsi)/4(yhash)로 작아, DP ≤ 2⁻¹²⁸ 목표를 단일 트레일로 달성하려면
활성 라운드가 ≥64(ypsi)/≥32(yhash) 필요한데, 얇은 마진(2/4)이 그만큼의 활성을
강제하는지 *증명되지 않았다*. **활성 F가 Δt를 전 워드에 broadcast해 차분을 흩뜨리는
효과**가 추가 활성을 강제할 가능성이 높으나(정성적), 정량 경계는 미확보.

→ 이것이 R2의 핵심 잔여 과제이며 **GPU 가속 trail 탐색(threshold/branch-and-bound)
또는 전용 MILP(Gurobi)**, 그리고 **R5 외부 분석**의 우선 대상이다.

## 5. 정직한 R2 판정

| 항목 | 상태 |
|------|------|
| F 차분 weight (정확) | ✅ ypsi 2 / yhash 4 (affine-rank, 휴리스틱 아님) |
| 확률-1 선형 차분 임계값 R\* | ✅ ypsi 8 / yhash 16 (선형대수 정확) |
| 단일 블록 prob-1 차분 배제 | ✅ R_b+R_c ≥ R\* (마진 2/4) |
| 채택 라운드 best trail DP ≤ 목표 | ❌ **미확립** (SMT timeout; GPU/Gurobi/R5 필요) |
| linear hull / boomerang / integral | ❌ 미수행 (아래 §6) |

**결론**: R2는 *부분 충족*. 워드 수준 모델을 비트 수준 정확 분석으로 대체해
(a) 라운드당 정확 DP와 (b) 확산 임계값 R*=w를 확정했고, prob-1 차분이 조합 수준에서
배제됨을 보였다. 그러나 **채택 R_b/R_c에서 trail DP가 보안 목표 이하라는 정량 증거는
아직 없으며**, 마진이 얇아(2/4 라운드) *라운드 수 상향 여지*가 있다. 이는 TODO B1
("라운드 수 정량 근거 미흡")을 정확히 사실로 확인한 것이다.

## 6. 범위 밖 (후속)

- **Linear trail / hull**: F의 선형 근사 상관도는 차분과 쌍대(transpose) 구조 →
  같은 R*=w 임계가 적용될 것으로 예상되나 별도 계산 필요(correlation weight).
- **Boomerang / integral / algebraic degree**: F는 차수 2 → r 라운드 후 대수 차수
  ≤ min(2ʳ, n−1). ypsi n=32는 ⌈log₂31⌉=5, yhash n=64는 6 라운드면 최대차수 도달
  가능(integral distinguisher 상한의 단서). 정밀 분석 미수행.
- **GPU 실측**: §4의 best-trail 탐색 + DP 실측(rank 예측 2^-weight 검증)은 GPU에
  적합(RTX 5050 가용). T4 증거 강화(pre-R5)로 별도 모듈 권장.
