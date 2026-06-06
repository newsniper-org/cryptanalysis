//! GF(2³²) α-곱. SPEC §2.

/// Polynomial: x³² + x²² + x² + x + 1.
/// Reduction low: x²² + x² + x + 1 = 0x400007 = 4_194_311.
pub const REDUCTION: u32 = 0x40_0007;

/// `α · y` = GF(2³²) multiplication by x.
#[inline(always)]
pub fn alpha(y: u32) -> u32 {
    let mask = 0u32.wrapping_sub(y >> 31);
    (y << 1) ^ (mask & REDUCTION)
}

/// `αᵏ · y`.
#[inline]
pub fn alpha_pow(mut y: u32, k: u32) -> u32 {
    for _ in 0..k {
        y = alpha(y);
    }
    y
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alpha_of_one() {
        // α · 1 = α (binary 10)
        assert_eq!(alpha(1), 2);
    }

    #[test]
    fn alpha_of_high_bit() {
        // α · 2^31: top bit shifts out → reduction XORed
        let r = alpha(0x8000_0000);
        // (0x8000_0000 << 1) = 0 (truncated), then XOR reduction
        assert_eq!(r, REDUCTION);
    }

    #[test]
    fn alpha_pow_4() {
        // α^4 = 16 (assuming no reduction triggered, which is true for small powers)
        assert_eq!(alpha_pow(1, 4), 16);
    }
}
