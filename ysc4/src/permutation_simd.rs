//! YSC4-p 순열 — Level B SIMD (inter-block batch).
//!
//! 독립 블록 BATCH개를 lane에 실어 동일 연산을 lane-병렬 적용한다 (SoA).
//! 백엔드:
//! - `nightly-portable-simd` → `core::simd::Simd<u64, 8>` ([`permute_batch`])
//! - `stable-portable-simd`  → `wide::u64x4` ([`permute_batch_wide`])
//!
//! 두 백엔드는 [`Lane64`] 트레잇으로 추상화 — 순열 알고리즘은 한 벌만 유지.
//! SoA 구성/fold는 호출측(`yhash::perm_simd`)이 담당한다.

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P, RC, STATE_WORDS};
use crate::gf2_64::REDUCTION;

/// nightly u64 batch 폭. (stable wide 경로는 4-lane.)
pub const BATCH: usize = 8;

/// u64 lane 벡터 추상화 (백엔드 중립, 폭 무관). 내부용.
trait Lane64: Copy {
    fn splat(x: u64) -> Self;
    fn xor(self, o: Self) -> Self;
    fn and(self, o: Self) -> Self;
    fn or(self, o: Self) -> Self;
    fn shl(self, k: u32) -> Self;
    fn shr(self, k: u32) -> Self;
    /// lane별 `0u64.wrapping_sub(self)`.
    fn neg(self) -> Self;
}

#[inline(always)]
fn rotl<L: Lane64>(v: L, k: u32) -> L {
    v.shl(k).or(v.shr(64 - k))
}

#[inline(always)]
fn f_v<L: Lane64>(s: L) -> L {
    s.xor(rotl(s, F_ROT_A).and(rotl(s, F_ROT_B)))
        .xor(rotl(s, F_ROT_C).and(rotl(s, F_ROT_D)))
}

#[inline(always)]
fn alpha_v<L: Lane64>(y: L) -> L {
    let mask = y.shr(63).neg(); // lane: 0 또는 0xFFFF…FF
    y.shl(1).xor(mask.and(L::splat(REDUCTION)))
}

#[inline(always)]
fn alpha_pow_v<L: Lane64>(mut y: L, k: u32) -> L {
    for _ in 0..k {
        y = alpha_v(y);
    }
    y
}

/// SoA(`soa[i]` = 모든 lane의 word i)에 `rounds` 라운드 적용. scalar와 lane별 일치.
#[inline]
fn permute_batch_generic<L: Lane64>(soa: &mut [L; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        let pos = r & 15;
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
        soa[8] = alpha_pow_v(soa[8], 5);
        soa[12] = alpha_pow_v(soa[12], 7);

        let old = *soa;
        for i in 0..STATE_WORDS {
            soa[i] = old[P[i]];
        }
    }
}

// ---- nightly: core::simd ----

/// nightly SoA 타입 (`Simd<u64, 8>`).
#[cfg(ysc4_simd_nightly)]
pub type Vu64 = core::simd::Simd<u64, BATCH>;

#[cfg(ysc4_simd_nightly)]
impl Lane64 for core::simd::Simd<u64, BATCH> {
    #[inline(always)]
    fn splat(x: u64) -> Self {
        Self::splat(x)
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
        self << Self::splat(k as u64)
    }
    #[inline(always)]
    fn shr(self, k: u32) -> Self {
        self >> Self::splat(k as u64)
    }
    #[inline(always)]
    fn neg(self) -> Self {
        Self::splat(0) - self
    }
}

/// nightly: 8-lane SoA batch 순열.
#[cfg(ysc4_simd_nightly)]
#[inline]
pub fn permute_batch(soa: &mut [Vu64; STATE_WORDS], rounds: usize) {
    permute_batch_generic(soa, rounds);
}

// ---- stable: wide ----

#[cfg(all(ysc4_simd_stable, not(ysc4_simd_nightly)))]
impl Lane64 for wide::u64x4 {
    #[inline(always)]
    fn splat(x: u64) -> Self {
        wide::u64x4::splat(x)
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
        self << wide::u64x4::splat(k as u64)
    }
    #[inline(always)]
    fn shr(self, k: u32) -> Self {
        self >> wide::u64x4::splat(k as u64)
    }
    #[inline(always)]
    fn neg(self) -> Self {
        wide::u64x4::splat(0) - self
    }
}

/// stable: 4-lane SoA batch 순열.
#[cfg(all(ysc4_simd_stable, not(ysc4_simd_nightly)))]
#[inline]
pub fn permute_batch_wide(soa: &mut [wide::u64x4; STATE_WORDS], rounds: usize) {
    permute_batch_generic(soa, rounds);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::permutation::permute_scalar;

    #[cfg(ysc4_simd_nightly)]
    #[test]
    fn batch_matches_scalar_nightly() {
        let mut states = [[0u64; STATE_WORDS]; BATCH];
        for (j, st) in states.iter_mut().enumerate() {
            for (i, w) in st.iter_mut().enumerate() {
                *w = 0x9E37_79B9_7F4A_7C15u64
                    .wrapping_mul((j as u64 + 1).wrapping_mul(i as u64 + 11))
                    .wrapping_add(((j as u64) << 16) ^ i as u64);
            }
        }
        for &rounds in &[1usize, 8, 16, 24] {
            let mut want = states;
            for st in want.iter_mut() {
                permute_scalar(st, rounds);
            }
            let mut soa: [Vu64; STATE_WORDS] =
                core::array::from_fn(|i| Vu64::from_array(core::array::from_fn(|j| states[j][i])));
            permute_batch(&mut soa, rounds);
            let got: [[u64; STATE_WORDS]; BATCH] =
                core::array::from_fn(|j| core::array::from_fn(|i| soa[i].to_array()[j]));
            assert_eq!(got, want, "rounds={}", rounds);
        }
    }

    #[cfg(all(ysc4_simd_stable, not(ysc4_simd_nightly)))]
    #[test]
    fn batch_matches_scalar_wide() {
        const W: usize = 4;
        let mut states = [[0u64; STATE_WORDS]; W];
        for (j, st) in states.iter_mut().enumerate() {
            for (i, w) in st.iter_mut().enumerate() {
                *w = 0x9E37_79B9_7F4A_7C15u64
                    .wrapping_mul((j as u64 + 1).wrapping_mul(i as u64 + 11))
                    .wrapping_add(((j as u64) << 16) ^ i as u64);
            }
        }
        for &rounds in &[1usize, 8, 16, 24] {
            let mut want = states;
            for st in want.iter_mut() {
                permute_scalar(st, rounds);
            }
            let mut soa: [wide::u64x4; STATE_WORDS] = core::array::from_fn(|i| {
                wide::u64x4::from(core::array::from_fn::<u64, W, _>(|j| states[j][i]))
            });
            permute_batch_wide(&mut soa, rounds);
            let got: [[u64; STATE_WORDS]; W] =
                core::array::from_fn(|j| core::array::from_fn(|i| soa[i].to_array()[j]));
            assert_eq!(got, want, "rounds={}", rounds);
        }
    }
}
