# cryptanalysis/ — YSC 패밀리 cryptanalysis & 재설계 작업

> *외부 검토를 위한 진입 문서.* 본 저장소는 (1) `newsniper-org/ysc2`의 cryptanalysis,
> (2) 그 결과를 반영한 *순차적 재설계* (YSC3 → YSC4 → YSC5), (3) Isabelle/HOL 형식 검증,
> (4) Typst 사양서, (5) MILP 차분 분석을 포함한다.

## 영문 abstract

We analyzed the stream cipher YSC2 (Bertoni et al.-style permutation, sponge mode) published at
`newsniper-org/ysc2`. We found *ten* vulnerabilities (V1~V10), six of which are *specification-level*
fatal flaws that allow full key recovery from a single 128-byte known-plaintext block.

We propose three redesigned ciphers as direct successors:

- **YSC3** — NORX-style generalized Feistel network on a sponge mode.
- **YSC4** — σ-Generalized Lai-Massey on a sponge mode (1/6 FHE AND count of YSC3).
- **YSC5** — same σ-GLM permutation as YSC4, but in *Farfalle* (parallel) construction.

The crucial *natural bridge* is that YSC4's σ-orthomorphism (multiplication by α in $"GF"(2^{64})$ with the
ISO-3309 polynomial) simultaneously satisfies (i) the Vaudenay orthomorphism conditions for the
Lai-Massey construction AND (ii) Farfalle's mask-roll requirements. We *formally verify* in Isabelle/HOL
that α is a primitive element of $"GF"(2^{64})^*$ with order $2^{64} - 1$, and that the cycle lengths of
$α^k$ for $k \in \{1, …, 16\}$ exceed $2^{60}$ — sufficient for any practical usage.

All three successor ciphers are implemented as `no_std` Rust crates with musl as the default target,
following RustCrypto trait conventions. Comprehensive test suites verify that the v1 attacks on YSC2
do *not* succeed against any of YSC3/YSC4/YSC5.

## 디렉토리 구조

```
cryptanalysis/
├── REPORT.md                       # YSC2 v1.0 cryptanalysis 보고서 (V1~V10)
├── attack/                         # YSC2 공격 PoC (Rust) — REPORT의 결함을 실증
│   └── src/recover_ysc2_*.rs
├── ysc2/                           # 원본 YSC2 저장소 (clone)
├── ysc3/                           # YSC3 (GFN sponge) — Rust + Typst SPEC
│   ├── SPEC.md, SPEC.typ, SPEC.pdf
│   ├── src/, tests/                # no_std + musl + 18 tests
├── ysc4/                           # YSC4 (σ-GLM sponge) — Rust + Typst SPEC
│   ├── SPEC.md, SPEC.typ, SPEC.pdf
│   ├── src/, tests/                # 24 tests
├── ysc5/                           # YSC5 (Farfalle) — RustCrypto convention
│   ├── SPEC.typ, SPEC.pdf          # 19-페이지 Typst 사양서
│   ├── SIMD.md                     # nightly portable_simd 가이드
│   ├── src/, tests/                # 26 tests, ysc5x feature로 AEAD/XOF/MAC
├── yhash/                          # YHash (256-bit) — Farfalle-tree hash on YSC4-p
│   ├── src/, tests/                # no_std, HashMap BuildHasher, RustCrypto digest
│   └── (SIMD: perm_simd, MT: spawner/parallel)
├── ypsilenti/                      # ypsilenti (128-bit) — downsized YHash (8×u32 σ-GLM)
│   ├── SPEC-draft.md, build.rs     # SIMD feature 검증
│   └── src/, tests/                # no_std, 동일 SIMD/MT 인프라
├── yhash-verify/, ypsilenti-verify/ # 형식 검증 (Q1'~, Y1'~)
├── yhash-bench/                    # YHash/ypsilenti vs BLAKE3 vs K12 벤치
│   ├── SECURE_HASH_COMPARISON.md   # 경쟁 해시 대비 throughput
│   └── SIMD_MT_RESULTS.md          # Level B SIMD / 멀티스레드 매트릭스
├── xtask/, presets/                # SIMD target-feature preset 적용 자동화
├── WASM.md                         # WebAssembly(simd128) 빌드 가이드
├── bench/                          # YSC3 vs YSC4 vs YSC5 비교 (throughput, FHE 비용)
├── farfalle-gen/                   # Farfalle 일반화 meta-task
│   ├── META.md                     # 설계 공간 6개 축으로 분해
│   ├── NOTE-orthomorphism-roll-coincidence.md  # YSC4 ↔ Farfalle 정합성
│   ├── NOTE-fhe-cost.md            # TFHE/BFV 백엔드별 비용 추정
│   ├── NOTE-aead-nonce-split.md    # Kravatte-SANE 식 vs 현 사양
│   ├── NOTE-multikey-security.md   # Mennink-style 환원
│   └── RESOLVED-q3-q8.md           # 미해결 6개 질문의 현 상태
├── isabelle-verify/                # Isabelle/HOL 형식 검증 (YSC_Probe session)
│   ├── GF64.thy                    # GF(2⁶⁴) 산술 (64 word 기반)
│   ├── Q1_Primitivity.thy          # α primitive element 증명
│   ├── Q2_Cycles.thy               # ord(α^k) 분포 검증
│   ├── Q3_RollMatrix.thy           # γ roll의 1-단계 distinct 검증
│   └── LOG.md                      # 빌드·증명 결과
└── milp/                           # MILP 차분 트레일 분석 (GLPK)
    ├── model.mod                   # 워드-수준 활성 트레일 모델
    └── analysis.md                 # R∈{8,12,16} 결과 + bit-level 후속작
```

## 핵심 발견 (한 문장 요약)

> *YSC4가 Lai-Massey 구조의 약점을 메우려고 도입한 "σ = $"GF"(2^{64})$ 곱" 한 줄이,
> 동시에 Farfalle의 mask-roll 요구사항을 *수학적으로 최적*으로 충족한다.
> 즉 YSC5는 별도의 새 primitive 도입 없이 YSC4-p × Farfalle 만으로 정의 가능하다.*

이 *우연한 정합*이 이 작업 전체의 메타-구조다.

## YHash 패밀리 — 해시 함수 (성능)

YSC4-p / σ-GLM 순열을 **Farfalle-tree 해시**로 재사용한 파생 작업:

- **yhash** — 256-bit digest, 1024-bit 상태 (YSC4-p 순열 재사용).
- **ypsilenti** — 128-bit digest, 256-bit 상태 (8×u32 σ-GLM 축소판). HashMap/임베디드용.

둘 다 `no_std` + `forbid(unsafe_code)`, `core::hash::BuildHasher` 및 RustCrypto
`digest` 호환. tree 모드라 블록 단위 병렬 처리가 자연스럽다.

### 성능 최적화 (Level B SIMD + 멀티스레드)

순열 가속은 *단일 순열*이 아니라 leaf의 **독립 블록 8개를 SIMD lane에 싣는**
inter-block batch(“Level B”)로 한다. 백엔드 2종:

- `nightly-portable-simd` — `core::simd` (u32x8 / u64x8)
- `stable-portable-simd` — `wide` crate (안정 채널, u32x8 / u64x4)

| 항목 | scalar 대비 |
|------|------------|
| leaf 압축 (ypsilenti) | nightly **3.9×** / stable **2.6×** |
| leaf 압축 (yhash) | nightly **2.2×** / stable **1.8×** |
| 멀티스레드 트리 빌드 (rayon, 16 thread) | rayon 스케일 **~8–10×** |

종합 throughput (x86_64, 16 thread; 절대치는 환경마다 다름):

| | 단일 thread (AVX) | rayon (16 thread) |
|------|------:|------:|
| ypsilenti | ~390 MB/s | **~3.2 GB/s** |
| yhash | ~250 MB/s | ~2.1 GB/s |
| K12 (참고) | ~0.93 GB/s | (단일) |
| BLAKE3 (참고) | ~6.3 GB/s | ~40 GB/s |

scalar 1-thread 대비 **ypsilenti ~16×**(SIMD+rayon)로, 멀티스레드에서 K12를
~3.4× 추월. 다만 BLAKE3의 hand-tuned AVX2/512 + 성숙한 rayon과는 본질적 격차가
남는다 (원인은 ISA가 아니라 라운드당 연산량 — σ-GLM의 GF 곱 + 마스크 유도).
멀티스레딩은 `Spawner` trait로 추상화돼 `no_std`에서도 임베더가 플랫폼 동시성을
주입할 수 있다. 자세한 수치·재현은 `yhash-bench/SIMD_MT_RESULTS.md`,
`yhash-bench/SECURE_HASH_COMPARISON.md` 참고.

> ⚠️ **이 성능 수치는 *internal v0.1* 기준이다.** 형식검증된 것은 *대수적 정확성*
> (아래 T1)뿐이며, **모드 보안 환원(T3)과 구체 순열의 암호분석(T4)은 미완**이다.
> 빠르다는 것이 안전하다는 뜻은 아니다 — frozen/on-disk·production 채택 전에는
> [검증 성숙도](#검증-성숙도와-채택-전제조건-r1r5) 섹션의 R1–R5를 먼저 충족해야 한다.

## 재현

### 1. YSC2 cryptanalysis (v1 공격 모음)

```bash
cd attack && cargo run --release --bin recover_ysc2_state
cd attack && cargo run --release --bin recover_ysc2_key
cd attack && cargo run --release --bin recover_auxcrypt_key
```

### 2. YSC3/YSC4/YSC5 빌드 및 테스트

```bash
cd ysc5 && cargo test --release --features ysc5x
# 26개 테스트 모두 통과 (lib unit + integration + RustCrypto traits)

cd bench && cargo run --release
# YSC3 (576 MB/s) vs YSC4 (243 MB/s) vs YSC5 (259 MB/s) 비교
```

### 2-b. YHash 패밀리 (해시) 빌드·벤치

```bash
cd yhash && cargo test                 # yhash 테스트 (scalar)
cd ypsilenti && cargo test             # ypsilenti 테스트

# SIMD + 멀티스레드 매트릭스 (nightly: core::simd)
cd yhash-bench
cargo +nightly run --release --bin simd_mt --features simd,mt
# stable SIMD (wide crate)
cargo run --release --bin simd_mt --features simd-stable,mt

# 경쟁 해시 비교 (BLAKE3/K12). AVX는 preset 또는 target-cpu로 켤 것:
RUSTFLAGS="-C target-cpu=native" \
  cargo +nightly run --release --bin secure_bench --features simd,mt
```

### 3. Isabelle/HOL 형식 검증

```bash
cd isabelle-verify && /opt/isabelle/bin/isabelle build -D .
# YSC_Probe session 빌드. by eval로 Q1/Q2/Q3 모든 정리 통과.
```

### 4. MILP 차분 분석

```bash
cd milp && glpsol --math model.mod --tmlim 60
# 워드-수준 트레일 분석 (보수적 하한)
```

### 5. Typst 사양서 컴파일

```bash
cd ysc5 && typst compile SPEC.typ
# 19-페이지 PDF 생성
```

## 환경 요구사항

| 도구 | 버전 | 용도 |
|------|------|------|
| Rust (stable) | 1.96+ | 모든 Rust 크레이트 (`stable-portable-simd`는 `wide` crate) |
| Rust nightly | optional | `nightly-portable-simd` (`core::simd`), YSC5 `simd` |
| musl target | x86_64-unknown-linux-musl | 정적 빌드 |
| AVX preset | `xtask -- preset x86-64-v3` 또는 `RUSTFLAGS=-C target-cpu=native` | SIMD 실효 (기본 타깃은 SSE2) |
| Isabelle/HOL | 2025-2 | 형식 검증 |
| GLPK | 4.52+ | MILP 분석 |
| Typst | 0.14.x | 사양서 컴파일 |

## 라이선스

BSD-2-Clause (원본 ysc2 라이선스 계승).

## 인용

```bibtex
@misc{ysc-family-2026,
  author = {YSC Project},
  title  = {Cryptanalysis of YSC2 and Iterative Redesign Suite: YSC3, YSC4, YSC5},
  year   = {2026},
  note   = {Includes Isabelle/HOL formal verification of GF(2^64) primitivity},
}
```

## 검증 성숙도와 채택 전제조건 (R1–R5)

본 작업은 전체가 *internal v0.1* 단계다. 특히 **YHash 패밀리(yhash/ypsilenti)를
frozen on-disk 포맷이나 production 원시함수로 채택**하려는 다운스트림을 위해, 현재
검증 성숙도와 남은 전제조건을 정직하게 밝힌다.

### 4-tier 검증 상태

| Tier | 내용 | yhash / ypsilenti |
|---|---|:--|
| **T1** | 기능/대수 정확성 (Isabelle) | ✅ α primitivity·cycle·encode 단사·XOR 분해·도메인태그·mask 단사 — kernel-checked, `sorry` 없음 |
| **T2** | 메모리안전 / constant-time | △ `forbid(unsafe_code)`·Zeroize ✅ / **CT는 "상속 주장"뿐, CT 도구 측정 0** |
| **T3** | 모드 보안 = 순열을 ideal로 가정한 **환원 증명** | ❌ `yhash-verify/Y5_CRReduction.thy` 100% `sorry` (선언만) |
| **T4** | 구체 순열의 계산적 보안 = **공개 암호분석** | ❌ word-level MILP만 (internal v0.1) |

> **대수 증명(T1)은 모드/순열 보안(T3·T4)을 함의하지 않는다.** 같은 계열의 YSC2가
> *10개 취약점·6개 치명*으로 파훼된 전례가 `REPORT.md`에 실재한다 — 대수가 못 잡는
> 결함이 이 계열에서 *실제로* 발생했다. T4는 원리적으로 형식검증 대상이 아니며
> (안전한 PRF ⟹ OWF ⟹ P≠NP) 오직 *공개 암호분석의 누적*으로만 확보된다.

### frozen/production 채택 전제조건 (우선순위 순)

| # | 항목 | 현재 | 수용 기준 |
|---|------|------|-----------|
| **R4** | **단일 권위 파라미터 동결 + 교차구현 KAT** | ❌ SPEC↔코드↔Isabelle **drift 존재**: yhash 상태크기(SPEC 512-bit vs 코드 1024-bit), ypsilenti GF 다항식(SPEC `0x1B` vs 코드 `0x400007`) | SPEC=코드=Isabelle 일치, 버전 태그, bit-exact KAT 공개 |
| **R2** | **bit-level 차분/선형 트레일 경계** | ❌ word-level 보수 하한만 (`TODO.md` B1) | 채택 라운드 수에서 best trail ≤ 보안목표(CR 2⁻²⁵⁶ / PRF 2⁻¹²⁸) 정량 |
| **R1** | **keyed PRF/deck 보안 환원 기계검증** | ❌ Y5 전부 `sorry` | `sorry`-free + 명시적 bound + single→multi-key |
| **R3** | **constant-time 검증 (키 경로)** | △ 주장만 | dudect/ctgrind 또는 검증형 CT + CI 회귀 |
| **R5** | **외부 공개 암호분석** *(최종 관문)* | ❌ 미수행 | 독립 분석가 공개 리뷰 또는 FSE/ToSC 동료심사 |

→ R1–R5는 frozen on-disk 채택을 검토한 다운스트림 감사에서 도출된 체크리스트로,
충족 시 알고리즘 agility version id로 채택 가능하다.

## 외부 검토 요청 항목 (YSC 본체)

1. **YSC2의 V1~V10 검증** — REPORT.md의 결함이 모두 정확한지.
2. **YSC4/YSC5의 형식 검증 범위** — Isabelle Q1/Q2/Q3가 실제로 사양의 핵심 가정을 검증하는지.
3. **bit-level MILP** — `milp/analysis.md`의 word-level 결과를 bit-level로 확장한 trail 확률 정량 (= R2).
4. **Multi-key 환원의 formal proof** — `NOTE-multikey-security.md`의 CryptHOL skeleton 완성 (= R1).
5. **FHE 백엔드 실측** — `NOTE-fhe-cost.md`의 해석적 추정과 실측 비교.

문의: `REPORT.md` 또는 본 README에 명시된 issue tracker.
