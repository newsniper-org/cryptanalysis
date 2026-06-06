//! v0.1과 동일한 attacker model로 v0.2도 무너지지 않음을 확인.

use ysc4::consts::STATE_WORDS;
use ysc4::permutation::permute;
use ysc4::stream::{Ysc4Variant, Ysc4_128, Ysc4_128Stream};

#[test]
fn v1_full_state_recovery_fails_keystream_is_half_state() {
    assert_eq!(Ysc4_128::RATE_BYTES, 64);
    assert_eq!(Ysc4_128::RATE_WORDS, 8);

    let key = [0x55u8; 32];
    let nonce = [0xAAu8; 24];
    let cipher = Ysc4_128Stream::new(&key, &nonce).unwrap();

    let mut ks = vec![0u8; Ysc4_128::RATE_BYTES];
    cipher.keystream_block(1, &mut ks);

    let rate_bits = ks.len() * 8;
    let state_bits = STATE_WORDS * 64;
    assert_eq!(state_bits - rate_bits, 512);
}

#[test]
fn v3_permutation_is_not_affine() {
    let zero = [0u64; STATE_WORDS];
    let mut p0 = zero;
    permute(&mut p0, 16);

    let mut x = [0u64; STATE_WORDS];
    let mut y = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        x[i] = 0x9E37_79B9_7F4A_7C15u64.wrapping_mul(i as u64 + 1);
        y[i] = 0xC6BC_2796_92B5_C323u64.wrapping_mul(i as u64 + 7);
    }
    let mut z = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        z[i] = x[i] ^ y[i];
    }

    let mut px = x;
    let mut py = y;
    let mut pz = z;
    permute(&mut px, 16);
    permute(&mut py, 16);
    permute(&mut pz, 16);

    let mut violation: u32 = 0;
    for i in 0..STATE_WORDS {
        violation += (px[i] ^ py[i] ^ pz[i] ^ p0[i]).count_ones();
    }
    assert!(
        violation > 256,
        "affine처럼 보임: violation={}",
        violation
    );
    eprintln!("[info] v0.2 affinity 위반 비트 = {} / 1024", violation);
}

#[test]
fn v5_avalanche_is_strong() {
    let mut a = [0u64; STATE_WORDS];
    let mut b = [0u64; STATE_WORDS];
    a[7] = 0xDEAD_BEEF_CAFE_BABE;
    b[7] = a[7] ^ 1;
    permute(&mut a, 16);
    permute(&mut b, 16);

    let diff: u32 = a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum();
    assert!(
        (256..=768).contains(&diff),
        "avalanche 부족: diff={}",
        diff
    );
}

#[test]
fn v8_zeroize_on_drop() {
    fn assert_zeroize<T: zeroize::Zeroize>() {}
    fn assert_zod<T: zeroize::ZeroizeOnDrop>() {}
    assert_zeroize::<Ysc4_128Stream>();
    assert_zod::<Ysc4_128Stream>();
}
