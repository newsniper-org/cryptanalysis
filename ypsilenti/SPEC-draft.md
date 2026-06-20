# ypsilenti 사양 초안 (v0.0-pre)

> *경고*: 구현은 형식 검증 통과 후 시작. 본 문서는 *설계*.

## 0. 목적

ypsilenti는 YHash의 *downsized* 변종. 같은 σ-GLM + Farfalle-tree 구조를 유지하되:
- 상태: **8 × u32 = 256 비트** (YHash의 1/4)
- α-mult: **GF(2³²)** (YHash의 GF(2⁶⁴) 대신)
- 라운드: R_b=4 / R_c=6 (절반 감축)
- 목표 보안: **64-bit DoS** (HashMap에 충분, SipHash 수준)

## 1. 매개변수 (확정)

| 항목 | 값 | 비고 |
|------|----|----|
| 상태 워드 수 | 8 | YHash 16의 절반 |
| 워드 비트폭 | 32 | YHash u64의 절반 |
| 상태 크기 | 256 비트 (32 byte) | YHash 1024 비트의 1/4 |
| Block 크기 | 256 비트 (= state size) | Farfalle 표준 |
| Chaining value | 128 비트 (16 byte) | YHash 256의 절반 |
| 라운드 R_b (compress) | 4 | |
| 라운드 R_c (finalize) | 6 | |
| 라운드 R_mask (mask derive) | 8 | |
| T_max (leaf 블록 수) | 8 | 동일 |
| Single-leaf 한계 | 256 byte | 8 × 32 |
| 키 크기 (keyed) | 128 비트 | DoS 충분 |

## 2. GF(2³²) 정의

> **동결 정정 (R4)**: 초기 초안은 yhash의 GF(2⁶⁴) 다항식 모양(x⁴+x³+x+1, `0x1B`)을
> 그대로 복사했으나, **`0x1B`는 GF(2³²)에서 primitive가 아니다** (α^(2³²−1) ≠ 1로 계산
> 검증됨). 구현·Isabelle(GF32.thy)은 처음부터 **primitive한 `0x400007`**을 사용한다.
> 아래는 권위값(`FROZEN-PARAMS.md` §2)으로 정정됨.

```
GF(2³²) = GF(2)[x] / p(x),  p(x) = x³² + x²² + x² + x + 1
```

**감소 상수**: `0x400007` = x²² + x² + x + 1 (low part).

α-mult:
```rust
fn alpha(y: u32) -> u32 {
    let mask = 0u32.wrapping_sub(y >> 31);
    (y << 1) ^ (mask & 0x40_0007)
}
```

**Q1' (완료)**: 이 다항식의 α = x가 GF(2³²)*의 primitive (차수 = 2³²−1 =
4,294,967,295) 임을 Isabelle `Q1p_Primitivity.thy`가 `by eval`로 형식 검증
(5개 소인수 {3,5,17,257,65537}에 대한 certificate).

## 3. F 함수 (u32 회전 상수 새로 선정)

```
F(s) = s ⊕ (rot(s, 7) ∧ rot(s, 17)) ⊕ (rot(s, 3) ∧ rot(s, 13))
```

- 회전 (7, 17, 3, 13): 모두 32와 서로소, mod 32 distinct, "well-spread"
- AND 게이트 64 (= 2 × 32)
- 차수 2

## 4. 8-cycle 워드 순열 π

```
P[i] = (5·i + 7) mod 8
P    = [7, 4, 1, 6, 3, 0, 5, 2]
```

- gcd(5, 8) = 1 → permutation
- P⁻¹의 cycle: 0 → 5 → 6 → 3 → 4 → 1 → 2 → 7 → 0 (length 8, 단일 cycle)

## 5. σ-층 (2개 branch, distinct α-거듭제곱)

| Branch | σ 함수 |
|--------|--------|
| 0      | α¹ · x |
| 4      | α³ · x |

YHash의 4-branch σ에서 절반. 비대칭 유지 + 비용 절반.

## 6. 라운드 함수

```
for r in 0..ROUNDS:
    state[r mod 8] ⊕= RC[r mod 8]      # 라운드 상수 주입
    S = ⊕ᵢ state[i]                     # XOR-축약
    T = F(S)
    for i in 0..8: state[i] ⊕= T       # broadcast
    state[0] = α¹ · state[0]           # σ
    state[4] = α³ · state[4]
    new_state[i] = state[P[i]]         # π
    state = new_state
```

라운드 상수 RC: SHA-256 IV의 32-bit half words를 차용 (NUMS).

## 7. 검증 의무 (구현 전)

| # | Theory | 의무 |
|---|--------|------|
| Q1' | GF(2³²)_primitivity | α는 GF(2³²)*의 primitive |
| Q2' | u32_orders | k ∈ {1..8}에 대해 gcd(k, 2³²−1) + ord(α^k) ≥ 2¹⁶ |
| Y1' | encode_injective | (level, pos, idx) 단사 (= YHash와 동일 구조) |
| Y2' | xor_decomposition | acc(xs @ ys) = acc xs ⊕ acc ys (= YHash와 동일) |
| Y3' | domain_separation | LEAF/INTERNAL/ROOT 충돌 불가 (= YHash와 동일) |
| Y4' | mask_uniqueness | distinct (lt, pos, idx) ⇒ distinct mask (locale) |

## 8. 구현 가이드 (post-verification)

- `no_std` + musl 기본
- Stack-only (YHash와 동일)
- u32 native — x86_64에서 native 인스트럭션
- 라운드 수 적어 instruction count도 적음
- 예상 per-hash (4-byte key): **400-600 ns** (YHash의 ~4-6×)

## 9. 변경 이력

- v0.0-pre (2026-06-07): 초안. 형식 검증 진행 중.
