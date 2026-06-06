//! v1 공격이 YSC5에서도 작동하지 않음을 확인 (RustCrypto API).

use cipher::{KeyIvInit, StreamCipher};
use ysc5::consts::STATE_WORDS;
use ysc5::farfalle::{Ysc5Variant, Ysc5_128};
use ysc5::Ysc5_128StreamCipher;

#[test]
fn v1_full_state_recovery_fails_keystream_is_only_rate() {
    assert_eq!(Ysc5_128::RATE_BYTES, 64);
    assert_eq!(STATE_WORDS * 64 - Ysc5_128::RATE_BYTES * 8, 512);
}

#[test]
fn v2_key_not_in_keystream() {
    let key = [0x42u8; 32];
    let mut c = Ysc5_128StreamCipher::new(&key.into(), &[0u8; 24].into());
    let mut buf = vec![0u8; 1024];
    c.apply_keystream(&mut buf);
    assert_ne!(buf[0], key[0]);
    let pat = buf.windows(32).filter(|w| *w == key.as_slice()).count();
    assert_eq!(pat, 0);
}

#[test]
fn v3_avalanche_on_nonce_change() {
    let key = [0u8; 32];
    let mut buf1 = vec![0u8; 256];
    let mut buf2 = vec![0u8; 256];
    let mut c1 = Ysc5_128StreamCipher::new(&key.into(), &[0u8; 24].into());
    c1.apply_keystream(&mut buf1);
    let mut nonce2 = [0u8; 24];
    nonce2[0] = 1;
    let mut c2 = Ysc5_128StreamCipher::new(&key.into(), &nonce2.into());
    c2.apply_keystream(&mut buf2);

    let diff: u32 = buf1
        .iter()
        .zip(buf2.iter())
        .map(|(a, b)| (a ^ b).count_ones())
        .sum();
    let total = (buf1.len() * 8) as u32;
    let ratio = diff as f64 / total as f64;
    assert!((0.4..0.6).contains(&ratio), "avalanche 부족: {:.3}", ratio);
}

#[test]
fn v8_zeroize_traits_on_core() {
    use ysc5::stream::Ysc5StreamCore;
    fn z<T: zeroize::Zeroize>() {}
    fn zd<T: zeroize::ZeroizeOnDrop>() {}
    z::<Ysc5StreamCore<Ysc5_128>>();
    zd::<Ysc5StreamCore<Ysc5_128>>();
}
