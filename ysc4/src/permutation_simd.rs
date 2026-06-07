//! YSC4-p 순열 — Level A SIMD (intra-permutation) 구현.
//!
//! 상태 16×u64 = 1024-bit를 단일 SIMD 레지스터로 처리.
//! - nightly: `core::simd::u64x16` (portable_simd)
//! - stable: 미구현 (scalar fallback)
//!
//! scalar `permutation.rs`와 비트단위로 일치해야 한다.

#[cfg(ysc4_simd_nightly)]
pub use nightly::permute_simd;

#[cfg(all(ysc4_simd_stable, not(ysc4_simd_nightly)))]
pub use stable_fallback::permute_simd;

// ---- Nightly: core::simd 기반 ----

#[cfg(ysc4_simd_nightly)]
mod nightly {
    use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, RC, STATE_WORDS};
    use crate::gf2_64::alpha_pow;
    use core::simd::num::SimdUint;
    use core::simd::{simd_swizzle, u64x16};

    /// F 함수 — scalar (단일 u64에 적용).
    #[inline(always)]
    fn f_scalar(s: u64) -> u64 {
        s ^ (s.rotate_left(F_ROT_A) & s.rotate_left(F_ROT_B))
          ^ (s.rotate_left(F_ROT_C) & s.rotate_left(F_ROT_D))
    }

    /// 16-lane state를 SIMD 벡터로 round 처리.
    #[inline]
    fn round_simd(v: u64x16, r: usize) -> u64x16 {
        // 1) ι: RC XOR at lane r&15
        let pos = r & 15;
        let mut rc_v = [0u64; 16];
        rc_v[pos] = RC[pos];
        let v = v ^ u64x16::from_array(rc_v);

        // 2) S = ⊕ᵢ vᵢ, T = F(S)
        let s = v.reduce_xor();
        let t = f_scalar(s);

        // 3) broadcast XOR T
        let v = v ^ u64x16::splat(t);

        // 4) σ-층: lanes {0,4,8,12}에 α^{1,3,5,7}
        let mut arr = v.to_array();
        arr[0] = alpha_pow(arr[0], 1);
        arr[4] = alpha_pow(arr[4], 3);
        arr[8] = alpha_pow(arr[8], 5);
        arr[12] = alpha_pow(arr[12], 7);
        let v = u64x16::from_array(arr);

        // 5) π-층: P[i] = (5i+7) mod 16 = [7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2]
        simd_swizzle!(v, [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2])
    }

    /// SIMD permute. scalar permute와 결과가 비트단위로 일치.
    #[inline]
    pub fn permute_simd(state: &mut [u64; STATE_WORDS], rounds: usize) {
        let mut v = u64x16::from_array(*state);
        for r in 0..rounds {
            v = round_simd(v, r);
        }
        *state = v.to_array();
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use crate::permutation::permute;

        #[test]
        fn simd_matches_scalar() {
            let inputs: [[u64; 16]; 4] = [
                {
                    let mut a = [0u64; 16];
                    a[3] = 1;
                    a
                },
                {
                    let mut a = [0u64; 16];
                    a[7] = 0x1234_5678_9ABC_DEF0;
                    a[0] = 0xDEAD_BEEF_CAFE_BABE;
                    a
                },
                [
                    0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
                    0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000,
                ],
                [u64::MAX; 16],
            ];
            for input in &inputs {
                for &rounds in &[1usize, 8, 16, 24] {
                    let mut a = *input;
                    let mut b = *input;
                    permute(&mut a, rounds);
                    permute_simd(&mut b, rounds);
                    assert_eq!(a, b, "rounds={} input={:?}", rounds, input);
                }
            }
        }
    }
}

// ---- Stable: 임시 fallback (scalar로 직접 호출) ----
//
// TODO: per-arch intrinsics 또는 wide crate 기반 stable SIMD.

#[cfg(all(ysc4_simd_stable, not(ysc4_simd_nightly)))]
mod stable_fallback {
    use crate::consts::STATE_WORDS;
    use crate::permutation::permute;

    pub fn permute_simd(state: &mut [u64; STATE_WORDS], rounds: usize) {
        permute(state, rounds);
    }
}
