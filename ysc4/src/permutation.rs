//! YSC3-p2 순열 (σ-Generalized Lai-Massey). 사양 §2.

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P, RC, STATE_WORDS};
use crate::gf2_64::alpha_pow;

/// F 함수: 사양 §1.3.
///
/// `F(s) = s ⊕ (rot(s,13) ∧ rot(s,37)) ⊕ (rot(s,5) ∧ rot(s,23))`
///
/// - AND 게이트 128 (= 2 × 64)
/// - 알고리즘 차수 2
/// - 모든 회전량이 64와 서로소이며 mod 64 distinct.
#[inline(always)]
pub fn f(s: u64) -> u64 {
    s ^ (s.rotate_left(F_ROT_A) & s.rotate_left(F_ROT_B))
      ^ (s.rotate_left(F_ROT_C) & s.rotate_left(F_ROT_D))
}

/// 전체 branch XOR 축약.
#[inline(always)]
fn xor_reduce(state: &[u64; STATE_WORDS]) -> u64 {
    let mut s = 0u64;
    for &w in state.iter() {
        s ^= w;
    }
    s
}

/// σ-층. 사양 §1.5: branches {0,4,8,12}에 α¹, α³, α⁵, α⁷.
#[inline(always)]
fn sigma_layer(state: &mut [u64; STATE_WORDS]) {
    state[0]  = alpha_pow(state[0],  1);
    state[4]  = alpha_pow(state[4],  3);
    state[8]  = alpha_pow(state[8],  5);
    state[12] = alpha_pow(state[12], 7);
}

/// π 워드 순열. 사양 §1.4.
#[inline(always)]
fn pi_layer(state: &mut [u64; STATE_WORDS]) {
    let mut new = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        new[i] = state[P[i]];
    }
    *state = new;
}

/// YSC3-p2 라운드 한 번. 사양 §2.
#[inline(always)]
fn round(state: &mut [u64; STATE_WORDS], r: usize) {
    // 1) ι: state[r mod 16] ⊕= RC[r mod 16]
    let pos = r & 15;
    state[pos] ^= RC[pos];

    // 2) S = ⊕ᵢ state[i],  T = F(S)
    let s = xor_reduce(state);
    let t = f(s);

    // 3) broadcast
    for w in state.iter_mut() {
        *w ^= t;
    }

    // 4) σ-층
    sigma_layer(state);

    // 5) π
    pi_layer(state);
}

/// YSC3-p2 순열 — scalar 구현 (테스트 및 fallback용 항상 노출).
#[inline]
pub fn permute_scalar(state: &mut [u64; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        round(state, r);
    }
}

/// YSC3-p2 순열 (단일 상태).
///
/// SIMD 가속은 *단일 순열*이 아니라 leaf의 *블록 batch*(Level B,
/// `permutation_simd::permute_batch`)에 적용된다. 단일 호출은 항상 scalar.
#[inline]
pub fn permute(state: &mut [u64; STATE_WORDS], rounds: usize) {
    permute_scalar(state, rounds);
}

/// *broadcast-only 변종 (σ 없음).* 사양 §5의 invariant 차단 검증용.
///
/// 이는 사양 정의가 *아니다* — 단지 σ-층이 없으면 invariant가 보존됨을
/// 직접 보이기 위한 reference variant.
#[doc(hidden)]
pub fn permute_without_sigma(state: &mut [u64; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        let pos = r & 15;
        state[pos] ^= RC[pos];
        let s = xor_reduce(state);
        let t = f(s);
        for w in state.iter_mut() {
            *w ^= t;
        }
        pi_layer(state);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn f_basic() {
        // F(0) = 0
        assert_eq!(f(0), 0);
        // F의 차분: 1비트 입력 차이가 출력에서 ~8비트 활성화되어야 함.
        let d_out = f(0) ^ f(1);
        let hw = d_out.count_ones();
        assert!(hw >= 1, "F는 입력 변화에 반응해야 함");
        assert!(hw <= 32, "F의 단일 비트 차분이 비현실적으로 크다: {}", hw);
    }

    #[test]
    fn permute_changes_state() {
        let mut s = [0u64; STATE_WORDS];
        s[3] = 1;
        permute(&mut s, 16);
        assert!(s.iter().any(|&w| w != 0));
    }

    #[test]
    fn avalanche_after_16_rounds() {
        let mut a = [0u64; STATE_WORDS];
        let mut b = [0u64; STATE_WORDS];
        a[7] = 0x1234_5678_9ABC_DEF0;
        b[7] = a[7] ^ 1;
        permute(&mut a, 16);
        permute(&mut b, 16);

        let diff: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
        assert!(
            (300..=724).contains(&diff),
            "avalanche 비트 수가 비정상: diff_bits={}",
            diff
        );
    }
}
