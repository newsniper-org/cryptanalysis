# SIMD / MT 벤치 매트릭스 결과

측정: `cargo +nightly run --release -p yhash_bench --bin simd_mt --features simd,mt`
호스트: x86_64, 16 logical threads (rayon pool).

> 절대 수치는 호스트마다 다르다. 중요한 건 **상대 비율(speedup)** 과 그 *경향*.

## 1. 순열 micro-bench — scalar vs SIMD (Level A)

| 순열 | 상태 | scalar | SIMD | speedup |
|------|------|--------|------|---------|
| ysc4 perm | 1024-bit (16×u64) | 108.4 ns | 187.2 ns | **0.58×** |
| ypsi perm | 256-bit (8×u32) | 110.2 ns | 150.6 ns | **0.73×** |

### ⚠️ Level A SIMD는 현재 *회귀(regression)*

`core::simd`로 상태 전체를 한 벡터에 담는 **Level A (intra-permutation)** 방식은
이 순열 구조에서 scalar보다 느리다. 원인:

1. **수평 reduction**: 매 라운드 `S = ⊕ᵢ stateᵢ` (`reduce_xor`)는 SIMD에 비친화적인
   수평 연산. lane-병렬성이 없다.
2. **σ-층의 lane 추출**: `αᵏ` 곱은 특정 lane(0/4/8/12)에만 적용되므로 벡터를
   배열로 꺼내(`to_array`) scalar로 계산 후 다시 싣는다(`from_array`).
   이 extract/insert가 라운드마다 발생.
3. 순열 한 번의 작업량(16 워드)이 작아 SIMD 셋업 비용을 못 갚는다.

→ **결론**: Level A는 이 σ-GLM 구조에 부적합. 가속하려면 **Level B
(inter-block batching)** — 독립 블록 N개를 N개 lane에 실어 *동일 연산을 병렬*
적용 — 이 맞다. leaf 내 T_MAX개 블록 또는 leaf 간 병렬이 후보. (후속 작업)

## 2. 전체 해시 throughput (streaming 직렬)

| size | yhash | ypsilenti |
|------|-------|-----------|
| 1 KiB | 183.8 MB/s | 152.3 MB/s |
| 4 KiB | 165.5 MB/s | 150.8 MB/s |
| 64 KiB | 159.4 MB/s | 151.2 MB/s |
| 1 MiB | 159.9 MB/s | 149.0 MB/s |

순열이 곧 병목 — throughput은 크기와 무관하게 ~150–160 MB/s로 수렴.

## 3. MT 스케일링 — `hash_parallel` × spawner

speedup은 SerialSpawner 대비.

| crate | size | serial | std-thread | rayon |
|-------|------|--------|-----------|-------|
| yhash | 256 KiB | 160.3 | 304.9 (1.90×) | 463.4 (2.89×) |
| yhash | 1 MiB | 159.9 | 276.6 (1.73×) | 453.0 (2.83×) |
| yhash | 16 MiB | 159.6 | 244.9 (1.53×) | 505.6 (3.17×) |
| yhash | 64 MiB | 158.9 | 232.5 (1.46×) | 509.6 (3.21×) |
| ypsilenti | 256 KiB | 148.8 | 124.2 (0.83×) | 451.5 (3.03×) |
| ypsilenti | 1 MiB | 149.2 | 115.8 (0.78×) | 437.9 (2.93×) |
| ypsilenti | 16 MiB | 148.3 | 91.8 (0.62×) | 484.6 (3.27×) |
| ypsilenti | 64 MiB | 148.5 | 86.7 (0.58×) | 498.6 (3.36×) |

### 관찰

- **rayon ~3×** — work-stealing 풀이 안정적. 16 코어에서 3× 정도면 divide-and-conquer
  분할 임계값(`PARALLEL_LEAF_THRESHOLD=8`)과 트리 빌드(순차)의 Amdahl 한계 때문.
- **std-thread는 스케일 실패** (특히 ypsilenti는 1× 미만!). `StdThreadSpawner`는
  `join`마다 `std::thread::scope`로 새 스레드를 spawn → divide-and-conquer가 O(leaves)
  개의 스레드를 만든다. 스레드 생성 비용이 leaf 계산보다 커지면(ypsilenti는 leaf가
  작아 더 심함) 직렬보다 느려진다.
  → 실사용은 **rayon spawner 권장**. std-thread는 풀이 없는 환경의 fallback.

## 시사점 / 후속 작업

1. **Level A SIMD 제거 또는 Level B로 교체** — 현재 SIMD 경로는 켜면 손해.
   (dispatcher는 유지하되 SIMD 구현을 Level B batch로 바꿔야 이득.)
2. **`hash_parallel` 분할 임계값 튜닝** + 트리 빌드 병렬화로 rayon 스케일 개선 여지.
3. **`StdThreadSpawner` 개선** — per-join spawn 대신 depth 제한(상위 몇 레벨만 spawn)
   두면 thread 폭증을 막을 수 있다.
