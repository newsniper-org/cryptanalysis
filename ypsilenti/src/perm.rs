//! ypsilenti 순열 (8×u32 σ-GLM). SPEC §3, §5, §6.

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P_PI, RC, STATE_WORDS};
use crate::gf32::alpha_pow;

pub type State = [u32; STATE_WORDS];

/// F 함수: u32 변종.
#[inline(always)]
pub fn f(s: u32) -> u32 {
    s ^ (s.rotate_left(F_ROT_A) & s.rotate_left(F_ROT_B))
      ^ (s.rotate_left(F_ROT_C) & s.rotate_left(F_ROT_D))
}

#[inline(always)]
fn xor_reduce(state: &State) -> u32 {
    state.iter().fold(0u32, |a, &w| a ^ w)
}

#[inline(always)]
fn sigma_layer(state: &mut State) {
    state[0] = alpha_pow(state[0], 1);
    state[4] = alpha_pow(state[4], 3);
}

#[inline(always)]
fn pi_layer(state: &mut State) {
    let mut new = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        new[i] = state[P_PI[i]];
    }
    *state = new;
}

#[inline(always)]
fn round(state: &mut State, r: usize) {
    state[r & 7] ^= RC[r & 7];
    let s = xor_reduce(state);
    let t = f(s);
    for w in state.iter_mut() {
        *w ^= t;
    }
    sigma_layer(state);
    pi_layer(state);
}

/// ypsilenti 순열 — scalar 구현 (테스트 및 fallback용 항상 노출).
#[inline]
pub fn permute_scalar(state: &mut State, rounds: usize) {
    for r in 0..rounds {
        round(state, r);
    }
}

/// ypsilenti 순열 — dispatcher.
/// `ypsi_simd_any` cfg 활성화 시 SIMD 경로로, 아니면 scalar로.
#[cfg(not(ypsi_simd_any))]
#[inline]
pub fn permute(state: &mut State, rounds: usize) {
    permute_scalar(state, rounds);
}

#[cfg(ypsi_simd_any)]
#[inline]
pub fn permute(state: &mut State, rounds: usize) {
    crate::perm_simd::permute_simd(state, rounds);
}

/// Mask seed (16 byte = 4 × u32)를 state로 packing 후 IV XOR + permute.
#[inline]
pub fn derive_mask(seed: &[u8; 16], iv: &State) -> State {
    let mut s = *iv;
    for i in 0..4 {
        let w = u32::from_le_bytes(seed[i * 4..(i + 1) * 4].try_into().unwrap());
        s[i] ^= w;
    }
    permute(&mut s, crate::consts::rounds::MASK_DERIVE);
    s
}

/// 블록을 mask와 XOR 후 permute.
#[inline]
pub fn compress_block(block: &[u8; 32], mask: &State, rounds: usize) -> State {
    let mut s = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let w = u32::from_le_bytes(block[i * 4..(i + 1) * 4].try_into().unwrap());
        s[i] = w ^ mask[i];
    }
    permute(&mut s, rounds);
    s
}

/// Finalize: state ⊕ mask_mid → permute.
#[inline]
pub fn finalize(state: &State, mask_mid: &State) -> State {
    let mut s = *state;
    for i in 0..STATE_WORDS {
        s[i] ^= mask_mid[i];
    }
    permute(&mut s, crate::consts::rounds::FINALIZE);
    s
}

/// CV (16 byte) 추출 — state의 처음 4 워드.
#[inline]
pub fn truncate_cv(state: &State) -> [u8; 16] {
    let mut cv = [0u8; 16];
    for i in 0..4 {
        cv[i * 4..(i + 1) * 4].copy_from_slice(&state[i].to_le_bytes());
    }
    cv
}

#[inline]
pub fn cv_to_state(cv: &[u8; 16]) -> State {
    let mut s = [0u32; STATE_WORDS];
    for i in 0..4 {
        s[i] = u32::from_le_bytes(cv[i * 4..(i + 1) * 4].try_into().unwrap());
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn permute_changes_state() {
        let mut s = [0u32; STATE_WORDS];
        s[0] = 1;
        permute(&mut s, 4);
        assert!(s.iter().any(|&w| w != 0));
    }

    #[test]
    fn permute_avalanche() {
        let mut a = [0u32; STATE_WORDS];
        let mut b = [0u32; STATE_WORDS];
        a[3] = 0xDEAD_BEEF;
        b[3] = 0xDEAD_BEEE;
        permute(&mut a, 4);
        permute(&mut b, 4);
        let diff: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
        // 256-bit 상태에 ~128 비트 이상 차이
        assert!((50..=200).contains(&diff), "avalanche: {}/256", diff);
    }
}
