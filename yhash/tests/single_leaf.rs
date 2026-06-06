//! YHash single-leaf fast path 검증.

use yhash::{YHashBuilder, YHasher};

#[test]
fn small_input_fits_in_single_leaf() {
    let builder = YHashBuilder::unkeyed();
    let inputs: &[&[u8]] = &[
        b"",
        b"a",
        b"hello",
        b"short string key",
        &[0u8; 32],
        &[0u8; 64],
        &[0u8; 128],
        &[0u8; 256],
        &[0u8; 512],
        &[0u8; 1024], // single-leaf 한계
    ];
    for input in inputs {
        let mut h = builder.build_hasher();
        h.update(input);
        let _d = h.finalize();
    }
}

#[test]
fn deterministic_across_calls() {
    let builder = YHashBuilder::keyed(b"key");
    let mut h1 = builder.build_hasher();
    h1.update(b"data");
    let d1 = h1.finalize();
    let mut h2 = builder.build_hasher();
    h2.update(b"data");
    let d2 = h2.finalize();
    assert_eq!(d1, d2);
}

#[test]
fn distinct_lengths_distinct() {
    // 같은 prefix, 길이만 다른 두 입력은 다른 digest를 가져야 함 (length encoding).
    let builder = YHashBuilder::unkeyed();
    let mut h1 = builder.build_hasher();
    h1.update(b"abc");
    let mut h2 = builder.build_hasher();
    h2.update(b"abcd");
    assert_ne!(h1.finalize(), h2.finalize());
}

#[test]
fn empty_vs_nonempty() {
    let builder = YHashBuilder::unkeyed();
    let mut h1 = builder.build_hasher();
    h1.update(b"");
    let mut h2 = builder.build_hasher();
    h2.update(b"\0");
    assert_ne!(h1.finalize(), h2.finalize());
}

#[test]
fn keyed_change_changes_output() {
    let mut h1 = YHashBuilder::keyed(b"key1").build_hasher();
    h1.update(b"same");
    let mut h2 = YHashBuilder::keyed(b"key2").build_hasher();
    h2.update(b"same");
    assert_ne!(h1.finalize(), h2.finalize());
}

#[test]
fn finalize_u64_consistent() {
    let builder = YHashBuilder::unkeyed();
    let mut h = builder.build_hasher();
    h.update(b"sample");
    let d = h.finalize();
    let expected_u64 = u64::from_le_bytes(d[0..8].try_into().unwrap());

    let mut h2 = builder.build_hasher();
    h2.update(b"sample");
    assert_eq!(h2.finalize_u64(), expected_u64);
}
