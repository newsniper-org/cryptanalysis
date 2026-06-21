# FROZEN-PARAMS — YHash 패밀리 동결 파라미터 (단일 권위 출처)

> **이 문서가 권위(authoritative)다.** SPEC-draft, 코드, Isabelle 사이에 불일치가
> 생기면 *이 표*가 기준이며, 셋 모두 이 표에 맞춘다. 값은 **실제 구현 + Isabelle이
> 검증한 값**으로 동결되었다 (아래 §4 "drift 정정 이력" 참조).
>
> 동결 의미: `PARAM_VERSION` 문자열이 같으면 모든 파라미터가 동일하고 digest가
> **bit-exact 재현**된다. 교차구현 KAT은 `yhash/tests/kat.rs`, `ypsilenti/tests/kat.rs`.
> 독립 재구현은 이 표 + KAT으로 정확성을 자체 검증할 수 있다 (downstream R4 수용 기준).

상태: R4 충족 — **단일 권위 파라미터 동결 + 교차구현 KAT 완료.** R1–R3·R5는 별도.

---

## 1. yhash — `PARAM_VERSION = "yhash-params-v1"`

| 항목 | 값 | 출처(코드) |
|------|----|-----------|
| 기반 순열 | YSC4-p (`ysc4::permutation::permute`) — 재사용 | — |
| 상태 폭 | **1024 bit = 16 × u64** | `consts::STATE_WORDS = 16` |
| GF 필드 | GF(2⁶⁴), p(x)=x⁶⁴+x⁴+x³+x+1, reduction `0x1B` *(primitive ✓)* | `ysc4::gf2_64::REDUCTION` |
| σ-층 | branch {0,4,8,12} ← α^{1,3,5,7} | `ysc4::permutation::sigma_layer` |
| F 함수 | s ⊕ (s⋘13 ∧ s⋘37) ⊕ (s⋘5 ∧ s⋘23) | `F_ROT = 13,37,5,23` |
| π 순열 | [7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2] = (5i+7)·mod16 | `ysc4::consts::P` |
| RC | √p 기반 16×u64 NUMS | `ysc4::consts::RC` |
| 블록 크기 | **128 byte (= 상태)** | `consts::BLOCK_BYTES = 128` |
| chaining value / digest | **256 bit (32 byte)** | `consts::CV_BYTES = 32` |
| T_max (leaf arity) | 8 | `consts::T_MAX` |
| internal arity | 2 (binary) | tree.rs |
| MAX_TREE_DEPTH | 32 | `consts::MAX_TREE_DEPTH` |
| R_b (compress, leaf·internal) | **8** | `rounds::LEAF = INTERNAL = 8` |
| R_c (finalize) | **12** | `rounds::FINALIZE = 12` |
| R_mask (mask derive) | **24** | `rounds::MASK_DERIVE = 24` |
| single-leaf 한계 | **1024 byte (8 × 128)** | `T_MAX × BLOCK_BYTES` |
| 도메인 (keyed) | `"YHash-K\0"` (u64 LE) | `domain::KEYED` |
| 도메인 (unkeyed) | `"YHash-U\0"` (u64 LE) | `domain::UNKEYED` |

## 2. ypsilenti — `PARAM_VERSION = "ypsilenti-params-v1"`

| 항목 | 값 | 출처(코드) |
|------|----|-----------|
| 기반 순열 | 자체 8-워드 σ-GLM | `perm.rs` |
| 상태 폭 | 256 bit = 8 × u32 | `consts::STATE_WORDS = 8` |
| GF 필드 | GF(2³²), **p(x)=x³²+x²²+x²+x+1, reduction `0x400007`** *(primitive ✓)* | `gf32::REDUCTION = 0x40_0007` |
| σ-층 | branch {0,4} ← α^{1,3} | `perm::sigma_layer` |
| F 함수 | s ⊕ (s⋘7 ∧ s⋘17) ⊕ (s⋘3 ∧ s⋘13) | `F_ROT = 7,17,3,13` |
| π 순열 | [7,4,1,6,3,0,5,2] = (5i+7)·mod8 | `consts::P_PI` |
| RC | SHA-256 IV 8×u32 NUMS | `consts::RC` |
| 블록 크기 | 32 byte (= 상태) | `consts::BLOCK_BYTES = 32` |
| chaining value / digest | 128 bit (16 byte) | `consts::CV_BYTES = 16` |
| T_max | 8 | `consts::T_MAX` |
| MAX_TREE_DEPTH | 32 | `consts::MAX_TREE_DEPTH` |
| R_b (compress) | 4 | `rounds::LEAF = INTERNAL = 4` |
| R_c (finalize) | 6 | `rounds::FINALIZE = 6` |
| R_mask | 8 | `rounds::MASK_DERIVE = 8` |
| single-leaf 한계 | 256 byte (8 × 32) | `T_MAX × BLOCK_BYTES` |
| 도메인 (keyed) | `"YPSI-K\0\0"` (u64 LE) | `domain::KEYED` |
| 도메인 (unkeyed) | `"YPSI-U\0\0"` (u64 LE) | `domain::UNKEYED` |

## 2.5 yttrium — `PARAM_VERSION = "yttrium-params-v0.2-pre"`

> ⚠ **검증 전 동결(pre-freeze)**: 파라미터를 KAT 재현·교차구현용으로 고정하나 보안검증
> (R1 형식검증·R5 외부분석) *이전* 단계다. 검증이 결함을 드러내면 파라미터 변경 + **버전 bump**.
> 동일 `PARAM_VERSION` ∧ 동일 변형 `(R_b,R_c,R_mask)` ⟹ digest **bit-exact**.

| 항목 | 값 | 출처(코드) |
|------|----|-----------|
| 기반 순열 | 영합(zero-sum) Lai-Massey + ARX 결합기 (Amaryllises 적응) | `lib.rs round()` |
| 상태 폭 | 256 bit = 8 × u32 | `STATE_WORDS = 8` |
| GF 필드 | GF(2³²), reduction `0x400007` *(primitive ✓)* | `REDUCTION = 0x40_0007` |
| 영합 reduction | `S = Σᵢ εᵢ·ROTL₈(xᵢ)`, ε=`[+,−,+,−,+,−,+,−]` (Σε=0) | `EPS_PLUS`, `zerosum_reduce` |
| ARX 결합기 | `yᵢ = ROTR₉(ROTL₈(xᵢ) ⊞ F(S))`, (α,β)=(8,9) | `round()`, `ROT_A/B` |
| σ-층 | all-8 `α^{kᵢ}`, k=`[1,2,3,4,5,6,7,9]` | `SIG_K` |
| F 함수 | s ⊕ (s⋘7∧s⋘17) ⊕ (s⋘3∧s⋘21) ⊕ (s⋘9∧s⋘29) | `F_ROT` |
| π 순열 | [7,4,1,6,3,0,5,2] = (5i+7)·mod8 | `P_PI` |
| RC | **비반복** SHA-256 **K[r]** (r<64), 레인 r mod 8 | `SHA256_K`, `rc()` |
| 블록 / CV | 32 byte / 128 bit | `BLOCK_BYTES`, `CV_BYTES` |
| T_max / MAX_TREE_DEPTH | 8 / 32 | `T_MAX`, `MAX_TREE_DEPTH` |
| **변형 패밀리** | `yttrium-(R_b,R_c,R_mask)`: (10,14,24)·(8,12,24)·(4,6,12)·(4,6,8) | `Rounds::*` |
| 도메인 (keyed/unkeyed) | `"YTTR-K\0\0"` / `"YTTR-U\0\0"` (u64 LE) | `domain::*` |
| KAT | `yttrium/tests/kat.rs` (4변형 × 벡터) | — |
| yttrium-large (u64) | 1024 bit·GF(2⁶⁴) 0x1B·k=[1..15,17]·RC=SHA-512 — **미동결**(round-count §11 open) | `large.rs` (순열 코어) |

(공통 규칙 §3 이월: LE 엔디안·encode 16-byte·키흡수=R_mask·truncation·binary-counter 트리.)

## 3. 공통 규칙 (양 크레이트)

- **엔디안**: 모든 워드 적재/추출은 **little-endian** (`from_le_bytes`/`to_le_bytes`).
- **encode (16 byte)**: `level_byte(1) ‖ level_l(1) ‖ 0(2) ‖ pos(u64 LE,8) ‖ idx(u32 LE,4)`.
  - level_byte: LEAF=0x00, INTERNAL=0x01, ROOT=0xFF. `mask_mid` = encode(·, pos, T_max).
  - root maskMid = encode(ROOT, total_len, shape_hash).
- **키 흡수 (keyed)**: iv_state 최상위 워드에 도메인 태그, 키를 8-byte(yhash)/4-byte(ypsi)
  청크로 capacity 워드에 XOR, 이후 R_mask 라운드 순열 → IV. (`hasher.rs`)
- **truncation**: CV = 상태 앞 4워드(LE). `finalize_u64` = digest 앞 8 byte(LE).
- **트리 형태**: binary-counter (BLAKE3 식). 병렬 빌드는 직렬과 bit-exact (전수 테스트).

## 4. drift 정정 이력 (R4)

감사에서 SPEC↔코드↔Isabelle 불일치가 발견되어 **코드/Isabelle 값으로 동결**하고
SPEC을 정정했다. 코드 값이 권위인 이유: 구현·테스트·벤치·Isabelle 검증이 모두
그 값 위에서 이뤄졌고, 두 GF 다항식 모두 *실제로 primitive함을 계산 검증*했다.

| 파라미터 | SPEC-draft(과거) | 코드 | Isabelle | 동결값 | 비고 |
|---|---|---|---|---|---|
| ypsilenti GF 다항식 | `0x1B` (x⁴+x³+x+1) | `0x400007` | `0x400007` (GF32.thy) | **`0x400007`** | SPEC의 0x1B는 GF(2³²)에서 **primitive 아님**(검증). 코드/Isabelle이 옳음 |
| yhash 상태 폭 | 512 bit (8×u64) | 1024 bit (16×u64) | 1024 (GF64/YSC4-p) | **1024 bit** | yhash는 YSC4-p를 *그대로* 재사용 → 1024. 512는 미실현 초안 |
| yhash 블록 크기 | 32 byte | 128 byte | — | **128 byte** | 상태=블록(Farfalle) |
| yhash single-leaf 한계 | 256 byte | 1024 byte | — | **1024 byte** | 8 × 128 |
| yhash mask 라운드 | 8 | 24 | — | **24** | `MASK_DERIVE` |
| Q1p.thy 주석 다항식 | x³²+x⁴+x³+x+1 | — | (gf_pow는 0x400007) | **x³²+x²²+x²+x+1** | 주석만 stale, 증명은 유효 |

> primitivity 재확인 (carryless mult, α=x의 차수 = 2ⁿ−1):
> ypsilenti `0x400007` → order = 2³²−1 ✓ primitive. yhash `0x1B` → order = 2⁶⁴−1 ✓ primitive.
> SPEC가 잘못 적었던 ypsilenti `0x1B`(32-bit)는 α^(2³²−1) ≠ 1 → **primitive 아님**.

## 5. 미충족 항목 (frozen on-disk 채택 전)

R4(본 문서)는 *재현성*의 전제일 뿐이다. 채택 전 잔여: R2(bit-level 트레일 경계),
R1(PRF 환원 기계검증), R3(constant-time), R5(외부 암호분석). 자세한 현황은
`README.md` "검증 성숙도와 채택 전제조건 (R1–R5)" 참조.
