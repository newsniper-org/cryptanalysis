//! YSC3-p 순열. 사양 §2.
//!
//! 모든 함수는 *상수시간* 보장:
//! - 분기 없음 (`r is even` 분기는 라운드 인덱스에만 의존; 비밀과 무관)
//! - 메모리 접근이 비밀-비종속
//! - 회전·시프트량이 컴파일 타임 상수

use crate::consts::{R0, R1, R2, R3, RC, STATE_WORDS};

/// H 함수. 사양 §2.1: `H(x, y) = x ⊕ y ⊕ ((x ∧ y) ≪ 1)`.
#[inline(always)]
pub fn h(x: u64, y: u64) -> u64 {
    x ^ y ^ ((x & y) << 1)
}

/// Quarter round. 사양 §2.2.
#[inline(always)]
pub fn quarter_round(a: &mut u64, b: &mut u64, c: &mut u64, d: &mut u64) {
    *a = h(*a, *b);
    *d = (*d ^ *a).rotate_left(R0);
    *c = h(*c, *d);
    *b = (*b ^ *c).rotate_left(R1);
    *a = h(*a, *b);
    *d = (*d ^ *a).rotate_left(R2);
    *c = h(*c, *d);
    *b = (*b ^ *c).rotate_left(R3);
}

#[inline(always)]
fn qr_at(s: &mut [u64; STATE_WORDS], i0: usize, i1: usize, i2: usize, i3: usize) {
    let mut a = s[i0];
    let mut b = s[i1];
    let mut c = s[i2];
    let mut d = s[i3];
    quarter_round(&mut a, &mut b, &mut c, &mut d);
    s[i0] = a;
    s[i1] = b;
    s[i2] = c;
    s[i3] = d;
}

/// Column round — 짝수 라운드. 사양 §2.4.
#[inline(always)]
fn column_round(s: &mut [u64; STATE_WORDS]) {
    qr_at(s, 0, 4, 8, 12);
    qr_at(s, 1, 5, 9, 13);
    qr_at(s, 2, 6, 10, 14);
    qr_at(s, 3, 7, 11, 15);
}

/// Diagonal round — 홀수 라운드. 사양 §2.4.
#[inline(always)]
fn diagonal_round(s: &mut [u64; STATE_WORDS]) {
    qr_at(s, 0, 5, 10, 15);
    qr_at(s, 1, 6, 11, 12);
    qr_at(s, 2, 7, 8, 13);
    qr_at(s, 3, 4, 9, 14);
}

/// ι: 라운드 상수 주입. 사양 §2.3.
#[inline(always)]
fn iota(s: &mut [u64; STATE_WORDS], r: usize) {
    let rc = RC[r & 15];
    if r & 1 == 0 {
        s[0] ^= rc;
    } else {
        s[15] ^= rc;
    }
}

/// YSC3-p 순열. 사양 §2.4.
///
/// `rounds`는 column/diagonal **합산** 라운드 수. 짝수가 권장 (full double-round).
#[inline]
pub fn permute(state: &mut [u64; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        iota(state, r);
        if r & 1 == 0 {
            column_round(state);
        } else {
            diagonal_round(state);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn h_is_correct_for_zero_inputs() {
        assert_eq!(h(0, 0), 0);
        assert_eq!(h(0, 0xDEAD_BEEF_CAFE_BABE), 0xDEAD_BEEF_CAFE_BABE);
    }

    #[test]
    fn h_approximates_addition_lsb() {
        for x in [0u64, 1, 2, 3, 0x5555_5555_5555_5555, 0xFFFF_FFFF_FFFF_FFFF] {
            for y in [0u64, 1, 2, 3, 0x5555_5555_5555_5555, 0xFFFF_FFFF_FFFF_FFFF] {
                let h_val = h(x, y);
                let add_val = x.wrapping_add(y);
                assert_eq!(h_val & 0b11, add_val & 0b11, "x={:#x}, y={:#x}", x, y);
            }
        }
    }

    #[test]
    fn permute_changes_state() {
        let mut s = [0u64; 16];
        s[0] = 1;
        permute(&mut s, 12);
        assert!(s.iter().any(|&w| w != 0));
        let mut s2 = [0u64; 16];
        s2[0] = 1;
        permute(&mut s2, 24);
        assert_ne!(s, s2);
    }

    #[test]
    fn permute_diffuses_avalanche() {
        // 1비트 차이가 6 더블 라운드(12 라운드) 후 ~512비트 차이로 확산해야 한다.
        let mut a = [0u64; 16];
        let mut b = [0u64; 16];
        a[5] = 0x1234_5678_9ABC_DEF0;
        b[5] = a[5] ^ 1;
        permute(&mut a, 12);
        permute(&mut b, 12);
        let diff_bits: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
        assert!(
            (256..=768).contains(&diff_bits),
            "avalanche 부족: diff_bits={}",
            diff_bits
        );
    }
}
