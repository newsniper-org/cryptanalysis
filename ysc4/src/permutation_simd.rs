//! YSC4-p 순열 — Level B SIMD (inter-block batch). nightly 전용.
//!
//! Level A(상태 16워드를 한 벡터에)는 매 라운드 수평 `reduce_xor` + σ-층 lane
//! 추출 때문에 scalar보다 느렸다. **Level B는 독립 블록 BATCH개를 lane에 실어**
//! *동일 연산을 lane-병렬*로 적용한다. 수평 연산은 라운드 루프 밖에만.
//!
//! - SoA 레이아웃: `soa[i]` 는 `Simd<u64, BATCH>` — 모든 lane(=블록)의 word `i`.
//!
//! yhash가 leaf 압축에서 이 `permute_batch`를 사용한다 (`yhash::perm_simd`).

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P, RC, STATE_WORDS};
use crate::gf2_64::REDUCTION;
use core::simd::Simd;

/// SIMD batch 폭 = YHash T_MAX (leaf 당 최대 블록 수).
pub const BATCH: usize = 8;
/// SoA batched state 타입.
pub type Vu64 = Simd<u64, BATCH>;

#[inline(always)]
fn rotl(v: Vu64, k: u32) -> Vu64 {
    (v << Vu64::splat(k as u64)) | (v >> Vu64::splat((64 - k) as u64))
}

#[inline(always)]
fn f_v(s: Vu64) -> Vu64 {
    s ^ (rotl(s, F_ROT_A) & rotl(s, F_ROT_B)) ^ (rotl(s, F_ROT_C) & rotl(s, F_ROT_D))
}

#[inline(always)]
fn alpha_v(y: Vu64) -> Vu64 {
    let msb = y >> Vu64::splat(63); // lane: 0 또는 1
    let mask = Vu64::splat(0) - msb; // lane: 0 또는 0xFFFF…FF
    (y << Vu64::splat(1)) ^ (mask & Vu64::splat(REDUCTION))
}

#[inline(always)]
fn alpha_pow_v(mut y: Vu64, k: u32) -> Vu64 {
    for _ in 0..k {
        y = alpha_v(y);
    }
    y
}

/// BATCH개 독립 상태(SoA)에 `rounds` 라운드 적용. scalar `permute`와 lane별 일치.
#[inline]
pub fn permute_batch(soa: &mut [Vu64; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        let pos = r & 15;
        soa[pos] ^= Vu64::splat(RC[pos]);

        let mut s = soa[0];
        for i in 1..STATE_WORDS {
            s ^= soa[i];
        }
        let t = f_v(s);
        for w in soa.iter_mut() {
            *w ^= t;
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::permutation::permute_scalar;

    #[test]
    fn batch_matches_scalar() {
        let mut states = [[0u64; STATE_WORDS]; BATCH];
        for (j, st) in states.iter_mut().enumerate() {
            for (i, w) in st.iter_mut().enumerate() {
                *w = 0x9E37_79B9_7F4A_7C15u64
                    .wrapping_mul((j as u64 + 1).wrapping_mul(i as u64 + 11))
                    .wrapping_add(0xDEAD_BEEF_0000_0000 ^ ((j as u64) << 16) ^ i as u64);
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
}
