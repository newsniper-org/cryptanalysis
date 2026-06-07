# yhash

> *Farfalle-tree hash for HashMap/KV stores (cryptographic-grade)*

[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](../LICENSE)
![no_std](https://img.shields.io/badge/no__std-yes-green)
![musl](https://img.shields.io/badge/target-musl-orange)
![verified](https://img.shields.io/badge/formal--verified-Isabelle%2FHOL-purple)

YSC4-p 순열 + Farfalle-tree 구조 기반 *cryptographic hash*. HashMap-API 호환이지만
설계 자체는 **256-bit secure hash + verified streaming**.

- 사양: [SPEC-draft.md](SPEC-draft.md)
- 참조 노트: [../farfalle-tree-design.md](../farfalle-tree-design.md)
- 형식 검증: [yhash-verify/](../yhash-verify/) — Y1~Y5

## 핵심 설계

- 1024-bit state (YSC4-p), 256-bit chaining value
- Tree-positional masks: `k(path) = P(IV ⊕ encode(path))`
- Single-leaf fast path (≤ 1024 byte 입력)
- Tree mode (큰 입력, fixed-depth 32)
- Keyed (DoS-resistant) + Unkeyed (deterministic) 양쪽

## 빌드

```bash
cd yhash
cargo build --release
cargo test --release --features yhash-digest   # RustCrypto digest 포함
```

## 사용 예제

### HashMap 통합

```rust
use std::collections::HashMap;
use yhash::YHashBuilder;

// DoS-resistant keyed mode
let builder = YHashBuilder::keyed(b"per-process-key");
let mut map: HashMap<String, i32, YHashBuilder> = HashMap::with_hasher(builder);
map.insert("key1".to_string(), 1);
```

### Streaming hash

```rust
use yhash::YHashBuilder;

let builder = YHashBuilder::unkeyed();
let mut h = builder.build_hasher();
h.update(b"chunk 1");
h.update(b"chunk 2");
let digest: [u8; 32] = h.finalize();
```

### RustCrypto Digest API (feature `yhash-digest`)

```rust
use digest::{Update, FixedOutput};
use yhash::digest_api::{YHashDigest, YHashMac};

// 256-bit hash
let mut h = YHashDigest::default();
Update::update(&mut h, b"data");
let out = h.finalize_fixed();    // GenericArray<u8, U32>

// MAC
use digest::{Mac, KeyInit};
let mut m = <YHashMac as KeyInit>::new_from_slice(&[0x42; 32]).unwrap();
Mac::update(&mut m, b"data");
let tag = m.finalize().into_bytes();
```

## 형식 검증된 사실

| 정리 | 명제 | 위치 |
|------|------|------|
| `Y1_encode_injective` | 트리 위치 인코딩 단사 | [Y1_TreeEncoding.thy](../yhash-verify/Y1_TreeEncoding.thy) |
| `Y2_decomposition` | `acc(xs @ ys) = acc xs ⊕ acc ys` | [Y2_XORDecomposition.thy](../yhash-verify/Y2_XORDecomposition.thy) |
| `Y3_*` | LEAF/INTERNAL/ROOT 충돌 불가 | [Y3_DomainSeparation.thy](../yhash-verify/Y3_DomainSeparation.thy) |
| `Y4_mask_inj` | distinct (lt, pos, idx) ⇒ distinct mask | [Y4_MaskUniqueness.thy](../yhash-verify/Y4_MaskUniqueness.thy) |
| `Y5_*` | CR reduction skeleton (sorry-permitted, research-grade) | [Y5_CRReduction.thy](../yhash-verify/Y5_CRReduction.thy) |

## 성능 (HashMap 패턴, builder 공유)

| 측정 | YHash |
|------|------:|
| State (Hasher) | 2,240 bytes |
| Builder | 128 bytes |
| 4-byte key | 2,015 ns |
| 1 KB throughput | 181 MB/s |

자세한 비교: [yhash-bench/RESULTS.md](../yhash-bench/RESULTS.md)

## 어디에 적합한가

✅ **적합**: file integrity, verified streaming (per-chunk MAC), content-addressed storage,
   *cryptographic-grade* DoS resistance가 필요한 경우

❌ **부적합**: 일반 HashMap key hashing (SipHash13/ahash 사용 권장)
   → 중간 옵션은 [ypsilenti](../ypsilenti/)

## YHash 패밀리

- **yhash** ← 현재 (full 1024-bit, 256-bit digest)
- [ypsilenti](../ypsilenti/) — downsized (256-bit state, 128-bit digest)
