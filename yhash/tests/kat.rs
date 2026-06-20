//! KAT(known-answer test) — frozen 파라미터 v1 회귀.
//!
//! 이 벡터들은 `examples/gen_kat.rs`로 생성된 *동결 기대값*이다. 독립 재구현은
//! 동일 입력에 대해 동일 digest/u64를 재현해야 한다 (cross-implementation KAT).
//! 값이 바뀌면 = 파라미터/알고리즘이 바뀐 것 = frozen 위반(=의도적이라면 버전 bump).

use std::hash::Hasher;
use yhash::YHashBuilder;

fn hx(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}

fn unkeyed(data: &[u8]) -> ([u8; 32], u64) {
    let mut h = YHashBuilder::unkeyed().build_hasher();
    h.update(data);
    (h.clone().finalize(), h.finalize_u64())
}
fn keyed(key: &[u8], data: &[u8]) -> ([u8; 32], u64) {
    let mut h = YHashBuilder::keyed(key).build_hasher();
    h.update(data);
    (h.clone().finalize(), h.finalize_u64())
}

fn check(label: &str, got: ([u8; 32], u64), exp_hex: &str, exp_u64: u64) {
    assert_eq!(hx(&got.0), exp_hex, "{label}: digest mismatch (frozen param 위반?)");
    assert_eq!(got.1, exp_u64, "{label}: u64 mismatch");
    // finalize_u64 == digest 첫 8바이트 LE 불변식
    assert_eq!(
        u64::from_le_bytes(got.0[0..8].try_into().unwrap()),
        got.1,
        "{label}: u64 != digest[0..8] LE"
    );
}

#[test]
fn yhash_frozen_kat_v1() {
    let p256: Vec<u8> = (0..256u32).map(|i| i as u8).collect();
    let leaf_full = vec![0xABu8; 1024];
    let tree2 = vec![0xCDu8; 1025];
    let tree_big: Vec<u8> = (0..16384u32).map(|i| (i.wrapping_mul(7) ^ 0x5A) as u8).collect();
    let key16 = b"0123456789abcdef";

    check("unkeyed empty", unkeyed(b""),
        "e4bc8871be42d3789f37ab59f093a7186a8d7daf476e785e6f48bb9ef678c563", 0x78d342be7188bce4);
    check("unkeyed abc", unkeyed(b"abc"),
        "6756260e61c9c9572090cd9dcd38d9ee038abde45ef85e21db374e4d79caaf39", 0x57c9c9610e265667);
    check("unkeyed 0..256", unkeyed(&p256),
        "f58e34bac1086d537f4d1ccd67329ec9a6b25c87cd1fba9e32b85d38a5043baf", 0x536d08c1ba348ef5);
    check("unkeyed leaf_full(1024)", unkeyed(&leaf_full),
        "86e7fa9dce35b7ceee29e181db1586e3812cc71db9ced12e884dc832ef8e8ff4", 0xceb735ce9dfae786);
    check("unkeyed tree(1025)", unkeyed(&tree2),
        "3ec7b3c9f56ec29e4c2b537fd8c74ebe7046da57e2e109b5e495acfe688ff6ce", 0x9ec26ef5c9b3c73e);
    check("unkeyed tree_big(16384)", unkeyed(&tree_big),
        "ca88c865703e77483257785188d297ae52574e198e7c91c1e08ad6bb1b7174af", 0x48773e7065c888ca);
    check("keyed[0;16] abc", keyed(&[0u8; 16], b"abc"),
        "63c931e706a3b7544018654e1c6115c01e7f0d59507389e373f2bdd5000a791e", 0x54b7a306e731c963);
    check("keyed[ascii] abc", keyed(key16, b"abc"),
        "0172416db46ea392b0e834035972d3c1771924e22fa38a2eb624c293b1bf8897", 0x92a36eb46d417201);
    check("keyed[ascii] tree_big", keyed(key16, &tree_big),
        "f1998aecb7eb333fb0cf3b5cec45b9add88321334c273e2643792c0bfd02555f", 0x3f33ebb7ec8a99f1);
}
