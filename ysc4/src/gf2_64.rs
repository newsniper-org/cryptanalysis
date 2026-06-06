//! GF(2⁶⁴) 위 `α-곱`. 사양 §1.2.
//!
//! 표현: `GF(2)[x] / (x⁶⁴ + x⁴ + x³ + x + 1)`. 감소 상수 `0x1B`.

/// 감소 다항식의 저차항: `x⁴ + x³ + x + 1`.
pub const REDUCTION: u64 = 0x1B;

/// `α · y` — 즉 GF(2⁶⁴)에서 `y`를 `x`만큼 곱한 결과.
///
/// 상수 시간:
/// - 분기 없음
/// - 데이터 종속 메모리 접근 없음
/// - FHE에서는 plaintext-mult: 상수와의 AND만 발생 (부트스트래핑 불필요).
#[inline(always)]
pub fn alpha(y: u64) -> u64 {
    // 최상위 비트가 1이면 0xFF…FF, 아니면 0.
    let mask = 0u64.wrapping_sub(y >> 63);
    (y << 1) ^ (mask & REDUCTION)
}

/// `αᵏ · y`. 단순 반복 — `k`는 라운드 상수, 작은 값이라 추가 최적화 불요.
#[inline]
pub fn alpha_pow(mut y: u64, k: u32) -> u64 {
    for _ in 0..k {
        y = alpha(y);
    }
    y
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alpha_is_bijection_small_sample() {
        // 표본 16개 입력으로 출력이 모두 다름을 확인 (작은 검증).
        let mut outputs = std::collections::BTreeSet::new();
        for i in 0u64..256 {
            let y = i.wrapping_mul(0x9E37_79B9_7F4A_7C15);
            assert!(outputs.insert(alpha(y)), "collision on input {:#x}", y);
        }
    }

    #[test]
    fn alpha_plus_identity_is_bijection_small_sample() {
        // Orthomorphism 조건의 두 번째 부분: `y ↦ y ⊕ α·y`가 bijection.
        let mut outputs = std::collections::BTreeSet::new();
        for i in 0u64..256 {
            let y = i.wrapping_mul(0xC6BC_2796_92B5_C323);
            let out = y ^ alpha(y);
            assert!(outputs.insert(out), "(α+1) collision on input {:#x}", y);
        }
    }

    #[test]
    fn alpha_pow_matches_iteration() {
        let y = 0xDEAD_BEEF_CAFE_BABE;
        let mut acc = y;
        for k in 0..16 {
            assert_eq!(alpha_pow(y, k), acc);
            acc = alpha(acc);
        }
    }

    #[test]
    fn alpha_distinct_powers() {
        // α¹, α³, α⁵, α⁷ — σ-층에 쓰는 4개 거듭제곱이 서로 다른 GF(2⁶⁴) 원소를 곱함.
        // 즉 같은 입력에 대해 모두 다른 출력을 줘야 함.
        let y = 0x0123_4567_89AB_CDEF;
        let outs: [u64; 4] = [alpha_pow(y, 1), alpha_pow(y, 3), alpha_pow(y, 5), alpha_pow(y, 7)];
        for i in 0..4 {
            for j in (i + 1)..4 {
                assert_ne!(outs[i], outs[j], "powers {} and {} collide", i, j);
            }
        }
    }
}
