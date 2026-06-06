//! Farfalle mask-roll γ. SPEC §9.
//!
//! γ((k_0, k_1, …, k_15)) := (α^1·k_0, α^2·k_1, …, α^16·k_15).
//! 워드별 distinct α-거듭제곱. YSC4의 GF(2⁶⁴) α-mult 재사용.

use crate::consts::STATE_WORDS;
use ysc4::gf2_64::alpha;

/// γ를 단일 적용 (in-place). 각 워드 i를 α^(i+1)만큼 곱한다.
///
/// 구현은 효율을 위해 α-mult을 누적: word 0은 1회, word 1은 2회, …, word 15는 16회.
/// 총 136 α-mult 호출 = 136 × (shift + masked-XOR) = 약 500 u64 ops.
#[inline]
pub fn roll(state: &mut [u64; STATE_WORDS]) {
    for i in 0..STATE_WORDS {
        // word i에 α^(i+1) 적용 = α-mult를 (i+1)회 반복
        let times = (i + 1) as u32;
        let mut y = state[i];
        for _ in 0..times {
            y = alpha(y);
        }
        state[i] = y;
    }
}

/// roll을 `n`회 적용한 결과. 즉 γ^n.
///
/// 효율: roll을 n번 단순 반복. 큰 n에 대해서는 추가 최적화 가능
/// (각 워드에 대해 α^(n(i+1))을 직접 계산하는 식). 본 참조 구현은 단순함을 우선.
#[inline]
pub fn roll_n(state: &mut [u64; STATE_WORDS], n: u64) {
    for _ in 0..n {
        roll(state);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roll_changes_all_words() {
        let mut s = [1u64; 16];
        let before = s;
        roll(&mut s);
        for i in 0..16 {
            // 모든 워드가 변해야 함 (1 != α^(i+1) · 1 for i+1 ≥ 1)
            assert_ne!(s[i], before[i], "word {} unchanged", i);
        }
    }

    #[test]
    fn roll_is_bijection_small_sample() {
        // 0이 아닌 입력에 대해 roll(x) ≠ 0
        let mut s = [0u64; 16];
        s[3] = 0x1234_5678_9ABC_DEF0;
        roll(&mut s);
        assert!(s.iter().any(|&w| w != 0));
    }

    #[test]
    fn roll_n_matches_iteration() {
        let mut s1 = [0u64; 16];
        s1[5] = 0xDEAD_BEEF_CAFE_BABE;
        let mut s2 = s1;

        for _ in 0..7 {
            roll(&mut s1);
        }
        roll_n(&mut s2, 7);

        assert_eq!(s1, s2);
    }
}
