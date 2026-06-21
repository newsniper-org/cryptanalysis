//! yttrium-large — u64 형 (1024-bit 상태, yhash 크기 대응). SPEC §1.2.
//!
//! 구조는 u32 형과 **완전 동일**(영합 LM + ARX + all-lane GF α^k + π); 워드폭만 u64.
//! 순열 코어(round/round_inv/permute)·GF(2⁶⁴) + **Farfalle-tree 모드 전체**(encode 재사용,
//! derive_mask/compress/finalize/leaf/internal/root/TreeBuilder/Builder/hash, 가변 출력 truncation).
//! u32 모드(lib.rs)의 u64 포팅(scalar). 라운드수 *값*은 변형패밀리 `Rounds` 그대로 적용.
//! ⚠ 단 현 변형은 u32 **128-bit-digest** 기준 — large(256-bit digest)의 full 2¹²⁸ 보안엔
//! R_b↑(u32 slope 외삽 ~16-17) 필요. u64 best-DP slope 측정 = 잔여(§11).
//!
//! 검증(SPEC §1.2): 가역 roundtrip ✓, σ-power [1..15,17] GF(2)-선형 R*=17·prob-1 R*=2,
//! 해시모드 동작(`large_hash_mode` 테스트: 결정성·길이민감·가변출력·트리·keyed 분리).

pub const WORDS: usize = 16;
pub type StateL = [u64; WORDS];

/// GF(2⁶⁴) reduction: x⁶⁴ + x⁴ + x³ + x + 1 → low = 0x1B (primitive; ypsilenti↔yhash 동일).
pub const REDUCTION64: u64 = 0x1B;

const ROT_A: u32 = 8;
const ROT_B: u32 = 9;
const F_ROT: [(u32, u32); 3] = [(7, 17), (3, 21), (9, 29)];
/// π: (5i+7) mod 16 (단일 16-cycle).
const P_PI: [usize; WORDS] = [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2];
/// ε = [+,−]×8 (Σ=0).
const EPS_PLUS: [bool; WORDS] = [
    true, false, true, false, true, false, true, false,
    true, false, true, false, true, false, true, false,
];
/// σ all-16 distinct power: [1..15, 17] (skip 16→17; Σ=137). GF(2)-선형 R*=17.
const SIG_K: [u32; WORDS] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17];

/// RC: 비반복 SHA-512 라운드상수 K[r] (80개). 주입 레인 = r mod 16.
const SHA512_K: [u64; 80] = [
    0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
    0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
    0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
    0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
    0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
    0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
    0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
    0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b,
    0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
    0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
    0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
    0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
    0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
    0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817,
];

#[inline(always)]
fn rc(r: usize) -> u64 {
    if r < 80 { SHA512_K[r] } else { SHA512_K[r % 80] ^ (r as u64) }
}

#[inline(always)]
pub fn alpha(y: u64) -> u64 {
    let mask = 0u64.wrapping_sub(y >> 63);
    (y << 1) ^ (mask & REDUCTION64)
}

#[inline(always)]
fn alpha_pow(mut y: u64, k: u32) -> u64 {
    for _ in 0..k {
        y = alpha(y);
    }
    y
}

#[inline(always)]
pub fn alpha_inv(v: u64) -> u64 {
    if v & 1 != 0 {
        ((v ^ REDUCTION64) >> 1) | 0x8000_0000_0000_0000
    } else {
        v >> 1
    }
}

#[inline(always)]
fn alpha_pow_inv(mut v: u64, k: u32) -> u64 {
    for _ in 0..k {
        v = alpha_inv(v);
    }
    v
}

#[inline(always)]
pub fn f(s: u64) -> u64 {
    let mut acc = s;
    for &(a, b) in F_ROT.iter() {
        acc ^= s.rotate_left(a) & s.rotate_left(b);
    }
    acc
}

#[inline(always)]
fn zerosum_reduce(xp: &StateL) -> u64 {
    let mut s = 0u64;
    for i in 0..WORDS {
        if EPS_PLUS[i] {
            s = s.wrapping_add(xp[i]);
        } else {
            s = s.wrapping_sub(xp[i]);
        }
    }
    s
}

#[inline]
fn round(state: &mut StateL, r: usize) {
    state[r % WORDS] ^= rc(r);
    let mut xp = [0u64; WORDS];
    for i in 0..WORDS {
        xp[i] = state[i].rotate_left(ROT_A);
    }
    let s = zerosum_reduce(&xp);
    let t = f(s);
    for i in 0..WORDS {
        let v = xp[i].wrapping_add(t).rotate_right(ROT_B);
        state[i] = alpha_pow(v, SIG_K[i]);
    }
    let mut new = [0u64; WORDS];
    for i in 0..WORDS {
        new[i] = state[P_PI[i]];
    }
    *state = new;
}

#[inline]
fn round_inv(state: &mut StateL, r: usize) {
    let mut y = [0u64; WORDS];
    for i in 0..WORDS {
        y[P_PI[i]] = state[i];
    }
    let mut v = [0u64; WORDS];
    for i in 0..WORDS {
        v[i] = alpha_pow_inv(y[i], SIG_K[i]).rotate_left(ROT_B);
    }
    let s = zerosum_reduce(&v);
    let t = f(s);
    for i in 0..WORDS {
        state[i] = v[i].wrapping_sub(t).rotate_right(ROT_A);
    }
    state[r % WORDS] ^= rc(r);
}

#[inline]
pub fn permute(state: &mut StateL, rounds: usize) {
    for r in 0..rounds {
        round(state, r);
    }
}

#[inline]
pub fn permute_inv(state: &mut StateL, rounds: usize) {
    for r in (0..rounds).rev() {
        round_inv(state, r);
    }
}

// ===================================================================================
// yttrium-large Farfalle-tree 모드 (u32 모드의 u64 포팅; SPEC §1.2)
// 라운드수 *미확정*(§11) — u32 변형 Rounds를 잠정 적용. encode/LevelTag/domain은 super 재사용.
// ===================================================================================

use super::{domain, encode, LevelTag, Rounds, MAX_TREE_DEPTH, T_MAX};

pub const BLOCK_BYTES_L: usize = WORDS * 8; // 128
pub const CV_BYTES_L: usize = 32; // 256-bit 체이닝 CV (내부); 출력은 가변 truncation

type CvL = [u8; CV_BYTES_L];

fn derive_mask(seed: &[u8; 16], iv: &StateL, r_mask: usize) -> StateL {
    let mut s = *iv;
    for i in 0..2 {
        s[i] ^= u64::from_le_bytes(seed[i * 8..(i + 1) * 8].try_into().unwrap());
    }
    permute(&mut s, r_mask);
    s
}

fn compress_block(block: &[u8; BLOCK_BYTES_L], mask: &StateL, r_b: usize) -> StateL {
    let mut s = [0u64; WORDS];
    for i in 0..WORDS {
        s[i] = u64::from_le_bytes(block[i * 8..(i + 1) * 8].try_into().unwrap()) ^ mask[i];
    }
    permute(&mut s, r_b);
    s
}

fn finalize_state(state: &StateL, mm: &StateL, r_c: usize) -> StateL {
    let mut s = *state;
    for i in 0..WORDS {
        s[i] ^= mm[i];
    }
    permute(&mut s, r_c);
    s
}

/// 가변 길이 출력: 최종 상태 앞 nbytes (LE), nbytes ≤ 128.
fn truncate(state: &StateL, nbytes: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(nbytes);
    'fill: for w in state.iter() {
        for b in w.to_le_bytes() {
            if out.len() == nbytes {
                break 'fill;
            }
            out.push(b);
        }
    }
    out
}

fn cv_of(state: &StateL) -> CvL {
    let mut cv = [0u8; CV_BYTES_L];
    for i in 0..(CV_BYTES_L / 8) {
        cv[i * 8..(i + 1) * 8].copy_from_slice(&state[i].to_le_bytes());
    }
    cv
}

fn cv_to_state(cv: &CvL) -> StateL {
    let mut s = [0u64; WORDS];
    for i in 0..(CV_BYTES_L / 8) {
        s[i] = u64::from_le_bytes(cv[i * 8..(i + 1) * 8].try_into().unwrap());
    }
    s
}

fn pad_partial(input: &[u8]) -> [u8; BLOCK_BYTES_L] {
    let mut b = [0u8; BLOCK_BYTES_L];
    b[..input.len()].copy_from_slice(input);
    b[input.len()] = 0x01;
    b[BLOCK_BYTES_L - 1] |= 0x80;
    b
}

fn pad_cv(cv: &CvL) -> [u8; BLOCK_BYTES_L] {
    let mut b = [0u8; BLOCK_BYTES_L];
    b[..CV_BYTES_L].copy_from_slice(cv);
    b[CV_BYTES_L] = 0x01;
    b[BLOCK_BYTES_L - 1] |= 0x80;
    b
}

fn split_blocks(input: &[u8]) -> ([[u8; BLOCK_BYTES_L]; T_MAX], usize) {
    let mut blocks = [[0u8; BLOCK_BYTES_L]; T_MAX];
    let full = input.len() / BLOCK_BYTES_L;
    let rem = input.len() % BLOCK_BYTES_L;
    for j in 0..full {
        blocks[j].copy_from_slice(&input[j * BLOCK_BYTES_L..(j + 1) * BLOCK_BYTES_L]);
    }
    let n = if rem > 0 || full == 0 {
        blocks[full] = pad_partial(&input[full * BLOCK_BYTES_L..]);
        full + 1
    } else {
        full
    };
    (blocks, n)
}

fn compute_leaf(blocks: &[[u8; BLOCK_BYTES_L]], n: usize, pos: u64, iv: &StateL, rd: &Rounds) -> CvL {
    let mut acc = [0u64; WORDS];
    for j in 0..n {
        let mask = derive_mask(&encode(LevelTag::Leaf, pos, j as u32), iv, rd.r_mask);
        let y = compress_block(&blocks[j], &mask, rd.r_b);
        for i in 0..WORDS {
            acc[i] ^= y[i];
        }
    }
    let mm = derive_mask(&encode(LevelTag::Leaf, pos, T_MAX as u32), iv, rd.r_mask);
    cv_of(&finalize_state(&acc, &mm, rd.r_c))
}

fn compute_internal(level: u32, pos: u64, l: &CvL, r: &CvL, iv: &StateL, rd: &Rounds) -> CvL {
    let ml = derive_mask(&encode(LevelTag::Internal(level), pos, 0), iv, rd.r_mask);
    let mr = derive_mask(&encode(LevelTag::Internal(level), pos, 1), iv, rd.r_mask);
    let yl = compress_block(&pad_cv(l), &ml, rd.r_b);
    let yr = compress_block(&pad_cv(r), &mr, rd.r_b);
    let mut acc = [0u64; WORDS];
    for i in 0..WORDS {
        acc[i] = yl[i] ^ yr[i];
    }
    let mm = derive_mask(&encode(LevelTag::Internal(level), pos, T_MAX as u32), iv, rd.r_mask);
    cv_of(&finalize_state(&acc, &mm, rd.r_c))
}

fn root_from_acc(acc: &StateL, total_len: u64, shape: u32, iv: &StateL, rd: &Rounds, out: usize) -> Vec<u8> {
    let mm = derive_mask(&encode(LevelTag::Root, total_len, shape), iv, rd.r_mask);
    truncate(&finalize_state(acc, &mm, rd.r_c), out)
}

#[derive(Clone)]
struct TreeBuilderL {
    pending: [Option<CvL>; MAX_TREE_DEPTH],
    next: u64,
}
impl TreeBuilderL {
    fn new() -> Self {
        Self { pending: [None; MAX_TREE_DEPTH], next: 0 }
    }
    fn push(&mut self, mut d: CvL, iv: &StateL, rd: &Rounds) {
        let mut level = 0u32;
        loop {
            match self.pending[level as usize].take() {
                None => {
                    self.pending[level as usize] = Some(d);
                    break;
                }
                Some(left) => {
                    let pos = self.next >> (level + 1);
                    level += 1;
                    d = compute_internal(level, pos, &left, &d, iv, rd);
                }
            }
        }
        self.next += 1;
    }
    fn finalize(mut self, total_len: u64, iv: &StateL, rd: &Rounds, out: usize) -> Vec<u8> {
        let mut cur: Option<CvL> = None;
        for level in 0..MAX_TREE_DEPTH {
            match (self.pending[level].take(), cur) {
                (None, c) => cur = c,
                (Some(p), None) => cur = Some(p),
                (Some(p), Some(c)) => {
                    let pos = self.next >> (level as u32 + 1);
                    cur = Some(compute_internal(level as u32 + 1, pos, &p, &c, iv, rd));
                }
            }
        }
        match cur {
            Some(d) => root_from_acc(&cv_to_state(&d), total_len, 1, iv, rd, out),
            None => root_from_acc(&[0u64; WORDS], 0, 0, iv, rd, out),
        }
    }
}

/// yttrium-large 빌더 (keyed: 키 ≤ 120 byte = capacity 15 워드; domain은 iv[15]).
#[derive(Clone)]
pub struct YttriumLargeBuilder {
    iv: StateL,
    rounds: Rounds,
}
impl YttriumLargeBuilder {
    pub fn unkeyed(rounds: Rounds) -> Self {
        let mut iv = [0u64; WORDS];
        iv[WORDS - 1] = domain::UNKEYED;
        permute(&mut iv, rounds.r_mask);
        Self { iv, rounds }
    }
    pub fn keyed(key: &[u8], rounds: Rounds) -> Self {
        let mut iv = [0u64; WORDS];
        iv[WORDS - 1] = domain::KEYED;
        for (i, ch) in key.chunks(8).enumerate() {
            if i >= WORDS - 1 {
                break;
            }
            let mut buf = [0u8; 8];
            buf[..ch.len()].copy_from_slice(ch);
            iv[i] ^= u64::from_le_bytes(buf);
        }
        permute(&mut iv, rounds.r_mask);
        Self { iv, rounds }
    }
    pub fn hash(&self, data: &[u8], out_bytes: usize) -> Vec<u8> {
        debug_assert!(out_bytes <= BLOCK_BYTES_L);
        // single-leaf fast path vs tree
        if data.len() <= T_MAX * BLOCK_BYTES_L {
            let (blocks, n) = split_blocks(data);
            let leaf = compute_leaf(&blocks, n, 0, &self.iv, &self.rounds);
            return root_from_acc(&cv_to_state(&leaf), data.len() as u64, 0, &self.iv, &self.rounds, out_bytes);
        }
        let mut tree = TreeBuilderL::new();
        let mut off = 0;
        while off + T_MAX * BLOCK_BYTES_L <= data.len() {
            let chunk = &data[off..off + T_MAX * BLOCK_BYTES_L];
            let (blocks, n) = split_blocks(chunk);
            let pos = tree.next;
            tree.push(compute_leaf(&blocks, n, pos, &self.iv, &self.rounds), &self.iv, &self.rounds);
            off += T_MAX * BLOCK_BYTES_L;
        }
        if off < data.len() {
            let (blocks, n) = split_blocks(&data[off..]);
            let pos = tree.next;
            tree.push(compute_leaf(&blocks, n, pos, &self.iv, &self.rounds), &self.iv, &self.rounds);
        }
        tree.finalize(data.len() as u64, &self.iv, &self.rounds, out_bytes)
    }
}

/// 편의: unkeyed yttrium-large 해시 (가변 출력).
pub fn hash(data: &[u8], rounds: Rounds, out_bytes: usize) -> Vec<u8> {
    YttriumLargeBuilder::unkeyed(rounds).hash(data, out_bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_is_invertible_u64() {
        let mut x: StateL = [
            0x0123_4567_89ab_cdef, 0xdead_beef_cafe_babe, 1, 2, 3, 4, 5, 6,
            0xffff_ffff_ffff_ffff, 7, 8, 9, 10, 11, 12, 0x8000_0000_0000_0001,
        ];
        let orig = x;
        for r in 0..50 {
            round(&mut x, r);
        }
        for r in (0..50).rev() {
            round_inv(&mut x, r);
        }
        assert_eq!(x, orig);
    }

    #[test]
    fn permute_roundtrip_u64() {
        let mut x: StateL = core::array::from_fn(|i| (i as u64).wrapping_mul(0x9E3779B97F4A7C15));
        let orig = x;
        permute(&mut x, 24);
        assert_ne!(x, orig);
        permute_inv(&mut x, 24);
        assert_eq!(x, orig);
    }

    #[test]
    fn alpha_inverse_u64() {
        for &v in &[0u64, 1, 2, 0x8000_0000_0000_0000, 0x1B, u64::MAX, 0x1234_5678_9abc_def0] {
            assert_eq!(alpha_inv(alpha(v)), v);
            assert_eq!(alpha(alpha_inv(v)), v);
        }
    }

    #[test]
    fn avalanche_u64() {
        let mut a: StateL = [0u64; WORDS];
        let mut b: StateL = [0u64; WORDS];
        b[3] = 1; // 1-bit diff
        permute(&mut a, 8);
        permute(&mut b, 8);
        let diff: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
        assert!((350..=674).contains(&diff), "avalanche {}/1024", diff);
    }

    #[test]
    fn large_hash_mode() {
        use super::Rounds;
        let rd = Rounds::V8_12_24;
        // 결정성
        assert_eq!(hash(b"abc", rd, 32), hash(b"abc", rd, 32));
        // 길이 민감성
        assert_ne!(hash(b"abc", rd, 32), hash(b"abcd", rd, 32));
        // 가변 출력: 256/384/512-bit (32/48/64 byte)
        assert_eq!(hash(b"abc", rd, 32).len(), 32);
        assert_eq!(hash(b"abc", rd, 48).len(), 48);
        assert_eq!(hash(b"abc", rd, 64).len(), 64);
        // 긴 출력은 짧은 출력의 prefix (truncation 일관)
        assert_eq!(&hash(b"abc", rd, 64)[..32], &hash(b"abc", rd, 32)[..]);
        // 변형 분리
        assert_ne!(hash(b"abc", rd, 32), hash(b"abc", Rounds::V10_14_24, 32));
        // 트리 모드 (>1024 byte single-leaf 한계 초과) 결정성·길이민감
        let big = vec![0xC3u8; 5000];
        assert_eq!(hash(&big, rd, 32), hash(&big, rd, 32));
        assert_ne!(hash(&vec![0xC3u8; 5001], rd, 32), hash(&big, rd, 32));
        // keyed(256-bit)/unkeyed 분리
        let ku = YttriumLargeBuilder::unkeyed(rd).hash(b"abc", 32);
        let kk = YttriumLargeBuilder::keyed(&[0x11u8; 32], rd).hash(b"abc", 32);
        assert_ne!(ku, kk);
    }
}
