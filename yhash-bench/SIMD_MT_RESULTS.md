# SIMD / MT 벤치 매트릭스 결과

측정: `cargo +nightly run --release -p yhash_bench --bin simd_mt --features simd,mt`
호스트: x86_64, 16 logical threads (rayon pool).

> 절대 수치는 호스트마다 다르다. 중요한 건 **상대 비율(speedup)** 과 그 *경향*.
> 이 문서는 **Level B SIMD + std-thread 캡** 적용 후 결과다.
> (이전 Level A SIMD는 회귀였고 std-thread는 스케일 실패했음 — 아래 "변경 이력" 참고.)

## 1. leaf 8-block 압축 — scalar vs Level B SIMD

leaf의 8개 블록 mask-derive + compress를 lane에 실어 batch 처리.

**nightly** (`core::simd`, `--features simd`):

| 대상 | 블록 | scalar | Level B SIMD | speedup |
|------|------|--------|--------------|---------|
| yhash | 8 × 128 B (16×u64) | 3738.0 ns | 1724.5 ns | **2.17×** |
| ypsilenti | 8 × 32 B (8×u32) | 631.8 ns | 161.4 ns | **3.92×** |

**stable** (`wide` crate, `--features simd-stable`, 안정 채널):

| 대상 | 블록 | scalar | Level B SIMD | speedup |
|------|------|--------|--------------|---------|
| yhash | 8 × 128 B | 4830.3 ns | 2746.1 ns | **1.76×** |
| ypsilenti | 8 × 32 B | 841.1 ns | 328.2 ns | **2.56×** |

- ypsilenti(u32x8)는 8 lane이 한 AVX2 레지스터에 맞아 nightly ~3.9× / stable ~2.6×.
- yhash(u64)는 nightly u64x8(512-bit, AVX-512 없으면 2분할) ~2.2×,
  stable은 `wide` 최대 u64x4라 8블록을 4-lane **2 chunk**로 처리 → ~1.8×.
- stable이 nightly보다 낮은 건 (a) u64 2-chunk, (b) `wide`의 코드젠이
  `core::simd`보다 약간 보수적이기 때문. 그래도 scalar 대비 분명한 이득.
- 모든 경로 batch 결과 == scalar 결과를 런타임 assert로 검증.

## 2. 전체 해시 throughput (streaming 직렬)

| size | yhash | ypsilenti |
|------|-------|-----------|
| 1 KiB | 307.2 MB/s | 471.0 MB/s |
| 4 KiB | 254.1 MB/s | 463.6 MB/s |
| 64 KiB | 242.6 MB/s | 461.4 MB/s |
| 1 MiB | 242.7 MB/s | 457.2 MB/s |

Level B 적용으로 scalar 대비: yhash ~160 → ~242 MB/s (**1.5×**),
ypsilenti ~150 → ~460 MB/s (**3.0×**). leaf 압축이 throughput의 지배 항이라
leaf-batch 가속이 그대로 반영된다.

## 3. MT 스케일링 — `hash_parallel` × spawner (Level B 빌드)

speedup은 SerialSpawner 대비. std-thread는 active-thread 캡 적용.

| crate | size | serial | std-thread | rayon |
|-------|------|--------|-----------|-------|
| yhash | 256 KiB | 245.6 | 328.4 (1.34×) | 456.7 (1.86×) |
| yhash | 1 MiB | 244.0 | 378.0 (1.55×) | 458.6 (1.88×) |
| yhash | 16 MiB | 244.6 | 467.6 (1.91×) | 496.1 (2.03×) |
| yhash | 64 MiB | 241.8 | 484.6 (2.00×) | 494.7 (2.05×) |
| ypsilenti | 256 KiB | 460.3 | 424.9 (0.92×) | 777.7 (1.69×) |
| ypsilenti | 1 MiB | 464.0 | 567.8 (1.22×) | 785.4 (1.69×) |
| ypsilenti | 16 MiB | 450.3 | 725.7 (1.61×) | 838.5 (1.86×) |
| ypsilenti | 64 MiB | 462.2 | 767.7 (1.66×) | 872.4 (1.89×) |

### 관찰

- **serial baseline 자체가 Level B로 ~3× 빨라져** MT의 상대 speedup 숫자는
  이전보다 작아 보이지만, *절대 throughput*은 전부 크게 올랐다
  (ypsilenti rayon 872 MB/s).
- **std-thread 캡이 회귀를 해소**: 이전엔 ypsilenti가 0.58×까지 떨어졌으나
  (per-join thread 폭증), 캡 후 0.92×(최소 크기)~1.66×로, 크기가 커질수록
  양(+)의 스케일. 작은 입력에서 near-parity는 thread 조율 오버헤드 탓.
- **rayon이 여전히 가장 안정적** — work-stealing 풀. 실사용 권장.
- MT가 ~2× 부근에서 포화하는 건 (a) 트리 빌드가 순차, (b) leaf-batch SIMD가
  이미 메모리 대역폭을 많이 쓰기 때문 (Amdahl + bandwidth bound).

## 변경 이력 — 왜 Level B로 갔나

초기 **Level A SIMD**(상태 전체를 한 벡터에)는 *회귀*였다: yhash 0.58×, ypsilenti
0.73×. 원인은 매 라운드의 수평 `reduce_xor` + σ-층 lane 추출(extract/insert).
→ **Level B(inter-block batch)** 로 교체: 독립 블록 8개를 lane에 실어 동일 연산을
lane-병렬 적용, 수평 연산은 라운드 밖(최종 fold)으로. 결과는 위 표.

초기 **StdThreadSpawner**는 `join`마다 thread를 spawn해 O(leaves) thread 폭증으로
스케일 실패(ypsilenti <1×). → active-thread **캡**(`available_parallelism()`) 추가,
도달 시 직렬 fallback. 결과는 §3.

## 남은 후속 작업

1. ~~stable SIMD~~ — **완료**: `wide` crate로 stable Level B 구현 (위 표).
2. **트리 빌드 병렬화** — 현재 leaf만 batch/병렬, internal 합성은 순차.
3. **internal 노드 batch** — 2-block이라 이득이 작지만 깊은 트리에서 고려.
