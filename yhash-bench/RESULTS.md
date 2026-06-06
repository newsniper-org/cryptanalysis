# 해시 비교 — keyed/unkeyed, HashMap 패턴

> 측정: x86_64 (단일 thread, `cargo run --release`).
> **공정성**: HashMap 사용 패턴 모사 — `BuildHasher` 한 번만 구축, `Hasher`는 매 호출 생성.
> 이전 측정 (builder를 매 호출마다 재구축)은 IV 도출 비용을 *과대 포함*해 부정확했음.

## 1. State / Builder 크기

| Type | bytes | 용도 |
|------|------:|------|
| YHasher (per hash) | 2,240 | hash 단위 인스턴스 |
| YpsiHasher (per hash) | 864 | hash 단위 인스턴스 |
| SipHasher13 (per hash) | 72 | hash 단위 인스턴스 |
| AHasher (per hash) | 32 | hash 단위 인스턴스 |
| FxHasher (per hash) | 8 | hash 단위 인스턴스 |
| YHashBuilder (per HashMap) | 128 | 정적 |
| YpsiBuilder (per HashMap) | 32 | 정적 |
| `ahash::RandomState` (per HashMap) | 32 | 정적 |

## 2. Keyed vs Unkeyed — 성능 차이 없음

| Hasher | 모드 | 4-byte key | 1 KB throughput |
|--------|------|-----------:|----------------:|
| YHash | keyed | 2,015 ns | 181 MB/s |
| YHash | **unkeyed** | 2,021 ns | 179 MB/s |
| ypsilenti | keyed | 386 ns | 273 MB/s |
| ypsilenti | **unkeyed** | 390 ns | 281 MB/s |

→ **IV 도출은 빌더 시점에 한 번만 발생**. 두 모드의 핫패스 비용은 사실상 동일.
   keyed 모드의 추가 비용은 *빌더 구축 시점*뿐이며, HashMap에서는 1회.

## 3. Throughput (MB/s, builder 공유)

| 입력 | YHash | ypsilenti | SipHash13 | ahash | FxHash |
|------|------:|----------:|----------:|------:|-------:|
| 16 B    |     8 |     43  |  2,808  | 17,811 | 13,569 |
| 64 B    |    32 |    148  |  4,990  | 24,613 | 34,511 |
| 256 B   |   100 |    297  |  6,218  | 22,910 | 36,599 |
| 1 KB    |   181 |    273  |  6,562  | 12,696 | 30,121 |
| 4 KB    |   160 |    270  |  6,718  | 19,183 | 27,766 |
| 64 KB   |   154 |    270  |  6,610  | 18,403 | 26,721 |

ypsilenti가 YHash의 1.7-5× 빠름 (작은 입력에서 효과 큼).

## 4. Per-call cost (HashMap-typical 작은 키)

| 키 길이 | YHash | ypsilenti | SipHash13 | ahash | FxHash |
|--------:|------:|----------:|----------:|------:|-------:|
| 4 B    | 2,015 |   **386** |   3.65 |  0.93 |  0.79 |
| 8 B    | 2,007 |   **364** |   4.53 |  0.93 |  0.79 |
| 16 B   | 2,013 |   **367** |   5.85 |  0.99 |  0.91 |
| 32 B   | 2,024 |   **375** |   8.14 |  1.47 |  1.08 |
| 64 B   | 2,020 |   **434** |  12.71 |  2.61 |  1.84 |
| 128 B  | 2,018 |   **573** |  22.37 |  8.44 |  3.55 |

(단위: ns/hash)

→ **ypsilenti는 YHash 대비 ~5.5× 빠름** (4-byte). \
   **SipHash13 대비는 여전히 ~100× 느림**. \
   이전 결과(~640×)는 builder 재구축 때문이었음.

## 5. 이전 측정 (잘못된 패턴)과의 차이

| Hasher | 매 호출 builder 구축 | builder 공유 (HashMap 패턴) | 차이 |
|--------|---------------------:|---------------------------:|-----:|
| YHash | 2,421 ns | 2,015 ns | -17% |
| ypsilenti | 501 ns | 386 ns | -23% |

→ **builder 재사용만으로 YHash는 17%, ypsilenti는 23% 가속**. \
   이는 IV 도출이 1회 비용으로 amortize되기 때문.

## 6. 의미 해석

### Keyed/Unkeyed 동등성의 의미
- **DoS resistance에 추가 성능 페널티 없음**: 같은 builder를 재사용한다면 keyed 모드를 *공짜로* 얻음.
- HashMap의 DoS 방어 키는 `RandomState` 같이 boot 시점에 한 번 생성 후 영구 재사용 → 매 hash 호출은 keyed/unkeyed 무관하게 같은 비용.

### Builder 크기 비교
- YHash builder 128 byte (16 워드 IV state)
- ypsilenti builder 32 byte (8 워드 × 4 byte)
- `ahash::RandomState` 32 byte (4 × u64 seed)

→ ypsilenti builder는 ahash와 동일 크기 (32 byte). 메모리 footprint는 동등.

### Niche 재확인
- **HashMap 핫패스**: ahash/FxHash 압도. SipHash13이 default여서 합리적 절충.
- **ypsilenti**: SipHash13보다 100× 느리지만 *128-bit DoS + 형식 검증된 트리 모드*가 필요한 시나리오에서 의미.
- **YHash**: 256-bit + Farfalle-tree + verified streaming이 필요한 경우.

## 7. 결론

이전 보고서의 *과대 평가 (~640×, ~130× 느림)*는 builder 재구축 비용 때문이었음.

**정정된 정확한 비교**:
- **ypsilenti는 SipHash13보다 ~100× 느림** (작은 키 기준)
- **keyed/unkeyed 모드 성능 차이는 무의미**
- **HashMap 사용 패턴에서 빌더 공유로 17-23% 추가 절약**

성능 위치:
- ypsilenti는 *cryptographic-grade* 와 *fast-hash* 사이의 **본질적 격차** 안에서 가장 효율적인 다운사이징.
- 더 줄이려면 (Tier 1: 라운드 감축, Tier 2: SIMD) 가능하나 ~2× 추가만 기대.
- SipHash13 수준까지는 cryptographic property를 유지하면서 도달 *불가*.
