# yttrium 처리량 벤치마크 (v0.2-pre)

> `cargo run --release --example bench -p yttrium` (taskset 코어고정, 1 MiB 동일 입력, 적응형 ≥0.5s).
> 대표 1회 측정(공유 호스트라 ±변동). **상대·구조 비교용**(절대수치 아님).

## ⚠ 공정성 caveat (결과 해석 전 필독)

- **yttrium = scalar 레퍼런스** (SIMD·멀티스레드 **없음**). BLAKE3=SIMD, SHA3/SipHash=최적화
  라이브러리. → **비대칭 비교**. yttrium 수치는 *미최적화 레퍼런스*이지 알고리즘 잠재력이 아니다.
- **yttrium-large 라운드수**: 변형패밀리 그대로. u64 보안레벨 정당화 완료
  (`milp/yttrium-large-rounds.md`) — u64 감쇠가 u32의 ~2배(16레인)라 **(10,14,24)-large가 full
  128-bit 충돌저항**(256-bit digest 상한). 즉 본 벤치 변형들은 그 보안레벨에서의 실측치다.
- yttrium-large는 가변출력을 최종상태 **truncation**(≤1024-bit)으로 제공 → 출력길이 무관하게 동일 비용.

## 결과 (MB/s)

### (1) key=256b, out=128b — BLAKE3 vs yttrium-large
| 함수 | MB/s | vs BLAKE3 |
|---|--:|--:|
| **BLAKE3** (keyed, SIMD) | **7373** | 1.0× |
| yttrium-(4,6,8)-large | 160 | 1/46 |
| yttrium-(4,6,12)-large | 120 | 1/61 |
| yttrium-(8,12,24)-large | 50 | 1/147 |
| yttrium-(10,14,24)-large | 35 | 1/210 |

### (2) key=128b, out=64b — SipHash-2-4 vs yttrium
| 함수 | MB/s | vs SipHash |
|---|--:|--:|
| **SipHash-2-4** | **3659** | 1.0× |
| yttrium-(4,6,8) | 99 | 1/37 |
| yttrium-(4,6,12) | 77 | 1/47 |
| yttrium-(8,12,24) | 39 | 1/93 |
| yttrium-(10,14,24) | 38 | 1/98 |

### (3) no key — SHA3 vs yttrium-large
| 출력 | SHA3 | y-(4,6,8) | y-(4,6,12) | y-(8,12,24) | y-(10,14,24) |
|---|--:|--:|--:|--:|--:|
| 256b | 535 | 162 | 121 | 62 | 59 |
| 384b | 415 | 162 | 122 | 62 | 58 |
| 512b | 287 | 161 | 122 | 63 | 58 |

## 관찰 (정직)

1. **전반**: yttrium scalar는 경쟁자 대비 8–210× 느림 — *예상*(미최적화 레퍼런스 vs SIMD/최적화 라이브러리).
2. **격차 최소는 SHA3 대비**: SHA3도 permutation 해시(SIMD 친화도 낮음). yttrium-large-(4,6,8)(161)은
   **SHA3-512(287)의 0.56×** — lite 변형은 SHA3-512에 근접. SHA3-256(535)엔 1/3.3.
3. **large > u32 (per-byte)**: 동일 변형 (8,12,24)서 large 50 vs u32 39 MB/s — u64가 블록당 4× 바이트
   처리해 라운드 비용(σ 137 vs 37 α-step) 상쇄·초과.
4. **출력길이**: yttrium-large는 truncation이라 256/384/512 무관 동일(58~62). SHA3는 rate 축소로 출력↑
   시 느려짐(535→287). 긴 출력서 격차 축소.
5. **변형 스프레드**: (4,6,8)↔(10,14,24) ≈ 4.5×(large)/2.6×(u32). 라운드수가 비용 지배.
6. **SIMD 잠재력(미구현)**: ypsilenti/yhash는 SIMD로 BLAKE3 격차를 크게 좁혔음(저장소 README). yttrium
   레퍼런스는 scalar뿐 — Level-B SIMD·병렬 트리 적용 시 격차 대폭 축소 예상(잔여 작업).

## 재현
```bash
cargo run --release --example bench -p yttrium   # taskset -c N 권장
```

---

## 2차 벤치 (SIMD on, `--features simd`)

Level-B SIMD(inter-block batch: u32x8 8-lane / u64x4 4-lane) 적용 후 (1 MiB, 코어고정).

| 비교 | 경쟁자 | yttrium (scalar → SIMD) MB/s | 배속 |
|---|---|---|---|
| (1) BLAKE3 ~8400 | large-(10,14,24) | 35.1 → 66.0 | 1.88× |
| | large-(8,12,24) | 50.1 → 70.5 | 1.41× |
| | large-(4,6,8) | 160.1 → 180.8 | 1.13× |
| (2) SipHash ~3580 | u32-(8,12,24) | 33.9 → 72.5 | 2.14× |
| | u32-(4,6,8) | 84.6 → 181.4 | 2.14× |
| (3) SHA3-512 285 | large-(4,6,8) | 161 → 177.8 | 1.10× (≈SHA3-512×0.62) |

관찰:
- **u32 ~2.1×**(u32x8=8레인), **large ~1.1-1.9×**(u64x4=4레인이라 병렬도 절반). lite 변형은
  leaf 비중↓라 가속률↓.
- **leaf 블록압축만 배치** — finalize·internal(2-block)·mask-mid(single)는 scalar라 부분가속.
  내부노드 배치·rayon 병렬트리·AVX-512는 추가 여지(잔여).
- 여전히 BLAKE3/SipHash(SIMD+수년 최적화)엔 크게 못 미침. **SHA3-512엔 lite 변형 근접**(0.62×).
- (BLAKE3 절대치는 run간 변동 ~7400-8400; 공유호스트.)

---

## 3차: 병렬 (멀티스레드, `--features "simd parallel"`)

16 MiB, 16 cores, SIMD on (스레드 오버헤드 amortize 위해 큰 입력).

| 경로 | MB/s | vs serial |
|---|--:|--:|
| yttrium-(8,12,24) serial(1-thread) | 70.9 | 1.0× |
| yttrium-(8,12,24) parallel(std-thread) | 445.4 | **6.3×** |

- 병렬(Spawner divide-and-conquer, 부분트리 분산)이 SIMD와 조합 → **SIMD 2.1× × 병렬 6.3×**.
- (8,12,24) 445 MB/s는 **SHA3-256(535)의 0.83×** 권역. 멀티스레드가 throughput의 실질 레버.
- 멀티스레드는 optional feature(`parallel`); no_std는 SerialSpawner(직렬) 또는 임베더 Spawner 구현.
- (cross-leaf/internal SIMD 레벨배치는 internal 노드 지배+transpose 오버헤드로 순효과 마이너스라
  미채택 — 1차 벤치 관찰. 병렬이 그 역할을 대체.)
