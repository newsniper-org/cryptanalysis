//! YSC5에서도 v1 공격 모음이 작동하지 않음을 확인.

use ysc5::consts::STATE_WORDS;
use ysc5::farfalle::{Ysc5Variant, Ysc5_128};
use ysc5::stream::Ysc5_128Stream;

#[test]
fn v1_full_state_recovery_fails_keystream_is_only_rate() {
    // YSC5-128: rate = 64 byte = 512 bit. 상태는 1024 bit.
    assert_eq!(Ysc5_128::RATE_BYTES, 64);
    assert_eq!(STATE_WORDS * 64 - Ysc5_128::RATE_BYTES * 8, 512);
}

#[test]
fn v2_key_in_capacity_only() {
    // 키스트림이 키와 자명한 상관관계 없음을 약식 확인.
    let key = [0x42u8; 32];
    let cipher = Ysc5_128Stream::new(&key, &[0u8; 24]).unwrap();
    let mut buf = vec![0u8; 1024];
    cipher.apply_keystream(&mut buf);
    // 키 첫 바이트와 키스트림 첫 바이트가 자명히 같지 않은지
    assert_ne!(buf[0], key[0]);
    // 키 32-바이트 패턴이 키스트림에 반복되지 않음
    let pattern_count = buf
        .windows(32)
        .filter(|w| *w == key.as_slice())
        .count();
    assert_eq!(pattern_count, 0, "키가 키스트림에 직접 나타남");
}

#[test]
fn v3_avalanche_on_nonce_change() {
    // Nonce 1비트 변경 → 키스트림 ~50% 변화 기대.
    let key = [0u8; 32];
    let mut buf1 = vec![0u8; 256];
    let mut buf2 = vec![0u8; 256];
    Ysc5_128Stream::new(&key, &[0u8; 24])
        .unwrap()
        .apply_keystream(&mut buf1);
    let mut nonce2 = [0u8; 24];
    nonce2[0] = 1;
    Ysc5_128Stream::new(&key, &nonce2)
        .unwrap()
        .apply_keystream(&mut buf2);

    let diff_bits: u32 = buf1
        .iter()
        .zip(buf2.iter())
        .map(|(a, b)| (a ^ b).count_ones())
        .sum();
    let total_bits = (buf1.len() * 8) as u32;
    let ratio = diff_bits as f64 / total_bits as f64;
    // 0.4 ~ 0.6 사이 (이상치 0.5)
    assert!(
        (0.4..0.6).contains(&ratio),
        "avalanche 부족: {} / {} ({:.3})",
        diff_bits,
        total_bits,
        ratio
    );
}

#[test]
fn v8_zeroize_on_drop() {
    fn z<T: zeroize::Zeroize>() {}
    fn zd<T: zeroize::ZeroizeOnDrop>() {}
    z::<Ysc5_128Stream>();
    zd::<Ysc5_128Stream>();
}
