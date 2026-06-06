//! Optional SIMD backend (nightly only).
//!
//! `feature = "simd"` 활성화 시 컴파일됨. `core::simd` (`portable_simd`) 사용.
//! Farfalle의 16-branch broadcast가 `u64x8 × 2` 또는 `u64x4 × 4`에 자연 매핑.
//!
//! 본 backend는 *기능적*으로 soft backend와 *동일*해야 함. SPEC 정의가 산술적으로 일관.

#![cfg(feature = "simd")]

use crate::consts::STATE_WORDS;
use core::simd::{u64x4, Simd};

/// 16-워드 상태를 4개 u64x4 SIMD 벡터로 표현.
///
/// `state[0..4]`, `state[4..8]`, `state[8..12]`, `state[12..16]` 각각이 u64x4.
pub type SimdState = [u64x4; 4];

/// state 슬라이스 → SIMD 벡터 4개.
#[inline(always)]
pub fn load_simd(state: &[u64; STATE_WORDS]) -> SimdState {
    [
        u64x4::from_slice(&state[0..4]),
        u64x4::from_slice(&state[4..8]),
        u64x4::from_slice(&state[8..12]),
        u64x4::from_slice(&state[12..16]),
    ]
}

/// SIMD 벡터 4개 → state 슬라이스.
#[inline(always)]
pub fn store_simd(simd: &SimdState, state: &mut [u64; STATE_WORDS]) {
    simd[0].copy_to_slice(&mut state[0..4]);
    simd[1].copy_to_slice(&mut state[4..8]);
    simd[2].copy_to_slice(&mut state[8..12]);
    simd[3].copy_to_slice(&mut state[12..16]);
}

/// 16 워드의 XOR-reduce를 SIMD-병렬로 계산.
///
/// `T = ⊕ᵢ state[i] = (((s0 ⊕ s1) ⊕ s2) ⊕ s3)의 horizontal XOR-fold.`
#[inline(always)]
pub fn xor_reduce_simd(simd: &SimdState) -> u64 {
    // step 1: 4 lane-wise XOR → 단일 u64x4
    let v: u64x4 = simd[0] ^ simd[1] ^ simd[2] ^ simd[3];
    // step 2: u64x4의 4 lane을 horizontal XOR
    let arr = v.to_array();
    arr[0] ^ arr[1] ^ arr[2] ^ arr[3]
}

/// T를 모든 16 워드에 broadcast XOR.
#[inline(always)]
pub fn broadcast_simd(simd: &mut SimdState, t: u64) {
    let t_splat = u64x4::splat(t);
    for v in simd.iter_mut() {
        *v ^= t_splat;
    }
}

/// γ roll의 SIMD 변종 — branch별 distinct α-거듭제곱.
///
/// 본 구현은 각 워드의 α-mult을 독립 적용. 완전 벡터화하려면 mask + select 조합 필요.
#[inline]
pub fn roll_simd(simd: &mut SimdState) {
    // simd[0] = (state[0], state[1], state[2], state[3])
    //   → (α·s0, α²·s1, α³·s2, α⁴·s3)
    // simd[1] = (s4..s7) → (α⁵·s4, ..., α⁸·s7)
    // simd[2] = (s8..s11) → (α⁹·s8, ..., α¹²·s11)
    // simd[3] = (s12..s15) → (α¹³·s12, ..., α¹⁶·s15)

    let mut arr0 = simd[0].to_array();
    let mut arr1 = simd[1].to_array();
    let mut arr2 = simd[2].to_array();
    let mut arr3 = simd[3].to_array();

    for (i, e) in arr0.iter_mut().enumerate() {
        *e = ysc4::gf2_64::alpha_pow(*e, (i + 1) as u32);
    }
    for (i, e) in arr1.iter_mut().enumerate() {
        *e = ysc4::gf2_64::alpha_pow(*e, (i + 5) as u32);
    }
    for (i, e) in arr2.iter_mut().enumerate() {
        *e = ysc4::gf2_64::alpha_pow(*e, (i + 9) as u32);
    }
    for (i, e) in arr3.iter_mut().enumerate() {
        *e = ysc4::gf2_64::alpha_pow(*e, (i + 13) as u32);
    }

    simd[0] = u64x4::from_array(arr0);
    simd[1] = u64x4::from_array(arr1);
    simd[2] = u64x4::from_array(arr2);
    simd[3] = u64x4::from_array(arr3);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::roll;

    #[test]
    fn simd_roll_matches_soft() {
        let mut soft = [0u64; STATE_WORDS];
        for i in 0..STATE_WORDS {
            soft[i] = 0x9E37_79B9_7F4A_7C15u64.wrapping_mul(i as u64 + 1);
        }
        let mut simd_state = load_simd(&soft);

        roll::roll(&mut soft);
        roll_simd(&mut simd_state);

        let mut from_simd = [0u64; STATE_WORDS];
        store_simd(&simd_state, &mut from_simd);

        assert_eq!(soft, from_simd, "SIMD roll이 soft와 다른 결과");
    }

    #[test]
    fn xor_reduce_simd_matches_naive() {
        let state = [0x1234_5678_9ABC_DEF0u64; 16];
        let simd_state = load_simd(&state);
        let r = xor_reduce_simd(&simd_state);
        let expected = state.iter().fold(0u64, |a, &b| a ^ b);
        assert_eq!(r, expected);
    }
}
