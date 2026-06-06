//! YSC5 기본 round-trip 테스트 (RustCrypto traits).

use cipher::{KeyIvInit, StreamCipher, StreamCipherSeek};
use ysc5::{Ysc5_128StreamCipher, Ysc5_256StreamCipher};

#[test]
fn empty_buffer() {
    let mut cipher = Ysc5_128StreamCipher::new(&[0u8; 32].into(), &[0u8; 24].into());
    let mut buf: Vec<u8> = vec![];
    cipher.apply_keystream(&mut buf);
    assert!(buf.is_empty());
}

#[test]
fn single_byte() {
    let mut cipher = Ysc5_128StreamCipher::new(&[1u8; 32].into(), &[2u8; 24].into());
    let mut buf = vec![0x42u8];
    cipher.apply_keystream(&mut buf);
    assert_ne!(buf[0], 0x42);
    // decrypt = encrypt with same key/iv
    let mut cipher = Ysc5_128StreamCipher::new(&[1u8; 32].into(), &[2u8; 24].into());
    cipher.apply_keystream(&mut buf);
    assert_eq!(buf[0], 0x42);
}

#[test]
fn multiple_block_lengths() {
    for size in [1usize, 63, 64, 65, 127, 128, 129, 1023, 1024] {
        let mut cipher = Ysc5_128StreamCipher::new(&[0xAA; 32].into(), &[0xBB; 24].into());
        let pt: Vec<u8> = (0..size).map(|i| (i & 0xFF) as u8).collect();
        let mut buf = pt.clone();
        cipher.apply_keystream(&mut buf);
        assert_ne!(buf, pt, "size {} ciphertext == plaintext", size);

        let mut cipher = Ysc5_128StreamCipher::new(&[0xAA; 32].into(), &[0xBB; 24].into());
        cipher.apply_keystream(&mut buf);
        assert_eq!(buf, pt, "size {} round-trip failed", size);
    }
}

#[test]
fn variant_256_roundtrip() {
    let mut cipher = Ysc5_256StreamCipher::new(&[0xCC; 64].into(), &[0xDD; 24].into());
    let pt = b"YSC5-256 with 512-bit key, 256-bit rate" as &[u8];
    let mut buf = pt.to_vec();
    cipher.apply_keystream(&mut buf);

    let mut cipher = Ysc5_256StreamCipher::new(&[0xCC; 64].into(), &[0xDD; 24].into());
    cipher.apply_keystream(&mut buf);
    assert_eq!(&buf[..], pt);
}

#[test]
fn same_key_different_nonce_diverges() {
    let key = [0u8; 32];
    let mut a = vec![0u8; 256];
    let mut b = vec![0u8; 256];

    let mut c1 = Ysc5_128StreamCipher::new(&key.into(), &[0u8; 24].into());
    c1.apply_keystream(&mut a);
    let mut c2 = Ysc5_128StreamCipher::new(&key.into(), &[1u8; 24].into());
    c2.apply_keystream(&mut b);
    assert_ne!(a, b);
}

#[test]
fn seek_consistency() {
    let mut c = Ysc5_128StreamCipher::new(&[0x77; 32].into(), &[0x88; 24].into());
    let mut buf_long = vec![0u8; 128];
    c.apply_keystream(&mut buf_long);

    let mut c2 = Ysc5_128StreamCipher::new(&[0x77; 32].into(), &[0x88; 24].into());
    c2.seek(64u64); // 2번째 블록부터
    let mut buf2 = vec![0u8; 64];
    c2.apply_keystream(&mut buf2);

    assert_eq!(&buf_long[64..], &buf2[..]);
}
