//! ypsilenti 순열 — Level A SIMD (intra-P) 구현.
//!
//! 상태 8×u32 = 256-bit를 단일 SIMD 레지스터로 처리.
//! - nightly: `core::simd::u32x8` (portable_simd)
//! - stable: 미구현 (TODO: wide crate 또는 per-arch intrinsics)
//!
//! 동일 알고리즘이므로 scalar perm.rs와 비트단위로 일치해야 한다.

#[cfg(ypsi_simd_nightly)]
pub use nightly::permute_simd;

#[cfg(all(ypsi_simd_stable, not(ypsi_simd_nightly)))]
pub use stable_fallback::permute_simd;

// ---- Nightly: core::simd 기반 ----

#[cfg(ypsi_simd_nightly)]
mod nightly {
    use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, RC, STATE_WORDS};
    use crate::gf32::alpha_pow;
    use core::simd::num::SimdUint;
    use core::simd::{simd_swizzle, u32x8};

    type State = [u32; STATE_WORDS];

    /// F 함수 — scalar (단일 u32에 적용).
    #[inline(always)]
    fn f_scalar(s: u32) -> u32 {
        s ^ (s.rotate_left(F_ROT_A) & s.rotate_left(F_ROT_B))
          ^ (s.rotate_left(F_ROT_C) & s.rotate_left(F_ROT_D))
    }

    /// 8-lane state를 SIMD 벡터로 round 처리.
    #[inline]
    fn round_simd(v: u32x8, r: usize) -> u32x8 {
        // 1) RC XOR at position r&7 (lane-specific)
        //    one-hot RC vector를 만들어 XOR
        let pos = r & 7;
        let mut rc_v = [0u32; 8];
        rc_v[pos] = RC[pos];
        let v = v ^ u32x8::from_array(rc_v);

        // 2) reduce XOR → scalar s, t = f(s)
        let s = v.reduce_xor();
        let t = f_scalar(s);

        // 3) broadcast XOR t
        let v = v ^ u32x8::splat(t);

        // 4) σ-layer: lane 0에 α^1, lane 4에 α^3
        let mut arr = v.to_array();
        arr[0] = alpha_pow(arr[0], 1);
        arr[4] = alpha_pow(arr[4], 3);
        let v = u32x8::from_array(arr);

        // 5) π-layer: P_PI = [7, 4, 1, 6, 3, 0, 5, 2]
        //    simd_swizzle! macro는 컴파일타임 상수 패턴 필요
        simd_swizzle!(v, [7, 4, 1, 6, 3, 0, 5, 2])
    }

    /// SIMD permute. scalar permute와 결과가 비트단위로 일치.
    #[inline]
    pub fn permute_simd(state: &mut State, rounds: usize) {
        let mut v = u32x8::from_array(*state);
        for r in 0..rounds {
            v = round_simd(v, r);
        }
        *state = v.to_array();
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use crate::perm::permute;

        #[test]
        fn simd_matches_scalar() {
            let inputs: [[u32; 8]; 4] = [
                [1, 0, 0, 0, 0, 0, 0, 0],
                [0xDEAD_BEEF, 0xCAFE_BABE, 0, 0, 0, 0, 0, 0],
                [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80],
                [u32::MAX, 0, u32::MAX, 0, u32::MAX, 0, u32::MAX, 0],
            ];
            for input in &inputs {
                for &rounds in &[1usize, 4, 6, 8] {
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
// TODO: wide crate 또는 per-arch intrinsics (x86_64 AVX2, aarch64 NEON, wasm32 simd128)
//       기반의 stable SIMD 구현. 현재는 scalar 코드와 동일하게 동작.

#[cfg(all(ypsi_simd_stable, not(ypsi_simd_nightly)))]
mod stable_fallback {
    use crate::consts::STATE_WORDS;
    use crate::perm::permute;

    pub fn permute_simd(state: &mut [u32; STATE_WORDS], rounds: usize) {
        // 현재는 scalar fallback — Phase B에서 본격 SIMD화 예정.
        permute(state, rounds);
    }
}
