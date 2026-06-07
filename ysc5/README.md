# ysc5

> *Farfalle PRF/Stream/AEAD/XOF on YSC4-p (σ-GLM) permutation*

[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](../LICENSE)
![no_std](https://img.shields.io/badge/no__std-yes-green)
![musl](https://img.shields.io/badge/target-musl-orange)
![RustCrypto](https://img.shields.io/badge/RustCrypto-traits-darkgreen)

YSC4-p 순열 + Bertoni-Daemen Farfalle 구조. 블록 간 *완전 병렬*, incremental update,
RustCrypto convention.

- 사양: [SPEC.typ](SPEC.typ) / [SPEC.pdf](SPEC.pdf) (Typst, 19 페이지)
- 핵심 통찰: YSC4의 σ-orthomorphism이 Farfalle의 mask-roll 요구를 *수학적으로 최적* 충족
- 위치: YSC 패밀리의 *병렬* 변종

## 핵심 설계

```
PRF(K, M):
    k = p_c(K∥pad)                                      # 키 확장 (1회)
    Y = ⊕_i p_b(M_i ⊕ γ^i(k))                           # 압축 (완전 병렬)
    Y' = p_d(Y) ⊕ γ^n(k) ⊕ DOMAIN_EXPAND                # 전이
    for j = 0..: Z_j = p_e(γ^j(Y')) → out               # 확장 (완전 병렬)
```

여기서 γ는 워드별 distinct α-거듭제곱 (= YSC4의 σ 재사용).

## 매개변수

| 변종 | 키 | Nonce | Rate | Capacity | R (init/b/d/e) |
|------|----|-------|------|---------|----------------|
| YSC5-128 | 256-bit | 192-bit | 512-bit | 512-bit | 24 / 12 / 8 / 12 |
| YSC5-256 | 512-bit | 192-bit | 256-bit | 768-bit | 32 / 16 / 12 / 16 |

## 빌드

```bash
cd ysc5
cargo build --release
cargo test --release --features ysc5x   # AEAD/XOF/MAC 포함
```

## 사용 예제

### Stream cipher (RustCrypto API)

```rust
use cipher::{KeyIvInit, StreamCipher};
use ysc5::Ysc5_128StreamCipher;

let mut cipher = Ysc5_128StreamCipher::new(&[0xAA; 32].into(), &[0xBB; 24].into());
let mut buf = b"plaintext".to_vec();
cipher.apply_keystream(&mut buf);
```

### AEAD (feature `ysc5x`)

```rust
use aead::{AeadInPlace, KeyInit};
use ysc5::Ysc5_128Aead;

let aead = Ysc5_128Aead::new(&[0x42; 32].into());
let mut buf = b"secret".to_vec();
let tag = aead
    .encrypt_in_place_detached(&[0xBB; 24].into(), b"ad", &mut buf)
    .unwrap();
aead.decrypt_in_place_detached(&[0xBB; 24].into(), b"ad", &mut buf, &tag)
    .unwrap();
```

### XOF (feature `ysc5x`)

```rust
use digest::{Update, ExtendableOutput, XofReader};
use ysc5::Ysc5_128Hasher;

let mut h = Ysc5_128Hasher::new();
h.update(b"hello");
let mut reader = h.finalize_xof();
let mut out = [0u8; 64];
reader.read(&mut out);
```

## 형식 검증 인용

YSC4의 [Q1, Q2, Q3](../isabelle-verify/)를 그대로 상속. Farfalle 환원 (Bertoni 2017)에 의해
PRF distinguishability bounded.

## 성능

| 측정 | YSC5 |
|------|-----:|
| FHE AND/block | 12,288 |
| 깊이 | 48 |
| 처리량 | 259 MB/s |
| **블록간 병렬성** | 완전 (Farfalle 핵심 장점) |

YSC4와 같은 단일 thread throughput이지만 *blocks 간 batch 가능* → FHE 백엔드에서 wall-clock 1/N.

## YSC 패밀리

- [ysc3](../ysc3/) — GFN baseline
- [ysc4](../ysc4/) — σ-GLM sponge
- **ysc5** ← 현재 (Farfalle 병렬)
