//! # yttrium — Amaryllises 기반 ARX 재설계 (YHash 패밀리) · 레퍼런스 구현
//!
//! 설계 근거: Grassi, "Generalizations of the Lai-Massey Scheme: the Blooming of
//! Amaryllises" (IACR ePrint 2022/1245). Amaryllises(비선형 Lai-Massey)를 체 곱셈 대신
//! **ARX(모듈러 가산)** 으로 적응하고, 가역성은 **영합(zero-sum) reduction**으로, σ-GLM의
//! 확률-1 약점은 **all-8 GF(2³²) α^k orthomorphism**으로 닫는다.
//!
//! - 상태: 8 × u32 = 256 bit. digest(CV): 128 bit.
//! - 라운드: `Rounds { r_b, r_c, r_mask }` — **변형 패밀리** `yttrium-(R_b,R_c,R_mask)`.
//! - 모드: Farfalle-tree (leaf 8-block XOR-누산 → internal 2-block → root), positional mask.
//!
//! ⚠ **v0.2-pre 레퍼런스**: SPEC-draft.md 기반. 형식검증(R1)·KAT 동결(R4)·외부 암호분석(R5)
//! 이전 단계 — 운영 사용 금지. 라운드수는 외삽 기반(`milp/yttrium-round-count.md`).
//!
//! 보안 주장(정직, 외삽): unkeyed 충돌저항은 acc-충돌(=1/best-DP(R_b))이 결정 →
//! `yttrium-(8,12,24)`≈birthday, `(10,14,24)` 마진. `(4,6,*)`는 **keyed 전용**(unkeyed 비저항).

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![forbid(unsafe_code)]

#[cfg(feature = "alloc")]
extern crate alloc;

/// yttrium-large (u64, 1024-bit) — 순열 코어 + 모드. SPEC §1.2.
pub mod large;

/// Level-B SIMD (inter-block batch). `feature = "simd"`.
#[cfg(feature = "simd")]
pub mod perm_simd;

// ===================================================================================
// §1. 파라미터 / 변형 패밀리
// ===================================================================================

/// 동결 파라미터 집합 버전. 이 문자열 ∧ 변형 `(R_b,R_c,R_mask)`가 같으면 digest가
/// **bit-exact** 재현된다(F·σ·ε·π·GF·RC·encode·도메인·엔디안 전부 고정). 권위 출처:
/// 저장소 루트 `FROZEN-PARAMS.md` §2.5. 교차구현 KAT: `tests/kat.rs`.
///
/// ⚠ `-pre` = **검증 전 동결**(R1 형식검증·R5 외부분석 이전). 검증이 결함을 드러내면
/// 파라미터 변경 + **버전 bump**. 운영 사용 금지.
pub const PARAM_VERSION: &str = "yttrium-params-v0.2-pre";

pub const STATE_WORDS: usize = 8;
pub const STATE_BYTES: usize = STATE_WORDS * 4; // 32
pub const BLOCK_BYTES: usize = STATE_BYTES;
pub const CV_BYTES: usize = 16; // 128-bit digest
pub const T_MAX: usize = 8;
pub const MAX_TREE_DEPTH: usize = 32;

pub type State = [u32; STATE_WORDS];
pub type Digest = [u8; CV_BYTES];

/// 변형 패밀리 라운드수. 이름 규약: `yttrium-(R_b, R_c, R_mask)`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rounds {
    /// 블록 압축 (leaf/internal). unkeyed acc-충돌이 R_b 단독 결정.
    pub r_b: usize,
    /// finalize. digest 충돌/2nd-preimage은 R_b+R_c 합성.
    pub r_c: usize,
    /// mask 유도 + keyed 키 흡수.
    pub r_mask: usize,
}

impl Rounds {
    /// 보수 unkeyed 크립토 (고마진): acc≳2⁷⁷, 합성 2nd-pre≳2¹²⁸ (외삽).
    pub const V10_14_24: Rounds = Rounds { r_b: 10, r_c: 14, r_mask: 24 };
    /// 기본 unkeyed 크립토 (yhash-class): acc≳2⁶¹ (≈birthday, 외삽).
    pub const V8_12_24: Rounds = Rounds { r_b: 8, r_c: 12, r_mask: 24 };
    /// keyed-lite (키스케줄 강화 R_mask=12): unkeyed 비저항(acc≳2³¹) — keyed 전용.
    pub const V4_6_12: Rounds = Rounds { r_b: 4, r_c: 6, r_mask: 12 };
    /// lite / 비적대 (ypsilenti-호환): unkeyed 비저항.
    pub const V4_6_8: Rounds = Rounds { r_b: 4, r_c: 6, r_mask: 8 };
}

/// 워드 순열 π: P[i] = (5i + 7) mod 8. 단일 8-cycle.
const P_PI: [usize; STATE_WORDS] = [7, 4, 1, 6, 3, 0, 5, 2];

/// 영합(zero-sum) reduction 부호 ε = [+,−,+,−,+,−,+,−] (Σε = 0; 가역의 토대).
const EPS_PLUS: [bool; STATE_WORDS] = [true, false, true, false, true, false, true, false];

/// σ orthomorphism 거듭제곱 k = [1,2,3,4,5,6,7,9] (all-8 distinct; Σ=37 α-step, 튜닝).
const SIG_K: [u32; STATE_WORDS] = [1, 2, 3, 4, 5, 6, 7, 9];

/// 결합기 회전 (α,β) = (8, 9).
const ROT_A: u32 = 8;
const ROT_B: u32 = 9;

/// F 회전 오프셋: (7,17),(3,21),(9,29) — per-active weight 6.
const F_ROT: [(u32, u32); 3] = [(7, 17), (3, 21), (9, 29)];

/// RC: 비반복 SHA-256 라운드상수 K[r] (r<64). 주입 레인 = r mod 8.
const SHA256_K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

#[inline(always)]
fn rc(r: usize) -> u32 {
    if r < 64 {
        SHA256_K[r]
    } else {
        SHA256_K[r % 64] ^ (r as u32)
    }
}

pub mod domain {
    pub const KEYED: u64 = u64::from_le_bytes(*b"YTTR-K\0\0");
    pub const UNKEYED: u64 = u64::from_le_bytes(*b"YTTR-U\0\0");
}

// ===================================================================================
// §2. GF(2³²) α-곱 (σ-층 orthomorphism)
// ===================================================================================

/// Reduction: x³² + x²² + x² + x + 1 → low = 0x400007 (primitive, order 2³²−1).
pub const REDUCTION: u32 = 0x0040_0007;

#[inline(always)]
pub fn alpha(y: u32) -> u32 {
    let mask = 0u32.wrapping_sub(y >> 31);
    (y << 1) ^ (mask & REDUCTION)
}

#[inline(always)]
fn alpha_pow(mut y: u32, k: u32) -> u32 {
    for _ in 0..k {
        y = alpha(y);
    }
    y
}

/// α⁻¹ (red bit0 = 1): low bit가 0이면 단순 >>1, 1이면 reduction 되돌림.
#[inline(always)]
pub fn alpha_inv(v: u32) -> u32 {
    if v & 1 != 0 {
        ((v ^ REDUCTION) >> 1) | 0x8000_0000
    } else {
        v >> 1
    }
}

#[inline(always)]
fn alpha_pow_inv(mut v: u32, k: u32) -> u32 {
    for _ in 0..k {
        v = alpha_inv(v);
    }
    v
}

// ===================================================================================
// §3. F 함수 (비선형, no S-box; F 비가역 무방 — Lai-Massey는 역산 안 함)
// ===================================================================================

#[inline(always)]
pub fn f(s: u32) -> u32 {
    let mut acc = s;
    for &(a, b) in F_ROT.iter() {
        acc ^= s.rotate_left(a) & s.rotate_left(b);
    }
    acc
}

// ===================================================================================
// §4. 라운드 함수 (영합 Lai-Massey + ARX 결합기 + all-8 σ + π)
// ===================================================================================

#[inline(always)]
fn zerosum_reduce(xp: &State) -> u32 {
    let mut s = 0u32;
    for i in 0..STATE_WORDS {
        if EPS_PLUS[i] {
            s = s.wrapping_add(xp[i]);
        } else {
            s = s.wrapping_sub(xp[i]);
        }
    }
    s
}

#[inline(always)]
fn round(state: &mut State, r: usize) {
    state[r % STATE_WORDS] ^= rc(r); // ι
    let mut xp = [0u32; STATE_WORDS]; // x'_i = ROTL_α(x_i)
    for i in 0..STATE_WORDS {
        xp[i] = state[i].rotate_left(ROT_A);
    }
    let s = zerosum_reduce(&xp); // S = Σ ε_i x'_i
    let t = f(s);
    for i in 0..STATE_WORDS {
        // y_i = ROTR_β(x'_i ⊞ t)
        let v = xp[i].wrapping_add(t).rotate_right(ROT_B);
        state[i] = alpha_pow(v, SIG_K[i]); // σ: α^{k_i}
    }
    let mut new = [0u32; STATE_WORDS]; // π
    for i in 0..STATE_WORDS {
        new[i] = state[P_PI[i]];
    }
    *state = new;
}

/// 역 라운드 (가역성 검증/참고용; 해시 모드엔 불필요).
#[inline]
fn round_inv(state: &mut State, r: usize) {
    let mut y = [0u32; STATE_WORDS]; // π⁻¹
    for i in 0..STATE_WORDS {
        y[P_PI[i]] = state[i];
    }
    let mut v = [0u32; STATE_WORDS]; // σ⁻¹ 후 ROTL_β → v_i = x'_i ⊞ t
    for i in 0..STATE_WORDS {
        v[i] = alpha_pow_inv(y[i], SIG_K[i]).rotate_left(ROT_B);
    }
    let s = zerosum_reduce(&v); // 영합 보존: Σ ε_i v_i = S
    let t = f(s);
    for i in 0..STATE_WORDS {
        // x_i = ROTR_α(v_i ⊟ t)
        state[i] = v[i].wrapping_sub(t).rotate_right(ROT_A);
    }
    state[r % STATE_WORDS] ^= rc(r);
}

#[inline]
pub fn permute(state: &mut State, rounds: usize) {
    for r in 0..rounds {
        round(state, r);
    }
}

#[inline]
pub fn permute_inv(state: &mut State, rounds: usize) {
    for r in (0..rounds).rev() {
        round_inv(state, r);
    }
}

// ===================================================================================
// §5. 모드 빌딩 블록 (Farfalle-tree; ypsilenti 구조 이월)
// ===================================================================================

#[inline]
fn derive_mask(seed: &[u8; 16], iv: &State, r_mask: usize) -> State {
    let mut s = *iv;
    for i in 0..4 {
        s[i] ^= u32::from_le_bytes(seed[i * 4..(i + 1) * 4].try_into().unwrap());
    }
    permute(&mut s, r_mask);
    s
}

#[inline]
fn compress_block(block: &[u8; BLOCK_BYTES], mask: &State, r_b: usize) -> State {
    let mut s = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let w = u32::from_le_bytes(block[i * 4..(i + 1) * 4].try_into().unwrap());
        s[i] = w ^ mask[i];
    }
    permute(&mut s, r_b);
    s
}

#[inline]
fn finalize_state(state: &State, mask_mid: &State, r_c: usize) -> State {
    let mut s = *state;
    for i in 0..STATE_WORDS {
        s[i] ^= mask_mid[i];
    }
    permute(&mut s, r_c);
    s
}

#[inline]
fn truncate_cv(state: &State) -> Digest {
    let mut cv = [0u8; CV_BYTES];
    for i in 0..4 {
        cv[i * 4..(i + 1) * 4].copy_from_slice(&state[i].to_le_bytes());
    }
    cv
}

#[inline]
fn cv_to_state(cv: &Digest) -> State {
    let mut s = [0u32; STATE_WORDS];
    for i in 0..4 {
        s[i] = u32::from_le_bytes(cv[i * 4..(i + 1) * 4].try_into().unwrap());
    }
    s
}

// ----- 위치 인코딩 (Y1: 단사) -----

#[derive(Clone, Copy)]
enum LevelTag {
    Leaf,
    Internal(u32),
    Root,
}

impl LevelTag {
    #[inline]
    fn byte(self) -> u8 {
        match self {
            LevelTag::Leaf => 0x00,
            LevelTag::Internal(_) => 0x01,
            LevelTag::Root => 0xFF,
        }
    }
    #[inline]
    fn level(self) -> u32 {
        match self {
            LevelTag::Internal(l) => l,
            _ => 0,
        }
    }
}

#[inline]
fn encode(level: LevelTag, pos: u64, idx: u32) -> [u8; 16] {
    let mut out = [0u8; 16];
    out[0] = level.byte();
    out[1] = level.level() as u8;
    out[4..12].copy_from_slice(&pos.to_le_bytes());
    out[12..16].copy_from_slice(&idx.to_le_bytes());
    out
}

#[inline]
fn pad_partial_block(input: &[u8]) -> [u8; BLOCK_BYTES] {
    debug_assert!(input.len() < BLOCK_BYTES);
    let mut block = [0u8; BLOCK_BYTES];
    block[..input.len()].copy_from_slice(input);
    block[input.len()] = 0x01;
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

#[inline]
fn pad_cv_to_block(cv: &Digest) -> [u8; BLOCK_BYTES] {
    let mut block = [0u8; BLOCK_BYTES];
    block[..16].copy_from_slice(cv);
    block[16] = 0x01;
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

fn split_input_into_blocks(input: &[u8]) -> ([[u8; BLOCK_BYTES]; T_MAX], usize) {
    let mut blocks = [[0u8; BLOCK_BYTES]; T_MAX];
    let full = input.len() / BLOCK_BYTES;
    let rem = input.len() % BLOCK_BYTES;
    debug_assert!(full <= T_MAX);
    for j in 0..full {
        blocks[j].copy_from_slice(&input[j * BLOCK_BYTES..(j + 1) * BLOCK_BYTES]);
    }
    let n = if rem > 0 || full == 0 {
        debug_assert!(full < T_MAX);
        blocks[full] = pad_partial_block(&input[full * BLOCK_BYTES..]);
        full + 1
    } else {
        full
    };
    (blocks, n)
}

fn compute_leaf(blocks: &[[u8; BLOCK_BYTES]], n: usize, pos: u64, iv: &State, rd: &Rounds) -> Digest {
    debug_assert!(n <= T_MAX);
    // Level-B SIMD: n개 블록 mask-derive+compress 배치 (feature="simd"). scalar와 bit-exact.
    #[cfg(feature = "simd")]
    let acc = {
        let mut seeds = [[0u8; 16]; T_MAX];
        for (j, s) in seeds.iter_mut().enumerate().take(n) {
            *s = encode(LevelTag::Leaf, pos, j as u32);
        }
        perm_simd::compute_leaf_acc(blocks, &seeds, n, iv, rd.r_mask, rd.r_b)
    };
    #[cfg(not(feature = "simd"))]
    let acc = {
        let mut acc = [0u32; STATE_WORDS];
        for j in 0..n {
            let mask = derive_mask(&encode(LevelTag::Leaf, pos, j as u32), iv, rd.r_mask);
            let y = compress_block(&blocks[j], &mask, rd.r_b);
            for i in 0..STATE_WORDS {
                acc[i] ^= y[i];
            }
        }
        acc
    };
    let mm = derive_mask(&encode(LevelTag::Leaf, pos, T_MAX as u32), iv, rd.r_mask);
    truncate_cv(&finalize_state(&acc, &mm, rd.r_c))
}

/// 입력을 leaf(=T_MAX*BLOCK byte)들로 쪼개 각 leaf digest를 순서대로 `tree`에 push.
/// `compute_leaf`가 leaf 내부 8블록을 SIMD 배치(feature="simd"). 스트리밍 finalize와 bit-exact.
/// (no_std: Vec 불요. cross-leaf/internal 레벨배치는 §full-accel 검토 — leaf-only 배치는 internal
///  노드 지배+transpose 오버헤드로 순효과 마이너스라 미채택.)
fn push_leaf_digests(data: &[u8], iv: &State, rd: &Rounds, tree: &mut TreeBuilder) {
    let leaf_bytes = T_MAX * BLOCK_BYTES;
    let nleaves = data.len().div_ceil(leaf_bytes);
    for p in 0..nleaves {
        let lo = p * leaf_bytes;
        let hi = core::cmp::min(lo + leaf_bytes, data.len());
        let (blocks, n) = split_input_into_blocks(&data[lo..hi]);
        tree.push_leaf(compute_leaf(&blocks, n, p as u64, iv, rd), iv, rd);
    }
}

fn compute_internal(level: u32, pos: u64, d_l: &Digest, d_r: &Digest, iv: &State, rd: &Rounds) -> Digest {
    let bl = pad_cv_to_block(d_l);
    let br = pad_cv_to_block(d_r);
    let ml = derive_mask(&encode(LevelTag::Internal(level), pos, 0), iv, rd.r_mask);
    let mr = derive_mask(&encode(LevelTag::Internal(level), pos, 1), iv, rd.r_mask);
    let yl = compress_block(&bl, &ml, rd.r_b);
    let yr = compress_block(&br, &mr, rd.r_b);
    let mut acc = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        acc[i] = yl[i] ^ yr[i];
    }
    let mm = derive_mask(&encode(LevelTag::Internal(level), pos, T_MAX as u32), iv, rd.r_mask);
    truncate_cv(&finalize_state(&acc, &mm, rd.r_c))
}

fn compute_root_from_acc(acc: &State, total_len: u64, shape_hash: u32, iv: &State, rd: &Rounds) -> Digest {
    let mm = derive_mask(&encode(LevelTag::Root, total_len, shape_hash), iv, rd.r_mask);
    truncate_cv(&finalize_state(acc, &mm, rd.r_c))
}

// ----- 이진 트리 빌더 (BLAKE3식 counter) -----

#[derive(Clone)]
struct TreeBuilder {
    pending: [Option<Digest>; MAX_TREE_DEPTH],
    next_leaf_pos: u64,
}

impl TreeBuilder {
    fn new() -> Self {
        Self { pending: [None; MAX_TREE_DEPTH], next_leaf_pos: 0 }
    }
    fn push_leaf(&mut self, leaf_digest: Digest, iv: &State, rd: &Rounds) {
        let mut digest = leaf_digest;
        let mut level: u32 = 0;
        loop {
            let li = level as usize;
            debug_assert!(li < MAX_TREE_DEPTH);
            match self.pending[li].take() {
                None => {
                    self.pending[li] = Some(digest);
                    break;
                }
                Some(left) => {
                    let pos = self.next_leaf_pos >> (level + 1);
                    level += 1;
                    digest = compute_internal(level, pos, &left, &digest, iv, rd);
                }
            }
        }
        self.next_leaf_pos += 1;
    }
    fn finalize(mut self, total_len: u64, iv: &State, rd: &Rounds) -> Digest {
        let mut current: Option<Digest> = None;
        for level in 0..MAX_TREE_DEPTH {
            match (self.pending[level].take(), current) {
                (None, c) => current = c,
                (Some(p), None) => current = Some(p),
                (Some(p), Some(c)) => {
                    let pos = self.next_leaf_pos >> (level as u32 + 1);
                    current = Some(compute_internal(level as u32 + 1, pos, &p, &c, iv, rd));
                }
            }
        }
        match current {
            Some(d) => compute_root_from_acc(&cv_to_state(&d), total_len, 1, iv, rd),
            None => compute_root_from_acc(&[0u32; STATE_WORDS], 0, 0, iv, rd),
        }
    }
}

// ===================================================================================
// §6. Hasher API
// ===================================================================================

#[derive(Clone)]
pub struct YttriumBuilder {
    iv: State,
    rounds: Rounds,
}

impl YttriumBuilder {
    pub fn unkeyed(rounds: Rounds) -> Self {
        let mut iv = [0u32; STATE_WORDS];
        let d = domain::UNKEYED.to_le_bytes();
        iv[STATE_WORDS - 1] = u32::from_le_bytes(d[0..4].try_into().unwrap());
        iv[STATE_WORDS - 2] = u32::from_le_bytes(d[4..8].try_into().unwrap());
        permute(&mut iv, rounds.r_mask);
        Self { iv, rounds }
    }

    pub fn keyed(key: &[u8], rounds: Rounds) -> Self {
        let mut iv = [0u32; STATE_WORDS];
        let d = domain::KEYED.to_le_bytes();
        iv[STATE_WORDS - 1] = u32::from_le_bytes(d[0..4].try_into().unwrap());
        iv[STATE_WORDS - 2] = u32::from_le_bytes(d[4..8].try_into().unwrap());
        for (i, chunk) in key.chunks(4).enumerate() {
            if i >= STATE_WORDS - 2 {
                break; // 키 ≤ 24 byte (capacity 6 워드)
            }
            let mut buf = [0u8; 4];
            buf[..chunk.len()].copy_from_slice(chunk);
            iv[i] ^= u32::from_le_bytes(buf);
        }
        permute(&mut iv, rounds.r_mask); // 키 흡수 = R_mask 라운드
        Self { iv, rounds }
    }

    pub fn build_hasher(&self) -> YttriumHasher {
        YttriumHasher::new(self.iv, self.rounds)
    }

    /// 일괄(one-shot) 해시. feature="simd"면 leaf-level 전체 SIMD 배치, 아니면 scalar.
    /// 스트리밍(`build_hasher`→update→finalize)과 **bit-exact** (no_std 호환, Vec 불요).
    pub fn hash(&self, data: &[u8]) -> Digest {
        let (iv, rd) = (&self.iv, &self.rounds);
        // single-leaf fast path (스트리밍은 256B서 flush → 경계는 strict <)
        if data.len() < T_MAX * BLOCK_BYTES {
            let (blocks, n) = split_input_into_blocks(data);
            let leaf = compute_leaf(&blocks, n, 0, iv, rd);
            return compute_root_from_acc(&cv_to_state(&leaf), data.len() as u64, 0, iv, rd);
        }
        let mut tree = TreeBuilder::new();
        push_leaf_digests(data, iv, rd, &mut tree);
        tree.finalize(data.len() as u64, iv, rd)
    }
}

#[derive(Clone)]
pub struct YttriumHasher {
    iv: State,
    rounds: Rounds,
    leaf_buf: [u8; T_MAX * BLOCK_BYTES],
    leaf_buf_len: usize,
    tree: TreeBuilder,
    in_tree_mode: bool,
    total_len: u64,
}

impl YttriumHasher {
    fn new(iv: State, rounds: Rounds) -> Self {
        Self {
            iv,
            rounds,
            leaf_buf: [0u8; T_MAX * BLOCK_BYTES],
            leaf_buf_len: 0,
            tree: TreeBuilder::new(),
            in_tree_mode: false,
            total_len: 0,
        }
    }

    pub fn update(&mut self, mut data: &[u8]) {
        self.total_len = self.total_len.wrapping_add(data.len() as u64);
        while !data.is_empty() {
            let space = T_MAX * BLOCK_BYTES - self.leaf_buf_len;
            let take = core::cmp::min(space, data.len());
            self.leaf_buf[self.leaf_buf_len..self.leaf_buf_len + take].copy_from_slice(&data[..take]);
            self.leaf_buf_len += take;
            data = &data[take..];
            if self.leaf_buf_len == T_MAX * BLOCK_BYTES {
                self.flush_leaf();
            }
        }
    }

    fn flush_leaf(&mut self) {
        let pos = self.tree.next_leaf_pos;
        let (blocks, n) = split_input_into_blocks(&self.leaf_buf[..self.leaf_buf_len]);
        let d = compute_leaf(&blocks, n, pos, &self.iv, &self.rounds);
        self.tree.push_leaf(d, &self.iv, &self.rounds);
        self.leaf_buf_len = 0;
        self.in_tree_mode = true;
    }

    pub fn finalize(mut self) -> Digest {
        if !self.in_tree_mode {
            let (blocks, n) = split_input_into_blocks(&self.leaf_buf[..self.leaf_buf_len]);
            let leaf = compute_leaf(&blocks, n, 0, &self.iv, &self.rounds);
            compute_root_from_acc(&cv_to_state(&leaf), self.total_len, 0, &self.iv, &self.rounds)
        } else {
            if self.leaf_buf_len > 0 {
                self.flush_leaf();
            }
            self.tree.clone().finalize(self.total_len, &self.iv, &self.rounds)
        }
    }
}

/// 편의 함수: unkeyed 일괄 해시 (배치 one-shot 경로).
pub fn hash(data: &[u8], rounds: Rounds) -> Digest {
    YttriumBuilder::unkeyed(rounds).hash(data)
}

// ===================================================================================
// side-channel 분석 훅 (운영 X; CPA 연구용으로 실 구현의 비밀-의존 중간값 노출)
// ===================================================================================

#[doc(hidden)]
#[cfg(debug_assertions)]
#[allow(dead_code)]
pub(crate) mod sca {
    //! ⚠ 분석 전용. 실제 keyed 경로가 계산하는 비밀-의존 중간값을 그대로 노출한다
    //! (전력 CPA가 타깃하는 값). **`pub(crate)` + `debug_assertions` 한정** — 공개 API
    //! 노출 안 됨, release 빌드엔 미포함(운영 코드에서 호출 불가). CPA는 in-crate 테스트.
    use super::*;

    /// 실제 derive_mask 산출 mask(leaf, pos, idx) — keyed IV에 의존(비밀).
    pub fn leaf_mask(b: &YttriumBuilder, pos: u64, idx: u32) -> State {
        derive_mask(&encode(LevelTag::Leaf, pos, idx), &b.iv, b.rounds.r_mask)
    }

    /// leaf 압축 첫 중간값 sᵢ = blockᵢ ⊕ mask(leaf,pos,idx) — 디바이스가 첫째로 leak하는 값.
    pub fn leaf_intermediate(b: &YttriumBuilder, block: &[u8; BLOCK_BYTES], pos: u64, idx: u32) -> State {
        let mask = leaf_mask(b, pos, idx);
        let mut s = [0u32; STATE_WORDS];
        for i in 0..STATE_WORDS {
            let w = u32::from_le_bytes(block[i * 4..(i + 1) * 4].try_into().unwrap());
            s[i] = w ^ mask[i];
        }
        s
    }

    /// 그 s로부터 라운드0 비선형 t = F(S) (전레인 혼합 post-mix; CPA 대조군 타깃).
    pub fn first_round_t(s: &State) -> u32 {
        let mut xp = [0u32; STATE_WORDS];
        for i in 0..STATE_WORDS {
            xp[i] = s[i].rotate_left(ROT_A);
        }
        f(zerosum_reduce(&xp))
    }
}

// ===================================================================================
// 단위 테스트 (정확성·가역성·구조)
// ===================================================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// §2.1 가역성: round_inv ∘ round = id (영합 reduction이 F·결합기 비가역과 무관하게 보장).
    #[test]
    fn round_is_invertible() {
        let mut x: State = [0x0123_4567, 0x89ab_cdef, 0xdead_beef, 0xcafe_babe, 1, 2, 3, 0xffff_ffff];
        let orig = x;
        for r in 0..50 {
            round(&mut x, r);
        }
        for r in (0..50).rev() {
            round_inv(&mut x, r);
        }
        assert_eq!(x, orig, "round_inv∘round must be identity");
    }

    /// permute / permute_inv 왕복.
    #[test]
    fn permute_roundtrip() {
        let mut x: State = [9, 8, 7, 6, 5, 4, 3, 2];
        let orig = x;
        permute(&mut x, 24);
        assert_ne!(x, orig);
        permute_inv(&mut x, 24);
        assert_eq!(x, orig);
    }

    /// α / α⁻¹ 왕복 (소표본).
    #[test]
    fn alpha_inverse() {
        for &v in &[0u32, 1, 2, 0x8000_0000, 0x400007, 0xffff_ffff, 0x1234_5678] {
            assert_eq!(alpha_inv(alpha(v)), v);
            assert_eq!(alpha(alpha_inv(v)), v);
        }
    }

    /// avalanche: 1비트 입력차분 → digest ~절반 비트 변화.
    #[test]
    fn avalanche() {
        let a = hash(b"yttrium", Rounds::V8_12_24);
        let b = hash(b"yttriun", Rounds::V8_12_24); // 1 byte diff
        let diff: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
        assert!((40..=88).contains(&diff), "avalanche {}/128", diff);
    }

    /// 결정성 + 변형/도메인 분리.
    #[test]
    fn determinism_and_separation() {
        assert_eq!(hash(b"abc", Rounds::V8_12_24), hash(b"abc", Rounds::V8_12_24));
        assert_ne!(hash(b"abc", Rounds::V8_12_24), hash(b"abc", Rounds::V10_14_24)); // 변형 분리
        let u = YttriumBuilder::unkeyed(Rounds::V4_6_12).build_hasher();
        let k = YttriumBuilder::keyed(b"key", Rounds::V4_6_12).build_hasher();
        let mut hu = u;
        let mut hk = k;
        hu.update(b"abc");
        hk.update(b"abc");
        assert_ne!(hu.finalize(), hk.finalize()); // keyed/unkeyed 분리
    }

    /// 멀티블록·멀티레벨 트리 경로 (single-leaf 한계 1024 byte 초과).
    #[test]
    fn tree_mode_runs() {
        let big = vec![0xA5u8; 5000];
        let d = hash(&big, Rounds::V8_12_24);
        assert_eq!(hash(&big, Rounds::V8_12_24), d);
        // 길이 민감성
        let big2 = vec![0xA5u8; 5001];
        assert_ne!(hash(&big2, Rounds::V8_12_24), d);
    }
}

// ===================================================================================
// 전력 side-channel (CPA) — Rust 실 구현 직접 공격 (sca 훅 사용; debug 빌드 한정)
// `cargo test --lib cpa_attack -- --ignored --nocapture` 로 실행.
// ===================================================================================
#[cfg(all(test, debug_assertions))]
mod sca_cpa {
    use super::*;

    fn hw(x: u8) -> f64 { x.count_ones() as f64 }
    fn sm(s: &mut u64) -> u64 {
        *s = s.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = *s;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
    fn gauss(s: &mut u64, sigma: f64) -> f64 {
        let u1 = ((sm(s) >> 11) as f64 / (1u64 << 53) as f64).max(1e-12);
        let u2 = (sm(s) >> 11) as f64 / (1u64 << 53) as f64;
        (-2.0 * u1.ln()).sqrt() * (2.0 * core::f64::consts::PI * u2).cos() * sigma
    }
    fn rand_block(s: &mut u64) -> [u8; BLOCK_BYTES] {
        let mut b = [0u8; BLOCK_BYTES];
        for c in b.iter_mut() { *c = sm(s) as u8; }
        b
    }
    /// leak=+HW+noise → 부호 있는 corr 최대 = 복구(보수 모호성 부호로 해소).
    fn cpa(known: &[u8], leak: &[f64], model: impl Fn(u8, u8) -> f64) -> (u8, f64) {
        let n = leak.len() as f64;
        let lm = leak.iter().sum::<f64>() / n;
        let lc: Vec<f64> = leak.iter().map(|&x| x - lm).collect();
        let ld = lc.iter().map(|x| x * x).sum::<f64>().sqrt();
        let (mut best, mut bestc) = (0u8, f64::MIN);
        for cand in 0..=255u8 {
            let pred: Vec<f64> = known.iter().map(|&b| model(b, cand)).collect();
            let pm = pred.iter().sum::<f64>() / n;
            let pc: Vec<f64> = pred.iter().map(|x| x - pm).collect();
            let pd = pc.iter().map(|x| x * x).sum::<f64>().sqrt();
            let cov: f64 = pc.iter().zip(&lc).map(|(a, b)| a * b).sum();
            let c = if pd > 0.0 && ld > 0.0 { cov / (pd * ld) } else { 0.0 };
            if c > bestc { bestc = c; best = cand; }
        }
        (best, bestc)
    }

    /// (A) 첫 중간값 block⊕mask 한 바이트 누출 → 실제 mask 바이트 복구.
    /// (C) 대조군: 비선형 t=F(S) per-byte CPA 실패. 귀속: 미보호 구현 누출(프리미티브 무관).
    #[test]
    #[ignore = "느림(수만 해시)·분석용; --ignored --nocapture 로 실행"]
    fn cpa_attack() {
        let kb = YttriumBuilder::keyed(b"yttrium-sca-secret-key", Rounds::V8_12_24);
        let secret = (sca::leaf_mask(&kb, 0, 0)[0] & 0xFF) as u8;
        let mut rs = 0xC0FFEE_1234_5678u64;
        println!("\n[CPA] 타깃 mask[0] 바이트0 = {:#04x} (공격자 미지)", secret);

        // (A) 노이즈 sweep
        for &sigma in &[0.5f64, 1.0, 2.0, 4.0] {
            let (mut known, mut leak) = (Vec::new(), Vec::new());
            for _ in 0..6000 {
                let blk = rand_block(&mut rs);
                let s = sca::leaf_intermediate(&kb, &blk, 0, 0);
                known.push(blk[0]);
                leak.push(hw((s[0] & 0xFF) as u8) + gauss(&mut rs, sigma));
            }
            let (rec, c) = cpa(&known, &leak, |b, k| hw(b ^ k));
            println!("  (A) σ={:>3}: 복구={:#04x} {} corr={:.3}", sigma, rec,
                     if rec == secret { "✓" } else { "✗" }, c);
            if sigma <= 2.0 { assert_eq!(rec, secret, "CPA가 mask 바이트를 복구해야(미보호 누출)"); }
        }

        // (C) 대조군: 비선형 t=F(S) per-byte → 실패 기대.
        let (mut known, mut leak) = (Vec::new(), Vec::new());
        for _ in 0..12000 {
            let blk = rand_block(&mut rs);
            let s = sca::leaf_intermediate(&kb, &blk, 0, 0);
            let t = sca::first_round_t(&s);
            known.push(blk[0]);
            leak.push(((t & 0xFF) as u8).count_ones() as f64 + gauss(&mut rs, 2.0));
        }
        let (_rec, c) = cpa(&known, &leak, |b, k| hw(b ^ k));
        println!("  (C) t=F(S) per-byte CPA: corr={:.3} → {}", c,
                 if c.abs() < 0.05 { "실패(기대): per-byte 비선형 타깃 부재" } else { "조사요" });
        assert!(c.abs() < 0.05, "비선형 post-mix는 per-byte CPA로 분리 불가해야");
        println!("  귀속: (A) 성공=미보호 선형 block⊕mask 누출(generic)·프리미티브 무관·HW-sim(하드웨어 아님).");
    }
}
