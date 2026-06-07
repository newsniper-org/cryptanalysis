# ypsilenti

> *Downsized Farfalle-tree hash. Niche: FxHash 가벼움과 BLAKE3 보안 사이의 *중간*.*

[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](../LICENSE)
![no_std](https://img.shields.io/badge/no__std-yes-green)
![musl](https://img.shields.io/badge/target-musl-orange)
![verified](https://img.shields.io/badge/formal--verified-Isabelle%2FHOL-purple)

YHash의 다운사이징 변종:
- 상태 8×u32 = 256-bit (YHash의 1/4)
- α-mult: GF(2³²) (Lidl-Niederreiter primitive polynomial, 형식 검증됨)
- 라운드 R_b=4 / R_c=6 (YHash의 절반)
- 128-bit chaining value

YHash 대비 **4.8× per-call 속도, 2.6× 작은 상태**. 형식 검증된 트리 모드는 그대로.

- 사양: [SPEC-draft.md](SPEC-draft.md)
- 형식 검증: [ypsilenti-verify/](../ypsilenti-verify/) — Q1', Q2', Y1'~Y4'

## 위치 (왜 ypsilenti?)

| 축 | FxHash | **ypsilenti** | YHash | BLAKE3 |
|----|:------:|:-------------:|:-----:|:------:|
| 속도 | ★★★★ | ★★ | ★ | ★★ |
| DoS 저항 | ✗ | ★★ | ★★★ | ★★★ |
| 형식 검증 | ✗ | ★★ | ★★ | ✗ |
| 메모리 footprint | ★★★★ | ★★★ | ★★ | ★★ |
| Tree mode | ✗ | ★ | ★★ | ★★★ |
| Builder size | 8 B | **32 B** (ahash와 동일) | 128 B | 적용 안 됨 |

ypsilenti는 *DoS-주의가 필요하지만 BLAKE3는 오버킬*인 자리.

## 빌드

```bash
cd ypsilenti
cargo build --release
cargo test --release --features ypsi-digest   # RustCrypto digest 포함
```

## 사용 예제

### HashMap 통합

```rust
use std::collections::HashMap;
use ypsilenti::YpsiBuilder;

let builder = YpsiBuilder::keyed(b"dos-key-16-byte!");
let mut map: HashMap<String, i32, YpsiBuilder> = HashMap::with_hasher(builder);
map.insert("k".to_string(), 1);
```

### Direct hashing

```rust
use ypsilenti::YpsiBuilder;

let builder = YpsiBuilder::unkeyed();
let mut h = builder.build_hasher();
h.update(b"data");
let digest: [u8; 16] = h.finalize();
```

### RustCrypto Digest (feature `ypsi-digest`)

```rust
use digest::{Update, FixedOutput, Mac, KeyInit};
use ypsilenti::digest_api::{YpsiDigest, YpsiMac};

// 128-bit hash
let mut h = YpsiDigest::default();
Update::update(&mut h, b"data");
let out = h.finalize_fixed();    // GenericArray<u8, U16>

// 128-bit MAC
let mut m = <YpsiMac as KeyInit>::new_from_slice(&[0x42; 16]).unwrap();
Mac::update(&mut m, b"data");
let tag = m.finalize().into_bytes();
```

## 형식 검증된 사실

| 정리 | 명제 | 위치 |
|------|------|------|
| `Q1p_primitive_certificate` | α는 GF(2³²)*의 primitive | [Q1p_Primitivity.thy](../ypsilenti-verify/Q1p_Primitivity.thy) |
| `Q2p_all_orders_practical` | k ∈ {1..8}에 대해 ord(α^k) > 2²⁸ | [Q2p_Cycles.thy](../ypsilenti-verify/Q2p_Cycles.thy) |
| `Y1p~Y4p` | tree 구조 (YHash와 동일 형태) | [ypsilenti-verify/](../ypsilenti-verify/) |

GF(2³²) polynomial: **x³² + x²² + x² + x + 1** (Lidl-Niederreiter table primitive).

## 성능 (HashMap 패턴)

| 측정 | ypsilenti |
|------|----------:|
| State (Hasher) | 864 bytes |
| Builder | 32 bytes (ahash와 동일) |
| 4-byte key | **386 ns** (YHash 2,015 ns 대비 5×) |
| 1 KB throughput | 273 MB/s |

자세한 비교: [yhash-bench/RESULTS.md](../yhash-bench/RESULTS.md)

## YHash 패밀리

- [yhash](../yhash/) — full (1024-bit state, 256-bit digest)
- **ypsilenti** ← 현재 (256-bit state, 128-bit digest)
