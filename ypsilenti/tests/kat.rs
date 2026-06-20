//! KAT(known-answer test) — frozen 파라미터 v1 회귀.
//!
//! `examples/gen_kat.rs`로 생성된 *동결 기대값*. 독립 재구현은 동일 입력에 대해
//! 동일 digest/u64를 재현해야 한다. 값이 바뀌면 frozen 위반(=의도적이면 버전 bump).

use std::hash::Hasher;
use ypsilenti::YpsiBuilder;

fn hx(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}

fn unkeyed(data: &[u8]) -> ([u8; 16], u64) {
    let mut h = YpsiBuilder::unkeyed().build_hasher();
    h.update(data);
    (h.clone().finalize(), h.finalize_u64())
}
fn keyed(key: &[u8], data: &[u8]) -> ([u8; 16], u64) {
    let mut h = YpsiBuilder::keyed(key).build_hasher();
    h.update(data);
    (h.clone().finalize(), h.finalize_u64())
}

fn check(label: &str, got: ([u8; 16], u64), exp_hex: &str, exp_u64: u64) {
    assert_eq!(hx(&got.0), exp_hex, "{label}: digest mismatch (frozen param 위반?)");
    assert_eq!(got.1, exp_u64, "{label}: u64 mismatch");
    assert_eq!(
        u64::from_le_bytes(got.0[0..8].try_into().unwrap()),
        got.1,
        "{label}: u64 != digest[0..8] LE"
    );
}

#[test]
fn ypsilenti_frozen_kat_v1() {
    let p200: Vec<u8> = (0..200u32).map(|i| i as u8).collect();
    let leaf_full = vec![0xABu8; 256];
    let tree2 = vec![0xCDu8; 257];
    let tree_big: Vec<u8> = (0..4096u32).map(|i| (i.wrapping_mul(7) ^ 0x5A) as u8).collect();
    let key16 = b"0123456789abcdef";

    check("unkeyed empty", unkeyed(b""),
        "787dbf67c2b2310afc758f9c81a56400", 0x0a31b2c267bf7d78);
    check("unkeyed abc", unkeyed(b"abc"),
        "ac29edefcbb9844b7a8fa1038470390e", 0x4b84b9cbefed29ac);
    check("unkeyed 0..200", unkeyed(&p200),
        "e1455acae322340cbbf6b37eac6d6ad8", 0x0c3422e3ca5a45e1);
    check("unkeyed leaf_full(256)", unkeyed(&leaf_full),
        "736f09099175ff13d9e8b5f3f1719cc1", 0x13ff759109096f73);
    check("unkeyed tree(257)", unkeyed(&tree2),
        "7f0a82ac842ec50151ee3058f1979407", 0x01c52e84ac820a7f);
    check("unkeyed tree_big(4096)", unkeyed(&tree_big),
        "f881d55c216f3d7249f85de9bfcf0195", 0x723d6f215cd581f8);
    check("keyed[0;16] abc", keyed(&[0u8; 16], b"abc"),
        "d53fa20eba629c04054cd916eb2c0510", 0x049c62ba0ea23fd5);
    check("keyed[ascii] abc", keyed(key16, b"abc"),
        "496173f69b56708226c3214955557e10", 0x8270569bf6736149);
    check("keyed[ascii] tree_big", keyed(key16, &tree_big),
        "5e0ae5ae28ed30f50ac4e67beeda80b4", 0xf530ed28aee50a5e);
}
