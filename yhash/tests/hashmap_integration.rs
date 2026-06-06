//! YHash을 std HashMap의 hasher로 사용.

use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use yhash::{YHashBuilder, YHasher};

#[test]
fn yhasher_implements_std_hasher() {
    let mut h = YHashBuilder::keyed(b"dos-key").build_hasher();
    "key1".hash(&mut h);
    let v1 = Hasher::finish(&h);

    let mut h = YHashBuilder::keyed(b"dos-key").build_hasher();
    "key1".hash(&mut h);
    let v2 = Hasher::finish(&h);

    assert_eq!(v1, v2);
}

#[test]
fn hashmap_with_yhash() {
    let mut map: HashMap<String, i32, YHashBuilder> =
        HashMap::with_hasher(YHashBuilder::keyed(b"dos-key"));
    map.insert("alpha".to_string(), 1);
    map.insert("beta".to_string(), 2);
    map.insert("gamma".to_string(), 3);

    assert_eq!(map.get("alpha"), Some(&1));
    assert_eq!(map.get("beta"), Some(&2));
    assert_eq!(map.get("gamma"), Some(&3));
    assert_eq!(map.get("delta"), None);
}

#[test]
fn hashmap_distinct_keys_produce_distinct_buckets() {
    let mut map: HashMap<&str, &str, YHashBuilder> =
        HashMap::with_hasher(YHashBuilder::keyed(b"dos-key"));
    for i in 0..1000 {
        let k = format!("key{}", i);
        map.insert(Box::leak(k.into_boxed_str()), "v");
    }
    assert_eq!(map.len(), 1000);
}

#[test]
fn dos_resistant_per_key_change() {
    // 키를 바꾸면 해시 분포도 바뀐다 (DoS 방어).
    let mut h1 = YHashBuilder::keyed(b"key1").build_hasher();
    "common".hash(&mut h1);
    let v1 = Hasher::finish(&h1);

    let mut h2 = YHashBuilder::keyed(b"key2").build_hasher();
    "common".hash(&mut h2);
    let v2 = Hasher::finish(&h2);

    assert_ne!(v1, v2);
}
