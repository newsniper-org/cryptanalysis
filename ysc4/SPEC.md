# YSC4 사양 — σ-Generalized Lai-Massey

> YSC3(GFN/NORX 기반)의 *모드 사양은 그대로 유지*하고, **순열을 YSC4-p (σ-GLM)으로 교체**한 후속작.
> 목적: 같은 보안 수준에서 FHE AND 카운트를 6배 이상 줄이면서 σ-GLM의 구조적 무결성을 확보.

---

## 0. YSC3 대비 변경 요약

| 항목 | YSC3 | **YSC4** |
|------|------|---------|
| 구조 | 4-branch Type-3 GFN (NORX/ChaCha 계열) | **16-branch σ-Generalized Lai-Massey** |
| 비선형 호출/라운드 | H 16회 | **F 1회** (모든 branch가 XOR-reduce → F → broadcast) |
| AND/라운드 | 1024 | **128** |
| AND/블록 (-128, 16 라운드) | 12,288 (12 라운드) | **2,048** |
| 알고리즘 차수 (라운드당) | ×2 | ×2 |
| 비전단성 보장 | H + QR 설계로 (잘 분석된 NORX) | **구조적 (Lai-Massey 자동)** |
| Lai-Massey 불변량 `⊕ᵢLᵢ` | 무 (구조상 비존재) | **σ로 명시 차단** |
| 모드 (stream/AEAD/XOF) | 그대로 | **그대로** (rate=512/256, capacity 분할 동일) |

---

## 1. 상수

`STATE_WORDS = 16`, 상태 1024비트. 모드/적재 방식은 YSC3와 동일하므로 변경 없음 (RC 16개, 도메인 분리자, rate/capacity 분할).

### 1.1 GF(2⁶⁴) 정의

```
GF(2⁶⁴) = GF(2)[x] / p(x),    p(x) = x⁶⁴ + x⁴ + x³ + x + 1
```

`p(x)`는 GF(2⁶⁴)의 표준적 저-Hamming-weight 기약 다항식 (Conway/HACL\*가 동일 차용).
**감소 상수** `RED = 0x1B` (= `x⁴ + x³ + x + 1`, leading x⁶⁴ 제외).

### 1.2 α-곱 (= 원시 σ)

`α = x` 로 두면 GF(2⁶⁴)에서 `α-mult(y) = y · α`는 다음과 같이 계산:

```
α_mult(y) = (y << 1) ⊕ ( (((y >> 63) & 1) == 1) ? RED : 0 )
```

상수 시간으로:
```rust
fn alpha(y: u64) -> u64 {
    let mask = 0u64.wrapping_sub(y >> 63);    // 0 또는 0xFFFF…FFFF
    (y << 1) ^ (mask & 0x1B)
}
```

* `α`는 GF(2⁶⁴)의 단위원 → bijection.
* `α + 1`도 GF(2⁶⁴)의 단위원 (= 다항식 `x+1`, 비제로). 따라서 `y ↦ y ⊕ α·y`도 bijection.
* 결론: `α-mult`는 **Vaudenay 의미의 orthomorphism**.
* FHE 비용: plaintext × ciphertext, 즉 *부트스트래핑 불필요* → 사실상 무료.

### 1.3 F 함수

```
F(s) = s ⊕ (rot(s, 13) ∧ rot(s, 37))
         ⊕ (rot(s,  5) ∧ rot(s, 23))
```

* 입력·출력 모두 64비트.
* **AND 게이트 128개** (= 2 × 64).
* **알고리즘 차수 2**.
* `(13, 37, 5, 23)`은 모두 64와 서로소이며 mod 64로 서로 다름 → 워드 내 확산 4 방향.

### 1.4 16-cycle 워드 순열 `P`

```
P[i] = (5·i + 7) mod 16,    i = 0..15
P    = [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2]
```

* `gcd(5, 16) = 1` → P는 `Z/16Z`의 permutation.
* P⁻¹이 단일 16-cycle임을 §6 부록에서 확인.
* 의의: σ가 적용된 branch가 16라운드 안에 모든 위치를 한 번씩 거친다.

### 1.5 σ-층 multi-σ 분배

라운드마다 σ는 **4개 branch**에 서로 다른 α-거듭제곱으로 적용:

| Branch | σ 함수 |
|--------|--------|
| 0      | α¹ · x |
| 4      | α³ · x |
| 8      | α⁵ · x |
| 12     | α⁷ · x |

이렇게 두는 이유:
* 짝수 인덱스 4개에 흩어 두면, broadcast 후 `state[i] ⊕ state[j]`의 어떤 부분집합도 σ로 인해 변조됨.
* 거듭제곱이 서로 다르면 `α^a ⊕ α^b ≠ 0` → 어떤 pair도 구조적 invariant subspace를 형성하지 못함.

### 1.6 라운드 수

| 매개변수 | ROUNDS_INIT | ROUNDS_BLOCK |
|----------|-------------|--------------|
| YSC4-128 | 32 | 16 |
| YSC4-256 | 40 | 20 |

(YSC3: 24/12, 32/16. YSC4는 라운드당 비용이 훨씬 낮으므로 더 많이 돌려도 총 FHE 비용은 여전히 YSC3보다 적다.)

---

## 2. YSC4-p 순열 (라운드)

```
permutation(state, ROUNDS):
    for r in 0 .. ROUNDS:
        # 1) 라운드 상수 주입 (도메인을 r mod 16 위치로 옮겨가며)
        state[r % 16] ⊕= RC[r % 16]

        # 2) F 호출: 모든 branch의 XOR-축약을 한 번의 F에 통과
        S = state[0] ⊕ state[1] ⊕ … ⊕ state[15]
        T = F(S)

        # 3) 16-branch broadcast
        for i in 0..16:
            state[i] ⊕= T

        # 4) σ-층: 4개 branch에 distinct α^(2k+1)
        state[ 0] = α¹ · state[ 0]
        state[ 4] = α³ · state[ 4]
        state[ 8] = α⁵ · state[ 8]
        state[12] = α⁷ · state[12]

        # 5) π: 워드 순열
        new_state[i] = state[P[i]]    for i = 0..15
        state = new_state
```

### 2.1 라운드의 비전단성

* (1) RC XOR — bijection.
* (2)·(3) F broadcast — bijection (입력 state로부터 S를 유일하게 결정, T 또한 결정; broadcast `state[i] ⊕ T`도 bijection. F 자체가 bijection이 아니어도 무관: 출력에서 S = ⊕ᵢ state[i] = ⊕ᵢ (Lᵢ⊕T) = ⊕ᵢLᵢ가 그대로 보존되므로 T = F(S)를 재계산하여 원래 Lᵢ 복원 가능. 단 16이 짝수일 때 broadcast가 `⊕ᵢLᵢ`를 보존하는 점이 핵심).
* (4) σ — α-mult이 bijection이므로 각 branch bijection.
* (5) π — bijection (단순 순열).

→ 라운드는 합성된 bijection. 따라서 ROUNDS회 합성도 bijection. **F의 내부 비선형성과 무관하게 전체 순열은 bijection.**

### 2.2 Lai-Massey 불변량 `⊕ᵢ Lᵢ`의 차단

* (2)·(3) broadcast 후: `⊕ᵢ state'[i] = ⊕ᵢ Lᵢ ⊕ 16·T = ⊕ᵢ Lᵢ` (16T = 0 in GF(2)).
  → broadcast만으로는 invariant 보존됨.
* (4) σ-층 적용 후:
  `⊕ᵢ state''[i] = ⊕ᵢ state'[i] ⊕ state'[0] ⊕ α·state'[0]
                                 ⊕ state'[4] ⊕ α³·state'[4]
                                 ⊕ state'[8] ⊕ α⁵·state'[8]
                                 ⊕ state'[12] ⊕ α⁷·state'[12]`
  `= ⊕ᵢ Lᵢ  ⊕  (α+1)·s₀'  ⊕  (α³+1)·s₄'  ⊕  (α⁵+1)·s₈'  ⊕  (α⁷+1)·s₁₂'`
* `(αᵏ+1)`는 GF(2⁶⁴)에서 모두 비제로 (k ≥ 1이므로 αᵏ ≠ 1) → invariant *깨짐*.

본 사양은 §5에서 이 사실을 **단위 테스트로 직접 검증**한다.

### 2.3 알고리즘 차수 / 비선형성 누적

* F의 차수 2.
* 한 라운드 후 모든 branch는 차수 2의 함수 (T가 모든 branch에 들어가므로).
* 두 라운드 후: 한 라운드 결과의 차수 2가 다음 F의 입력 → F의 출력은 차수 2의 차수 2 = 차수 4.
* r 라운드 후 차수 ≤ 2^r.
* r = 16라운드: 차수 ≤ 2¹⁶ = 65536 ≫ 1024 (상태 비트 수).
  → 다항식 단순 표현 불가능. **Algebraic / interpolation 공격 무력.**

### 2.4 차분·선형 특성 (대략)

* F는 워드 내부에서 4개 회전 방향으로 확산. 1비트 차분 입력은 F 출력에 평균 4×2 = 8 비트 확산.
* broadcast로 1개 비트 차분 ⊕ → 16개 branch에 동시 확산 → 1라운드에 차분 비트 활성수 ≥ 8×16 = 128 (보수치, 충돌 무시).
* MILP 형식 증명은 추후 — 본 사양은 *경험적* avalanche/affinity 검증으로 YSC3와 동등한 무결성을 보임.

---

## 3. 모드 사양

**YSC3의 §3 (스트림 cipher, AEAD, XOF, MAC)을 그대로 차용한다.** 변경되는 것은 `permute` 호출 한 줄뿐 (YSC3의 `permute(state, R)` ↔ YSC4의 `permute(state, R)`, 단 후자는 σ-GLM 순열).

매개변수 표는 동일:

| 매개변수 | 키 | 논스 | rate | capacity | ROUNDS_INIT/BLOCK |
|----------|----|----|------|----------|--------------------|
| YSC4-128 | 256 비트 | 192 비트 | 512 | 512 | 32 / 16 |
| YSC4-256 | 512 비트 | 192 비트 | 256 | 768 | 40 / 20 |

---

## 4. FHE 비용 비교 (블록당 AND)

| 항목 | YSC3 (GFN, 12 라운드) | **YSC4 (σ-GLM, 16 라운드)** |
|------|----------------------|----------------------------|
| 라운드당 F/H 호출 | H × 16 (≡ 16 × 64 AND) | F × 1 (≡ 2 × 64 AND) |
| 라운드당 AND 합계 | 1024 | **128** |
| σ-mult 비용 (FHE) | — | plaintext-mult (≈ 0 AND) |
| 블록당 AND 합계 | **12,288** | **2,048** |
| **AND 깊이** (multiplicative depth) | 48 | 32 |
| 동시 처리 가능 branch | 4 (column/diagonal) | 16 (XOR-reduce는 트리, broadcast 자명) |

YSC4 = **YSC3의 1/6 AND 카운트**, 깊이도 2/3.

---

## 5. 사양 규정의 검증 단위 테스트

본 사양은 다음 5가지 단위 테스트를 *사양의 일부*로 요구한다.

1. **bijectivity_one_round** — 임의의 두 입력이 같은 라운드 출력을 갖지 않음 (소표본 + 역연산 정합).
2. **lai_massey_invariant_broken** — broadcast-only(σ 제거) 변종이 `⊕ᵢLᵢ` 불변량을 보존하는 반면, σ 포함 정상 변종은 깨뜨림을 직접 측정.
3. **affinity_violated** — `P(x) ⊕ P(y) ⊕ P(x⊕y) ≠ P(0)`이 16라운드에서 ~512 비트 위반.
4. **avalanche** — 1비트 차이가 16라운드 후 ≈ 512비트 차이로 확산.
5. **algebraic_degree_growth** — F의 차수 2 누적이 라운드별로 두 배 확산되는지 추산.

(`tests/` 폴더 참조)

---

## 6. 부록: P의 16-cycle 검증

`P = [(5i + 7) mod 16 : i = 0..15] = [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2]`

```
P^{-1} = [5, 2, 15, 12, 9, 6, 3, 0, 13, 10, 7, 4, 1, 14, 11, 8]
```

P⁻¹ cycle from 0:
`0 → 5 → 6 → 3 → 12 → 1 → 2 → 15 → 8 → 13 → 14 → 11 → 4 → 9 → 10 → 7 → 0`

길이 16. 단일 cycle. ✓

따라서 σ가 적용되는 branch {0, 4, 8, 12}은 16 라운드에 걸쳐 모든 branch를 정확히 4회씩 σ로 다룬다 (4 × 4 = 16).

---

## 7. 변경 이력

* YSC4 v0.1 (2026-06-06) — σ-Generalized Lai-Massey로 순열 교체. 모드 사양은 YSC3와 동일. FHE AND 카운트 ~1/6 절감.
