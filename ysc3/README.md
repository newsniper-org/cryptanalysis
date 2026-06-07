# ysc3

> *ChaCha/NORX 기반 generalized Feistel network sponge 스트림 암호*

[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](../LICENSE)
![no_std](https://img.shields.io/badge/no__std-yes-green)
![musl](https://img.shields.io/badge/target-musl-orange)

YSC2 v1.0의 [cryptanalysis](../REPORT.md) 결과를 반영한 *재설계 1차*. NORX H 함수
(`x ⊕ y ⊕ ((x∧y) << 1)`) + ChaCha column/diagonal 더블 라운드. 1024-bit sponge 모드.

- 사양: [SPEC.md](SPEC.md) / [SPEC.pdf](SPEC.pdf) (Typst)
- 형식 검증: 없음 (YSC4가 후속). YSC3는 *비교 baseline*.
- 위치: YSC 패밀리의 *generalized Feistel* 변종

## 매개변수

| 변종 | 키 | rate | capacity | R_init / R_block |
|------|----|------|---------|-----------------|
| YSC3-128 | 256-bit | 512-bit | 512-bit | 24 / 12 |
| YSC3-256 | 512-bit | 256-bit | 768-bit | 32 / 16 |

## 빌드

```bash
cd ysc3
cargo build --release             # no_std + musl
cargo test --release --features ysc3x  # AEAD + XOF 포함
```

## 사용 예제

### Stream cipher

```rust
use ysc3::stream::Ysc3_128Stream;

let cipher = Ysc3_128Stream::new(&[0xAA; 32], &[0xBB; 24]).unwrap();
let mut buf = b"plaintext message".to_vec();
cipher.apply_keystream(&mut buf, 0);    // encrypt
cipher.apply_keystream(&mut buf, 0);    // decrypt (XOR symmetry)
```

### AEAD (feature `ysc3x`)

```rust
use ysc3::aead::Ysc3Aead;
use ysc3::stream::Ysc3_128;

let aead = Ysc3Aead::<Ysc3_128>::new(&[0; 32]).unwrap();
let mut buf = b"secret".to_vec();
let tag = aead.encrypt(&[0; 24], b"ad", &mut buf).unwrap();
aead.decrypt(&[0; 24], b"ad", &mut buf, &tag).unwrap();
```

## 성능

| 측정 | YSC3 |
|------|-----:|
| Throughput | 576 MB/s (단일 thread, musl release) |
| FHE AND/block | 12,288 |
| 상태 | 1024-bit |

YSC4 대비 ~1/6 FHE 비용 절감 *기회를 놓친* 변종. FHE 우선이라면 YSC4 권장.

## YSC 패밀리

- **ysc3** ← 현재 (GFN baseline)
- [ysc4](../ysc4/) — σ-GLM (FHE 최적화, 형식 검증)
- [ysc5](../ysc5/) — Farfalle (병렬)
