//! ypsilenti 순열 — Level B SIMD (inter-block batch).
//!
//! Level A(상태 8워드를 한 벡터에)는 매 라운드 수평 reduce + σ-층 lane 추출로
//! scalar보다 느렸다. **Level B는 독립 블록 BATCH개를 lane에 실어** 동일 연산을
//! lane-병렬로 적용한다. 수평 연산은 라운드 루프 밖(최종 fold)에만.
//!
//! 백엔드:
//! - `nightly-portable-simd` → `core::simd::Simd<u32, 8>`
//! - `stable-portable-simd`  → `wide::u32x8`
//!
//! 두 백엔드 모두 [`Lane`] 트레잇으로 추상화 — 알고리즘은 한 벌만 유지한다.

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P_PI, RC, STATE_WORDS};
use crate::gf32::REDUCTION;
use crate::perm::State;

/// SIMD batch 폭 = T_MAX (leaf 당 최대 블록 수). u32 경로는 8 lane이 단일 레지스터.
pub const BATCH: usize = 8;

/// 8-lane u32 벡터 추상화 (백엔드 중립).
trait Lane: Copy {
    fn splat(x: u32) -> Self;
    fn from_arr(a: [u32; BATCH]) -> Self;
    fn to_arr(self) -> [u32; BATCH];
    fn xor(self, o: Self) -> Self;
    fn and(self, o: Self) -> Self;
    fn or(self, o: Self) -> Self;
    /// lane-wise 논리 좌측 시프트 (uniform amount).
    fn shl(self, k: u32) -> Self;
    /// lane-wise 논리 우측 시프트 (uniform amount).
    fn shr(self, k: u32) -> Self;
    /// lane별 `0u32.wrapping_sub(self)` (α-곱 mask 생성용).
    fn neg(self) -> Self;
}

#[inline(always)]
fn rotl<L: Lane>(v: L, k: u32) -> L {
    v.shl(k).or(v.shr(32 - k))
}

#[inline(always)]
fn f_v<L: Lane>(s: L) -> L {
    s.xor(rotl(s, F_ROT_A).and(rotl(s, F_ROT_B)))
        .xor(rotl(s, F_ROT_C).and(rotl(s, F_ROT_D)))
}

#[inline(always)]
fn alpha_v<L: Lane>(y: L) -> L {
    let msb = y.shr(31); // lane: 0 또는 1
    let mask = msb.neg(); // lane: 0 또는 0xFFFF_FFFF
    y.shl(1).xor(mask.and(L::splat(REDUCTION)))
}

#[inline(always)]
fn alpha_pow_v<L: Lane>(mut y: L, k: u32) -> L {
    for _ in 0..k {
        y = alpha_v(y);
    }
    y
}

/// BATCH개 독립 상태(SoA)에 `rounds` 라운드 적용. scalar `permute`와 lane별 일치.
#[inline]
fn permute_batch<L: Lane>(soa: &mut [L; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        let pos = r & 7;
        soa[pos] = soa[pos].xor(L::splat(RC[pos]));

        let mut s = soa[0];
        for i in 1..STATE_WORDS {
            s = s.xor(soa[i]);
        }
        let t = f_v(s);
        for w in soa.iter_mut() {
            *w = w.xor(t);
        }

        soa[0] = alpha_pow_v(soa[0], 1);
        soa[4] = alpha_pow_v(soa[4], 3);

        let old = *soa;
        for i in 0..STATE_WORDS {
            soa[i] = old[P_PI[i]];
        }
    }
}

/// 백엔드-제네릭 leaf 압축. n개 블록(≤BATCH)을 한 batch로 처리.
fn compute_leaf_acc_impl<L: Lane>(
    blocks: &[[u8; 32]],
    seeds: &[[u8; 16]],
    n: usize,
    iv: &State,
    mask_rounds: usize,
    leaf_rounds: usize,
) -> State {
    debug_assert!(n <= BATCH);

    // --- mask derive (SoA): md[i] lane j = iv[i] ⊕ (seed_j word i, i<4) ---
    let mut md = [[0u32; BATCH]; STATE_WORDS];
    for (i, row) in md.iter_mut().enumerate() {
        *row = [iv[i]; BATCH];
    }
    for j in 0..n {
        for i in 0..4 {
            let w = u32::from_le_bytes(seeds[j][i * 4..i * 4 + 4].try_into().unwrap());
            md[i][j] ^= w;
        }
    }
    let mut m: [L; STATE_WORDS] = core::array::from_fn(|i| L::from_arr(md[i]));
    permute_batch(&mut m, mask_rounds);

    // --- compress (SoA): c_in[i] = block_word ⊕ mask ---
    let mut bl = [[0u32; BATCH]; STATE_WORDS];
    for j in 0..n {
        for i in 0..STATE_WORDS {
            bl[i][j] = u32::from_le_bytes(blocks[j][i * 4..i * 4 + 4].try_into().unwrap());
        }
    }
    let mut c: [L; STATE_WORDS] = core::array::from_fn(|i| L::from_arr(bl[i]).xor(m[i]));
    permute_batch(&mut c, leaf_rounds);

    // --- fold lanes 0..n into acc (라운드 밖) ---
    let mut acc = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let lanes = c[i].to_arr();
        let mut w = 0u32;
        for &l in lanes.iter().take(n) {
            w ^= l;
        }
        acc[i] = w;
    }
    acc
}

/// Leaf의 n개 블록을 batch로 mask-derive + compress 하여 `acc` 반환.
///
/// scalar 경로(`derive_mask` → `compress_block` → XOR 누적)와 비트단위로 일치.
#[inline]
pub fn compute_leaf_acc(
    blocks: &[[u8; 32]],
    seeds: &[[u8; 16]],
    n: usize,
    iv: &State,
    mask_rounds: usize,
    leaf_rounds: usize,
) -> State {
    compute_leaf_acc_impl::<Backend>(blocks, seeds, n, iv, mask_rounds, leaf_rounds)
}

// ---- 백엔드: nightly core::simd ----

#[cfg(ypsi_simd_nightly)]
type Backend = core::simd::Simd<u32, BATCH>;

#[cfg(ypsi_simd_nightly)]
impl Lane for core::simd::Simd<u32, BATCH> {
    #[inline(always)]
    fn splat(x: u32) -> Self {
        Self::splat(x)
    }
    #[inline(always)]
    fn from_arr(a: [u32; BATCH]) -> Self {
        Self::from_array(a)
    }
    #[inline(always)]
    fn to_arr(self) -> [u32; BATCH] {
        self.to_array()
    }
    #[inline(always)]
    fn xor(self, o: Self) -> Self {
        self ^ o
    }
    #[inline(always)]
    fn and(self, o: Self) -> Self {
        self & o
    }
    #[inline(always)]
    fn or(self, o: Self) -> Self {
        self | o
    }
    #[inline(always)]
    fn shl(self, k: u32) -> Self {
        self << Self::splat(k)
    }
    #[inline(always)]
    fn shr(self, k: u32) -> Self {
        self >> Self::splat(k)
    }
    #[inline(always)]
    fn neg(self) -> Self {
        Self::splat(0) - self
    }
}

// ---- 백엔드: stable wide ----

#[cfg(all(ypsi_simd_stable, not(ypsi_simd_nightly)))]
type Backend = wide::u32x8;

#[cfg(all(ypsi_simd_stable, not(ypsi_simd_nightly)))]
impl Lane for wide::u32x8 {
    #[inline(always)]
    fn splat(x: u32) -> Self {
        wide::u32x8::splat(x)
    }
    #[inline(always)]
    fn from_arr(a: [u32; BATCH]) -> Self {
        wide::u32x8::from(a)
    }
    #[inline(always)]
    fn to_arr(self) -> [u32; BATCH] {
        self.to_array()
    }
    #[inline(always)]
    fn xor(self, o: Self) -> Self {
        self ^ o
    }
    #[inline(always)]
    fn and(self, o: Self) -> Self {
        self & o
    }
    #[inline(always)]
    fn or(self, o: Self) -> Self {
        self | o
    }
    #[inline(always)]
    fn shl(self, k: u32) -> Self {
        self << wide::u32x8::splat(k)
    }
    #[inline(always)]
    fn shr(self, k: u32) -> Self {
        self >> wide::u32x8::splat(k)
    }
    #[inline(always)]
    fn neg(self) -> Self {
        wide::u32x8::splat(0) - self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::consts::{rounds, LevelTag};
    use crate::encode::encode;
    use crate::perm::{compress_block, derive_mask};

    /// batch leaf 압축이 scalar 경로와 비트단위 일치하는지 (활성 백엔드 기준).
    #[test]
    fn batch_leaf_matches_scalar() {
        let iv: State = core::array::from_fn(|i| 0x9E37_79B9u32 ^ (i as u32).wrapping_mul(0x101));
        for n in 1..=BATCH {
            let blocks: [[u8; 32]; BATCH] =
                core::array::from_fn(|j| core::array::from_fn(|b| (j * 13 + b * 7 + 1) as u8));
            let seeds: [[u8; 16]; BATCH] =
                core::array::from_fn(|j| encode(LevelTag::Leaf, 0, j as u32));

            // scalar 기대값
            let mut want = [0u32; STATE_WORDS];
            for j in 0..n {
                let mask = derive_mask(&seeds[j], &iv);
                let y = compress_block(&blocks[j], &mask, rounds::LEAF);
                for i in 0..STATE_WORDS {
                    want[i] ^= y[i];
                }
            }
            let got = compute_leaf_acc(&blocks, &seeds, n, &iv, rounds::MASK_DERIVE, rounds::LEAF);
            assert_eq!(got, want, "n={}", n);
        }
    }
}
