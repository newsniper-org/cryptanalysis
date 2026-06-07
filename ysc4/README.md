# ysc4

> *σ-Generalized Lai-Massey 기반 FHE 최적화 sponge 스트림 암호*

[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](../LICENSE)
![no_std](https://img.shields.io/badge/no__std-yes-green)
![musl](https://img.shields.io/badge/target-musl-orange)
![verified](https://img.shields.io/badge/formal--verified-Isabelle%2FHOL-purple)

YSC3 대비 *FHE AND 카운트 1/6 절감*. σ-orthomorphism으로 Lai-Massey 구조의 약점 차단.

- 사양: [SPEC.md](SPEC.md) / [SPEC.pdf](SPEC.pdf) (Typst)
- 형식 검증: [isabelle-verify/](../isabelle-verify/) — Q1 (primitive α), Q2 (cycle 분포), Q3 (γ roll)
- 위치: YSC 패밀리의 *FHE-친화* 변종

## 핵심 설계

```
1 round:
  state[r mod 16] ⊕= RC[r mod 16]
  T = F(⊕ᵢ state[i])              # F 호출 단 1회
  state[i] ⊕= T  for all i        # broadcast
  state[ 0] = α¹·state[ 0]       # σ-층 (4 워드)
  state[ 4] = α³·state[ 4]
  state[ 8] = α⁵·state[ 8]
  state[12] = α⁷·state[12]
  state[i] = state[P[i]]          # 16-cycle π
```

## 매개변수

| 변종 | 키 | Rate | Capacity | R_init / R_block |
|------|----|------|---------|------------------|
| YSC4-128 | 256-bit | 512-bit | 512-bit | 32 / 16 |
| YSC4-256 | 512-bit | 256-bit | 768-bit | 40 / 20 |

## 빌드

```bash
cd ysc4
cargo build --release
cargo test --release --features ysc4x
```

## 사용 예제

```rust
use ysc4::stream::Ysc4_128Stream;

let cipher = Ysc4_128Stream::new(&[0xAA; 32], &[0xBB; 24]).unwrap();
let mut buf = b"plaintext".to_vec();
cipher.apply_keystream(&mut buf, 0);    // encrypt
```

## 형식 검증된 사실

| 정리 | 명제 | 위치 |
|------|------|------|
| `Q1_primitive_certificate` | α는 GF(2⁶⁴)*의 primitive (ord = 2⁶⁴−1) | [Q1_Primitivity.thy](../isabelle-verify/Q1_Primitivity.thy) |
| `Q2_all_orders_practical` | k ∈ {1..16}에 대해 ord(α^k) > 2⁶⁰ | [Q2_Cycles.thy](../isabelle-verify/Q2_Cycles.thy) |
| `Q3_roll_distinct_for_ones` | γ roll의 1-단계 distinct 결과 | [Q3_RollMatrix.thy](../isabelle-verify/Q3_RollMatrix.thy) |

## 성능 (vs YSC3)

| 측정 | YSC3 | **YSC4** |
|------|-----:|---------:|
| FHE AND/block | 12,288 | **2,048** (1/6) |
| 깊이 | 48 | **16** (1/3) |
| 처리량 | 576 MB/s | 243 MB/s |

YSC3보다 *FHE에서* 빠르고 *소프트웨어에서* 느림.

## YSC 패밀리

- [ysc3](../ysc3/) — GFN baseline
- **ysc4** ← 현재 (σ-GLM, FHE 최적화)
- [ysc5](../ysc5/) — Farfalle (병렬)
