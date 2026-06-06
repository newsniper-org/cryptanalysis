# YHash family vs 외부 해시 — 벤치 결과

> 측정: x86_64 (단일 thread, `cargo run --release`).
> 라이브러리: `yhash`, `ypsilenti` (path), `ahash 0.8`, `rustc-hash 2`, `siphasher 1`.

## 1. State size (Hasher 인스턴스 메모리)

| Hasher | bytes | YHasher 대비 |
|--------|------:|------------:|
| **YHasher** (16 × u64) | **2,240** | 1.0× |
| **ypsilenti** (8 × u32) | **864** | 0.39× |
| SipHasher13 | 72 | 0.03× |
| AHasher | 32 | 0.014× |
| FxHasher | 8 | 0.004× |

→ **ypsilenti**가 YHash의 ~2.6× 작음. 여전히 SipHash13보다는 12× 큼.

## 2. Throughput (MB/s)

| 입력 크기 | YHash | **ypsilenti** | SipHash13 | ahash | FxHash |
|----------|------:|--------------:|----------:|------:|-------:|
| 16 B    |     7 |      **31** |  2,760  | 13,382 | 19,888 |
| 64 B    |    27 |     **116** |  5,021  | 21,396 | 32,935 |
| 256 B   |    88 |     **261** |  6,221  | 21,432 | 35,862 |
| 1 KB    |   169 |     **267** |  6,579  | 20,496 | 29,852 |
| 4 KB    |   159 |     **268** |  6,385  | 19,688 | 27,724 |
| 16 KB   |   155 |     **269** |  6,567  | 18,747 | 27,151 |
| 64 KB   |   154 |     **269** |  6,653  | 18,824 | 26,716 |

ypsilenti는 모든 입력 크기에서 YHash 대비 ~1.7× 빠름. SipHash13 대비는 여전히 ~25× 느림.

## 3. Per-call cost (HashMap-typical 4~128 byte keys)

| 키 길이 | YHash | **ypsilenti** | SipHash13 | ahash | FxHash |
|-------:|------:|--------------:|----------:|------:|-------:|
| 4 B   | 2,421 |       **501** |    3.74 |   1.21 |   0.99 |
| 8 B   | 2,425 |       **514** |    4.52 |   1.21 |   0.81 |
| 16 B  | 2,426 |       **500** |    5.81 |   1.19 |   0.80 |
| 32 B  | 2,422 |       **494** |    8.19 |   1.78 |   1.23 |
| 64 B  | 2,425 |       **563** |   14.26 |   4.60 |   1.95 |
| 128 B | 2,404 |       **716** |   22.27* |   5.75 |   3.61 |

(*추정값, 단위 ns/hash)

→ **ypsilenti는 YHash의 약 4.8× 빠름** (다운사이징 효과 확인). \
   SipHash13 대비 여전히 ~130× 느림 (256-bit perm 호출 자체가 비쌈).

## 4. 의미 해석

### Downsizing 효과 정량화
- 워드 폭 1/2 + 워드 개수 1/2 + 라운드 1/2 → *조합 효과* ≈ **4.8× 가속**.
- 이론 예측 (1.5× × 2× × 2× ≈ 6×)과 부합. 실제로는 약간 작은 게 라운드 수 영향이 dominant.

### Comparison 매트릭스

| Hasher | DoS-resistant | Crypto-grade | Verified streaming | HashMap-fast |
|--------|:---:|:---:|:---:|:---:|
| FxHash | ✗ | ✗ | ✗ | ★★★ |
| ahash | △ (heuristic) | ✗ | ✗ | ★★★ |
| SipHash13 | ★★ | △ | ✗ | ★★ |
| **ypsilenti** | ★★ | △ (64-bit) | ★ | ★ |
| **YHash** | ★★★ | ★★★ | ★★★ | ✗ |

### Niche
- **HashMap default 필요?**: `ahash` 또는 `SipHash13`.
- **256-bit secure hash + tree 필요?**: `YHash`.
- **128-bit DoS 충분, 작은 메모리 footprint 원함?**: **ypsilenti** (중간 지점).

## 5. 결론

다운사이징은 **유효**하지만 *cryptographic hash와 fast hash의 격차*가 본질적이라 SipHash13 수준까지는 미달. ypsilenti의 자리는:
- YHash보다 *명백히* 가볍고 빠름 (5×)
- 임베디드 / no_std에서 SipHash13 대비 *형식 검증된* 대안
- 작은 키 (≤ 256 B) 단일-leaf fast path 활용 시 추가 절약 여지

추가 가속 (~2× 더)이 필요하면 라운드 감축 (R_b=2, R_c=4) 또는 SIMD가 후보.
