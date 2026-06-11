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

## 3. MT 스케일링 — `hash_parallel` × spawner (Level B + 병렬 트리 빌드)

speedup은 SerialSpawner 대비. std-thread는 active-thread 캡 적용.
**트리 빌드(internal 노드 합성)도 병렬화** — 이전엔 leaf만 병렬이고 트리 reduction이
순차라 ~2×에서 포화했다. 이제 트리도 divide-and-conquer로 병렬.

| crate | size | serial | std-thread | rayon |
|-------|------|--------|-----------|-------|
| yhash | 256 KiB | 184.6 | 286.0 (1.55×) | 938.1 (5.08×) |
| yhash | 1 MiB | 184.8 | 594.3 (3.22×) | 1630.2 (8.82×) |
| yhash | 16 MiB | 183.9 | 1154.1 (6.28×) | 1826.4 (9.93×) |
| yhash | 64 MiB | 184.3 | 1284.3 (6.97×) | 1800.6 (9.77×) |
| ypsilenti | 256 KiB | 336.5 | 229.1 (0.68×) | 1794.7 (5.33×) |
| ypsilenti | 1 MiB | 337.9 | 572.1 (1.69×) | 2583.8 (7.65×) |
| ypsilenti | 16 MiB | 334.6 | 1334.1 (3.99×) | 2840.4 (8.49×) |
| ypsilenti | 64 MiB | 336.1 | 1436.1 (4.27×) | 2910.2 (8.66×) |

### 관찰

- **트리 빌드 병렬화로 rayon이 ~2× → ~8–10×로 도약** (16 코어). 이전의 Amdahl
  병목(순차 reduction)이 제거됐다. 절대 throughput: yhash rayon ~1.8 GB/s,
  ypsilenti rayon ~2.9 GB/s.
- **std-thread**도 큰 입력에서 ~4–7×까지 스케일 (캡 + 트리 병렬). 작은 입력
  (256 KiB)의 ypsilenti 0.68×는 thread 조율 오버헤드 — 작은 입력은 rayon 권장.
- **rayon이 가장 안정적** — work-stealing 풀. 실사용 권장.
- 병렬 트리 빌드는 `TreeBuilder`의 binary-counter 형태를 재귀로 *정확히 복제*
  (완전 부분트리 + 상단 fold) → 직렬과 비트단위 동일. leaf 수 1..=40 전수 검증.

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
2. ~~트리 빌드 병렬화~~ — **완료**: divide-and-conquer 재귀로 internal 합성 병렬
   (rayon ~8–10× 달성). KAT 동일성 유지.
3. **internal 노드 batch** — 2-block이라 이득이 작지만 깊은 트리에서 고려.
4. **작은 입력 std-thread** — 256 KiB대에서 near-parity. spawn 임계값 튜닝 여지.
