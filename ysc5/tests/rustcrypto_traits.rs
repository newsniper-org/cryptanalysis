//! YSC5가 RustCrypto convention의 표준 trait들을 구현함을 명시적으로 확인.

#[cfg(feature = "ysc5x")]
use aead::{Aead, AeadInPlace, KeyInit as AeadKeyInit};
#[cfg(feature = "ysc5x")]
use digest::{ExtendableOutput, Update, XofReader, Mac, KeyInit as MacKeyInit};
use cipher::{KeyIvInit, StreamCipher};

#[test]
fn stream_implements_rustcrypto_traits() {
    fn assert_key_iv_init<T: KeyIvInit>() {}
    fn assert_stream_cipher<T: StreamCipher>() {}
    assert_key_iv_init::<ysc5::Ysc5_128StreamCipher>();
    assert_stream_cipher::<ysc5::Ysc5_128StreamCipher>();
    assert_key_iv_init::<ysc5::Ysc5_256StreamCipher>();
    assert_stream_cipher::<ysc5::Ysc5_256StreamCipher>();
}

#[cfg(feature = "ysc5x")]
#[test]
fn aead_roundtrip_rustcrypto() {
    let aead = ysc5::Ysc5_128Aead::new(&[0x42; 32].into());
    let nonce = [0xBB; 24];
    let mut buf = b"plaintext".to_vec();
    let tag = aead
        .encrypt_in_place_detached(&nonce.into(), b"ad", &mut buf)
        .unwrap();
    aead.decrypt_in_place_detached(&nonce.into(), b"ad", &mut buf, &tag)
        .unwrap();
    assert_eq!(&buf[..], b"plaintext");
}

#[cfg(feature = "ysc5x")]
#[test]
fn aead_tag_tamper_detected() {
    let aead = ysc5::Ysc5_128Aead::new(&[0x11; 32].into());
    let mut buf = b"secret".to_vec();
    let mut tag = aead
        .encrypt_in_place_detached(&[0u8; 24].into(), b"", &mut buf)
        .unwrap();
    tag[0] ^= 1;
    assert!(aead
        .decrypt_in_place_detached(&[0u8; 24].into(), b"", &mut buf, &tag)
        .is_err());
}

#[cfg(feature = "ysc5x")]
#[test]
fn xof_implements_rustcrypto_traits() {
    let mut h = ysc5::Ysc5_128Hasher::new();
    h.update(b"hello");
    let mut reader = h.finalize_xof();
    let mut o1 = [0u8; 32];
    reader.read(&mut o1);

    let mut h = ysc5::Ysc5_128Hasher::new();
    h.update(b"hello");
    let mut reader = h.finalize_xof();
    let mut o2 = [0u8; 32];
    reader.read(&mut o2);
    assert_eq!(o1, o2);

    let mut h = ysc5::Ysc5_128Hasher::new();
    h.update(b"world");
    let mut reader = h.finalize_xof();
    let mut o3 = [0u8; 32];
    reader.read(&mut o3);
    assert_ne!(o1, o3);
}

#[cfg(feature = "ysc5x")]
#[test]
fn mac_implements_rustcrypto_traits() {
    let mut m = <ysc5::Ysc5_128Mac as MacKeyInit>::new_from_slice(&[0xAB; 32]).unwrap();
    Update::update(&mut m, b"hello");
    let tag = m.finalize();
    let bytes1 = tag.into_bytes();

    let mut m = <ysc5::Ysc5_128Mac as MacKeyInit>::new_from_slice(&[0xAB; 32]).unwrap();
    Update::update(&mut m, b"hello");
    let tag = m.finalize();
    let bytes2 = tag.into_bytes();
    assert_eq!(bytes1, bytes2);

    let mut m = <ysc5::Ysc5_128Mac as MacKeyInit>::new_from_slice(&[0xCD; 32]).unwrap();
    Update::update(&mut m, b"hello");
    let tag3 = m.finalize().into_bytes();
    assert_ne!(bytes1, tag3);
}
