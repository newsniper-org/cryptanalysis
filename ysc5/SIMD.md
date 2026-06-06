# YSC5 SIMD backend (nightly)

`feature = "simd"` 활성화 시 nightly Rust의 `core::simd` (= `portable_simd`)를 사용한 SIMD 백엔드가 컴파일됨.

## 빌드

```bash
# 기본 (stable, no SIMD)
cargo build --release

# Nightly + SIMD
rustup install nightly
cargo +nightly build --release --features simd
```

## 매핑

Farfalle의 16-워드 상태가 `u64x4 × 4`에 자연 매핑:

| 연산 | Soft 구현 | SIMD 변종 |
|------|----------|-----------|
| XOR-reduce ⊕ᵢ state[i] | 16 XOR | 4 lane-wise XOR + 4-way reduce |
| Broadcast state[i] ⊕= T | 16 XOR | 4 `u64x4 ^= u64x4::splat(T)` |
| F: rot + AND | per-word | per-word (회전이 SIMD에서 비싸지 않음) |
| γ roll | 16 α-mult | 동시 4 lane × 4 vec, 거듭제곱 인덱스만 다름 |
| π 워드 순열 | 단순 인덱싱 | shuffle intrinsic |

## 성능 기대치

- Compression의 핵심 비용은 `ysc4::permutation::permute` 호출. ysc4의 simd feature가 활성화되면 자동 가속.
- YSC5 추가 비용 (roll, broadcast, reduce)도 4배 SIMD 가속.
- 예상 throughput: stable 259 MB/s → simd 800-1200 MB/s (단일 thread).

## 한계

- `core::simd`는 nightly 전용 (안정화는 RFC #3499 진행 중).
- ARM NEON, AVX2/AVX-512 자동 매핑 — 컴파일 타깃의 SIMD 지원 능력에 의존.
- WASM SIMD (`v128`)도 지원되지만 추가 검증 필요.

## Soft vs SIMD 일관성

`tests::simd_roll_matches_soft` 등에서 soft와 simd 결과가 *비트 단위 동일* 함을 검증.
이로써 SIMD 백엔드는 soft 사양의 *동등 구현*이지 *다른 알고리즘*이 아님 (V7 결함 회피).

## 향후 작업

- AVX-512 path: `u64x8 × 2`로 더 큰 SIMD 폭 활용.
- FMA / VPCLMULQDQ 활용 가능성 (GF$(2⁶⁴)$ 곱 가속).
- ARM SVE 분기.
