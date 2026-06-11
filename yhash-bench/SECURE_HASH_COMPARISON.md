# 종합 보안 해시 비교 — YHash 패밀리 vs BLAKE3 vs KangarooTwelve

> 동일 조건: 단일 thread, `cargo run --release` (musl), 같은 iteration 수.
> Crate 버전: `blake3 1.x`, `k12 0.5.1`, `yhash/ypsilenti` path.

## 1. State size (Hasher 인스턴스)

| Hash | bytes | 비고 |
|------|------:|------|
| **KangarooTwelve(Kt128)** | **424** | 가장 작음 (k12 0.5의 sponge-cursor 최적화) |
| ypsilenti | 864 | 256-bit 상태 + tree-buffer |
| Blake3 Hasher | 1,920 | tree-build 누적 버퍼 |
| YHasher | 2,240 | 1024-bit 상태 + tree-buffer |

→ K12가 *놀랍게도 가장 작음*. ypsilenti는 두 번째.

## 2. Throughput (작은 입력 ≤ 4 KB)

| 입력 | yhash | ypsilenti | BLAKE3 | **K12** |
|------|------:|----------:|-------:|--------:|
| 16 B    |     8 |       44 |    275 |  **98** |
| 64 B    |    33 |      148 |  1,090 | **397** |
| 256 B   |   104 |      300 |  1,282 | **859** |
| 1 KB    |   182 |      280 |  1,347 | **1,073** |
| 4 KB    |   162 |      274 |  3,774 | **1,218** |

(단위: MB/s)

**관찰**:
- BLAKE3가 모든 영역 1위 (SIMD 최적화).
- **K12 0.5.1이 ypsilenti의 ~2-3× 빠름** (k12 0.5의 큰 개선).
- ypsilenti는 yhash의 ~5×, K12의 ~1/3.

## 3. Throughput (큰 입력)

| 입력 | yhash | ypsilenti | BLAKE3 | K12 |
|------|------:|----------:|-------:|----:|
| 64 KB   |   157 |      274 |  8,655 | 1,244 |
| 1 MB    |   155 |      273 |  **8,447** | 1,245 |

**관찰**:
- BLAKE3는 *대용량에서 폭주* — SIMD/AVX-2 효과.
- K12는 BLAKE3의 ~15%, ypsilenti의 ~5×.
- yhash가 가장 느림.

## 4. Per-hash 비용 (ns/hash)

| 입력 | yhash | ypsilenti | BLAKE3 | K12 |
|------|------:|----------:|-------:|----:|
| 16 B  | 1,951 |       365 |     58 |   163 |
| 64 B  | 1,946 |       431 |     59 |   161 |
| 256 B | 2,463 |       854 |    200 |   298 |
| 1 KB  | 5,612 |     3,659 |    760 |   955 |

**관찰**:
- BLAKE3는 16~64 byte에서 *상수 58 ns* — 압도적.
- K12는 16~64 byte에서 *161 ns 일정* (ypsilenti 392의 ~1/2).
- ypsilenti는 small input에서 K12의 ~2-2.4×.

## 5. 패밀리 위치 정리

| 측면 | yhash | ypsilenti | BLAKE3 | K12 |
|------|:-----:|:---------:|:------:|:---:|
| Throughput (1 MB) | ★ | ★★ | ★★★★ | ★★★ |
| Throughput (16 B) | ★ | ★★ | ★★★★ | ★★★ |
| State size | ★★ | ★★★ | ★★ | ★★★★ |
| Formal verification | ★★ | ★★ | ✗ | △ (Keccak indiff.) |
| Tree mode | ★★★ | ★★ | ★★★ | ★★ |
| Crypto strength | 256-bit | 128-bit | 256-bit | 128-bit (Kt128) |
| Maturity | v0.1 | v0.1 | 광범위 | 표준 후보 |

## 6. 정직한 평가

### BLAKE3가 최강
SIMD 최적화 + multi-core 자동 분할. 큰 입력에서 K12의 7배. yhash 패밀리와 *본질적 격차*.

### K12 0.5.1이 K12 0.3 대비 크게 개선됨
- State: 9144 → 424 byte (21× 축소)
- Small input throughput: 35 → 98 MB/s (3× 가속)
- K12가 *예전의 yhash 자리*를 차지

### YHash 패밀리의 자리 *재평가*
K12 0.5.1과의 비교에서 패밀리 위치가 조정됨:

- **K12**가 일반적인 *secure hash + small state*의 강자
- **ypsilenti**: K12의 ~1/2 throughput이지만 **128-bit 보안 영역에서 K12와 동급 충돌 저항**, *형식 검증된 사양*
- **yhash**: 256-bit 보안이 필수일 때만. 그 외엔 BLAKE3가 우월

### 누가 무엇을 선택하나
- **광범위 secure hash**: BLAKE3
- **표준 호환 + sponge 친화**: K12 (TurboSHAKE family)
- **256-bit + formal verification + Farfalle-tree**: yhash
- **128-bit + 형식 검증 + 임베디드**: ypsilenti
- *content-addressed storage with verified streaming*: yhash 또는 BLAKE3

## 7. 향후 가속 여지 → **실측 (Level B SIMD + 병렬 트리)**

§1–6은 *최적화 이전*(scalar, 단일 thread) 기준이다. 이후 적용:
**Level B SIMD**(leaf 블록 batch, nightly `core::simd` / stable `wide`) +
**병렬 트리 빌드**(rayon). 아래는 동일 호스트(x86_64, 16 thread) 재측정.

> 주의: dev 박스라 절대치는 run마다 흔들린다(BLAKE3도 6.2~8.4 GB/s 사이).
> **비율**과 *자릿수*가 핵심.

### 7.1 단일 thread throughput (MB/s)

| 입력 | yhash | ypsilenti | BLAKE3 | K12 |
|------|------:|----------:|-------:|----:|
| 256 B  |   58 |      387 |    916 |   597 |
| 1 KB   |  236 |      352 |    998 |   797 |
| 4 KB   |  191 |      343 |  2,796 |   907 |
| 64 KB  |  179 |      337 |  6,466 |   943 |
| 1 MB   |  180 |      341 |  6,246 |   934 |

SIMD 적용 효과 (단일 thread, 1 MB, 같은 도구 scalar→SIMD):
- yhash 115 → 180 MB/s (**1.56×**)
- ypsilenti 200 → 341 MB/s (**1.71×**)

### 7.2 멀티 thread throughput (rayon, 16 thread, MB/s)

| 입력 | yhash | ypsilenti | BLAKE3 | K12(1T) |
|------|------:|----------:|-------:|--------:|
| 1 MB   | 1,634 |    2,573 | 31,189 |   937 |
| 16 MB  | 1,956 |    3,080 | 50,652 |   925 |
| 64 MB  | 2,076 |    3,209 | 39,848 |   935 |

`k12` 크레이트는 손쉬운 MT API가 없어 단일 thread로 측정.

### 7.3 종합 — 향상분 + 경쟁 위치

- **ypsilenti**: scalar 1-thread 200 → SIMD+rayon **3,209 MB/s ≈ 16×**.
  이제 **K12(단일 thread)를 ~3.4× 앞서고**, BLAKE3 *단일 thread*의 약 절반.
- **yhash**: SIMD+rayon **~2.1 GB/s**. K12를 ~2.2× 앞서나 256-bit라 무겁다.
- **BLAKE3는 여전히 다른 리그**: 단일 thread ~6.2 GB/s(런타임 AVX2/AVX-512
  hand-tuned + 멀티블록), rayon ~40 GB/s. 우리의 portable `core::simd`/`wide`
  Level B로는 MT에서도 BLAKE3 MT의 ~1/12~1/20.

→ 결론: **예측은 절반만 적중.** SIMD+MT로 K12를 (특히 MT에서) 추월했고
자릿수가 GB/s대로 올라왔지만, BLAKE3의 hand-optimized SIMD + 성숙한 rayon
통합과는 여전히 본질적 격차가 남는다.

## 8. 재현

```bash
cd yhash-bench
# 최적화 전 (scalar, 단일 thread)
cargo run --release --bin secure_bench
# SIMD(nightly) + 멀티thread + BLAKE3 rayon
cargo +nightly run --release --bin secure_bench --features simd,mt
# stable SIMD(wide) + 멀티thread
cargo run --release --bin secure_bench --features simd-stable,mt
```

크레이트 버전: `blake3 = "1"` (rayon feature), `k12 = "0.5"` (v0.5.1).
