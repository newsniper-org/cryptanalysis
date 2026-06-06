//! YSC5 기본 round-trip 테스트.

use ysc5::stream::{Ysc5_128Stream, Ysc5_256Stream};

#[test]
fn empty_buffer() {
    let cipher = Ysc5_128Stream::new(&[0u8; 32], &[0u8; 24]).unwrap();
    let mut buf: Vec<u8> = vec![];
    cipher.apply_keystream(&mut buf);
    assert!(buf.is_empty());
}

#[test]
fn single_byte() {
    let cipher = Ysc5_128Stream::new(&[1u8; 32], &[2u8; 24]).unwrap();
    let mut buf = vec![0x42u8];
    cipher.apply_keystream(&mut buf);
    assert_ne!(buf[0], 0x42);
    cipher.apply_keystream(&mut buf);
    assert_eq!(buf[0], 0x42);
}

#[test]
fn multiple_block_lengths() {
    for size in [1usize, 63, 64, 65, 127, 128, 129, 1023, 1024] {
        let cipher = Ysc5_128Stream::new(&[0xAA; 32], &[0xBB; 24]).unwrap();
        let pt: Vec<u8> = (0..size).map(|i| (i & 0xFF) as u8).collect();
        let mut buf = pt.clone();
        cipher.apply_keystream(&mut buf);
        assert_ne!(buf, pt, "size {} ciphertext == plaintext", size);
        cipher.apply_keystream(&mut buf);
        assert_eq!(buf, pt, "size {} round-trip failed", size);
    }
}

#[test]
fn variant_256_roundtrip() {
    let cipher = Ysc5_256Stream::new(&[0xCC; 64], &[0xDD; 24]).unwrap();
    let pt = b"YSC5-256 with 512-bit key, 256-bit rate" as &[u8];
    let mut buf = pt.to_vec();
    cipher.apply_keystream(&mut buf);
    cipher.apply_keystream(&mut buf);
    assert_eq!(&buf[..], pt);
}

#[test]
fn same_key_different_nonce_diverges() {
    let key = [0u8; 32];
    let mut a = vec![0u8; 256];
    let mut b = vec![0u8; 256];
    Ysc5_128Stream::new(&key, &[0u8; 24])
        .unwrap()
        .apply_keystream(&mut a);
    Ysc5_128Stream::new(&key, &[1u8; 24])
        .unwrap()
        .apply_keystream(&mut b);
    assert_ne!(a, b);
}
