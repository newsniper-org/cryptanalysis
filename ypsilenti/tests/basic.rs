//! ypsilenti 기본 동작 검증.

use ypsilenti::{YpsiBuilder, YpsiHasher};

#[test]
fn deterministic() {
    let builder = YpsiBuilder::unkeyed();
    let mut h1 = builder.build_hasher();
    h1.update(b"hello");
    let mut h2 = builder.build_hasher();
    h2.update(b"hello");
    assert_eq!(h1.finalize(), h2.finalize());
}

#[test]
fn distinct_input() {
    let builder = YpsiBuilder::unkeyed();
    let mut h1 = builder.build_hasher();
    h1.update(b"hello");
    let mut h2 = builder.build_hasher();
    h2.update(b"world");
    assert_ne!(h1.finalize(), h2.finalize());
}

#[test]
fn keyed_vs_unkeyed() {
    let mut h1 = YpsiBuilder::unkeyed().build_hasher();
    h1.update(b"data");
    let mut h2 = YpsiBuilder::keyed(b"secret").build_hasher();
    h2.update(b"data");
    assert_ne!(h1.finalize(), h2.finalize());
}

#[test]
fn incremental_matches_oneshot() {
    let builder = YpsiBuilder::unkeyed();
    let mut h1 = builder.build_hasher();
    h1.update(b"hello world");
    let d1 = h1.finalize();
    let mut h2 = builder.build_hasher();
    h2.update(b"hello ");
    h2.update(b"world");
    let d2 = h2.finalize();
    assert_eq!(d1, d2);
}

#[test]
fn large_input_tree_mode() {
    let builder = YpsiBuilder::unkeyed();
    let mut h = builder.build_hasher();
    h.update(&vec![0xAB; 4096]);
    let _d = h.finalize();
}

#[test]
fn hashmap_compatible() {
    use std::collections::HashMap;
    let mut map: HashMap<String, i32, YpsiBuilder> =
        HashMap::with_hasher(YpsiBuilder::keyed(b"dos-key"));
    map.insert("a".to_string(), 1);
    map.insert("b".to_string(), 2);
    assert_eq!(map.get("a"), Some(&1));
    assert_eq!(map.get("b"), Some(&2));
}
