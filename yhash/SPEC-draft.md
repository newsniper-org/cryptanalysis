# YHash 사양 초안 (v0.0-pre)

> *경고: 본 문서는 **사양 초안**이다. 구현(Rust 코드)은 형식 검증이 통과한 후에만 시작.*
> 참조: `farfalle-tree-design.md` (Farfalle-tree 설계 노트), `ysc5/SPEC.typ` (모드 사양).

## 0. 목적

YHash는 *HashMap·KV store* 등에서 사용할 **DoS-resistant 키 해시 함수**다. YSC5의 *순열·산술
인프라*를 재사용하되, 다음을 위해 *downsize* 한다:

- *작은 키* (보통 < 64 바이트) — 트리 오버헤드 없는 단일-리프 fast-path.
- *짧은 출력* (64/128 비트) — HashMap 슬롯 인덱싱.
- *DoS 저항* (keyed) + *결정적 해시* (unkeyed-random-IV).
- *Farfalle-tree 구조 상속* — 큰 입력 (파일 해싱) 지원, 검증 가능 streaming.

## 1. 설계 매개변수 (확정)

| 매개변수 | 값 | 비고 |
|----------|----|----|
| 기반 순열 P | YSC4-p 변종 (= 본 사양의 P_y) | 라운드 수만 다름 |
| 상태 폭 b | 512 비트 (8 × u64) | YSC5의 절반. SipHash-256과 비교 |
| chaining value 크기 n | 256 비트 | digest 절단 길이; 보안 강도 결정 |
| 라운드 수 (leaf) | 8 | YSC4의 R_b=16의 절반 (소형 입력 가속) |
| 라운드 수 (internal/root) | 12 | tree 내부 노드는 조금 더 |
| Leaf arity T_max | 8 | leaf 내 블록 수 상한 (Wagner 회피) |
| Internal arity | 2 | binary tree |
| 키 크기 (keyed) | 128 비트 (16 바이트) | DoS-resistant 충분 |
| IV 크기 (unkeyed) | 128 비트 | random per-process |
| 출력 크기 | 64 / 128 비트 (선택) | HashMap=64, 일반=128 |

### 단일-리프 fast-path

메시지 길이 ≤ `T_max × block_size` (= 8 × 32 = 256 byte) 인 입력은:
- 트리 없이 *단일 leaf* 처리.
- 출력 = `trunc(P(Acc ⊕ maskMid(LEAF, 0)))`.
- HashMap 키의 대부분(< 256 byte) 이 경로로 흐름.

## 2. encode 함수 (단사)

트리 위치 인코딩:

```
encode : (level, pos, idx_in_node) → mask_seed
```

여기서:
- `level` ∈ {LEAF, INTERNAL_l, ROOT}, `l ∈ ℕ`
- `pos` = 노드의 트리 내 위치 (level별 0-indexed)
- `idx_in_node` = 노드 내부 블록 인덱스 (leaf의 경우 0..T_max-1, internal의 경우 0 또는 1)

구체 인코딩 (16바이트 = 128비트):

```
encode(level, pos, idx) =
    level_byte (1 B)  ||  level_l_byte (1 B)  ||  zero (2 B)  ||
    pos_u64 (8 B LE)  ||  idx_u32 (4 B LE)
```

여기서 `level_byte` ∈ {0x00 (LEAF), 0x01 (INTERNAL), 0xFF (ROOT)},
`level_l_byte` = level (internal의 경우 ≥ 1, leaf/root는 0).

**단사성 증명 의무**: encode가 단사 ⇔ 서로 다른 `(level, pos, idx)`가 서로 다른
16-바이트 시퀀스를 생성. (Y1에서 형식 검증.)

## 3. 마스크 derivation

```
mask(level, pos, idx) = P_y(IV ⊕ encode(level, pos, idx))
```

- `IV`는 keyed-mode에서 128-비트 키, unkeyed-mode에서 fixed NUMS 상수 또는 random session-IV.
- `P_y`는 YSC4-p의 8-라운드 변종 (mask derivation은 일회성, 빠른 라운드 OK).
- *마스크는 모두 사전 계산 가능* (직렬 의존성 없음).

## 4. 노드 함수

### 4.1 Leaf node

위치 `pos`, 블록 `x_0, …, x_{t-1}` (t ≤ T_max, 각 블록 32 바이트 = 256비트):

```
Acc_leaf(pos, [x_0..x_{t-1}]) = ⊕_{j=0..t-1} P_y(x_j ⊕ mask(LEAF, pos, j), R_b)
leafDigest(pos, [x_0..x_{t-1}]) = trunc_n(P_y(Acc_leaf ⊕ maskMid(LEAF, pos), R_c))
```

여기서:
- `R_b` = 8 (leaf 압축 라운드)
- `R_c` = 12 (leaf 종결 라운드)
- `maskMid(LEAF, pos) = mask(LEAF, pos, T_max)` (= 블록 인덱스 T_max에 해당 — 일반 블록 인덱스와 분리)

### 4.2 Internal node

level `l` (≥ 1), 위치 `pos`, 자식 digest `d_L, d_R`:

```
Acc_int(l, pos, d_L, d_R) =
    P_y(d_L ⊕ mask(INTERNAL_l, pos, 0), R_b)  ⊕
    P_y(d_R ⊕ mask(INTERNAL_l, pos, 1), R_b)
intDigest(l, pos, d_L, d_R) = trunc_n(P_y(Acc_int ⊕ maskMid(INTERNAL_l, pos), R_c))
```

### 4.3 Root

루트는 internal node로 처리하되, `maskMid` 인코딩에 *전체 길이*와 *트리 모양*을 주입:

```
rootEncode(level=ROOT, pos=0, idx=0, len, shape) =
    0xFF || ... || len_u64_LE || shape_hash_u32_LE
```

이로써 같은 *substring*을 다른 *길이/모양*으로 압축한 결과는 root에서 충돌 불가.

## 5. 단일-리프 fast-path (소형 입력)

`|msg| ≤ T_max × block_size`:

```
YHash(msg, len) :
    blocks = split(msg, block_size=32)
    pad_last_block(blocks)
    leafD = leafDigest(pos=0, blocks)
    out = trunc_n(P_y(leafD ⊕ rootEncode(LEAF, 0, 0, len, SHAPE_SINGLE_LEAF), R_c))
    return out
```

큰 입력은 표준 Farfalle-tree로 분기.

## 6. 보안 목표

| 항목 | Keyed | Unkeyed |
|------|-------|---------|
| DoS resistance | 128-bit | 128-bit (random IV) |
| Pre-image | 128-bit | 128-bit (n/2) |
| Collision | 64-bit (DoS scale OK) | 128-bit (n/2 = 128) |
| Second pre-image | 128-bit | 128-bit |

n = 256으로 collision 한계 = 2^128 (DoS-scale에서 무관함).

## 7. 검증 의무 (formal verification 우선)

**구현 이전에** 다음을 형식 검증 (Isabelle/HOL):

| 검증 항목 | 책임 theory | 난이도 |
|----------|------------|--------|
| **Y1**. encode 단사성 | `Y1_TreeEncoding.thy` | Easy (combinatorial) |
| **Y2**. XOR accumulator 분해 (left/right 분리 가능) | `Y2_XORDecomposition.thy` | Easy (algebraic) |
| **Y3**. maskMid 도메인 분리 (LEAF/INTERNAL/ROOT) | `Y3_DomainSeparation.thy` | Easy |
| **Y4**. mask uniqueness (distinct position ⇒ distinct mask) | `Y4_MaskUniqueness.thy` | Medium (encode 단사 + P bijection) |
| **Y5**. Collision resistance reduction (random-perm model) | `Y5_CRReduction.thy` | Hard (CryptHOL, sorry 허용) |

**Y1~Y4가 통과**한 후 Rust 구현 진입.
**Y5는 research-grade**, sorry 골격으로 둠.

## 8. RustCrypto API 사양 (구현 후)

YSC5처럼 다음 traits 구현 예정:

- `core::hash::Hasher` (HashMap 자연 사용)
- `digest::{Update, FixedOutput, ExtendableOutput, MacMarker, KeyInit}`
- *no_std*, *musl* 기본

API 형태:

```rust
// HashMap 용
use yhash::YHash64;
use std::hash::{Hash, BuildHasher};

let hasher: YHash64 = YHash64::with_key(&[0x42; 16]);  // keyed (DoS-resistant)
let map: HashMap<String, V, YHash64::Builder> = HashMap::with_hasher(hasher.builder());

// 큰 입력 (파일 해싱)
use yhash::Hasher;
let mut h = Hasher::new();
h.update(file_chunk_1);
h.update(file_chunk_2);
let digest = h.finalize();  // 256-bit
```

## 9. 변경 이력

- v0.0-pre (2026-06-07): 최초 설계 초안. 구현 *이전* 단계 — formal verification 진행 중.

## 10. 구현 가이드라인 (권장사항)

### 10.1 Heap allocation 자제 (no_alloc 기본)

yhash 내부 핫패스에서는 *heap allocation을 가급적 피한다*:
- 출력은 fixed-size `[u8; 32]` (256-bit digest) 또는 `[u8; 16]` (128-bit) 또는 `u64`.
- 입력 streaming은 stack-allocated `[u8; 32]` 블록 버퍼만 사용.
- Single-leaf fast path: 완전히 stack-only (≤ 256 byte 키).
- Tree depth: 1 GB 입력 ≤ 22 레벨 → fixed-size `[NodeState; 32]` (overhead minimal).
- *unbounded XOF output* 같이 alloc이 자연스러운 경우에만 `alloc` feature 사용.

이로써 yhash는:
- `core::hash::Hasher` (alloc 없이) 자연 사용 가능.
- HashMap 핫패스에서 zero-allocation 보장.
- 임베디드/no_std 환경 friendly.

### 10.2 기타 가이드라인

- *Const-time*: 모든 분기 비-입력-의존 (이미 YSC4-p 상속).
- *No data-dependent memory access* (이미 YSC4-p 상속).
- *Zeroize*: 비밀 상태(keyed mode key) `ZeroizeOnDrop`.

## 11. 미해결 사항

- T_max = 8의 Wagner-bound 정량 계산 (별도 분석).
- maskMid 인코딩의 정확한 비트 layout (Y3 검증과 함께 확정).
- AES-NI 활용 여부 (YSC4-p가 SIMD 친화이지만 AES-NI는 부재).
