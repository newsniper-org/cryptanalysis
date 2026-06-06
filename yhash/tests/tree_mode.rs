//! YHash tree-mode (큰 입력) 검증.

use yhash::YHashBuilder;

#[test]
fn large_input_uses_tree() {
    let builder = YHashBuilder::unkeyed();
    let large = vec![0xABu8; 4096]; // > 1024 byte = single-leaf 한계
    let mut h = builder.build_hasher();
    h.update(&large);
    let _d = h.finalize();
}

#[test]
fn incremental_chunks_match_oneshot_large() {
    let builder = YHashBuilder::unkeyed();
    let data: Vec<u8> = (0..3000).map(|i| (i & 0xFF) as u8).collect();

    let mut h1 = builder.build_hasher();
    h1.update(&data);
    let d1 = h1.finalize();

    // 작은 chunk로 incremental
    let mut h2 = builder.build_hasher();
    for chunk in data.chunks(37) {
        h2.update(chunk);
    }
    let d2 = h2.finalize();

    assert_eq!(d1, d2);
}

#[test]
fn different_large_inputs_different_digests() {
    let builder = YHashBuilder::unkeyed();
    let a: Vec<u8> = (0..2000).map(|i| (i & 0xFF) as u8).collect();
    let b: Vec<u8> = (0..2000).map(|i| ((i + 1) & 0xFF) as u8).collect();

    let mut h_a = builder.build_hasher();
    h_a.update(&a);
    let mut h_b = builder.build_hasher();
    h_b.update(&b);

    assert_ne!(h_a.finalize(), h_b.finalize());
}

#[test]
fn boundary_input_1024_bytes() {
    // 정확히 1024 byte = single-leaf 한계
    let builder = YHashBuilder::unkeyed();
    let data = vec![0xCD; 1024];
    let mut h = builder.build_hasher();
    h.update(&data);
    let _d = h.finalize();
}

#[test]
fn boundary_input_1025_bytes() {
    // 1025 byte → tree mode (한 leaf 초과)
    let builder = YHashBuilder::unkeyed();
    let data = vec![0xCD; 1025];
    let mut h = builder.build_hasher();
    h.update(&data);
    let _d = h.finalize();
}
