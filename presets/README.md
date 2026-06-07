# presets — SIMD/target-feature 프리셋

`.cargo/config.toml`에 적용할 RUSTFLAGS 묶음. xtask로 자동 적용:

```bash
cargo run -p xtask -- list
cargo run -p xtask -- suggest        # 호스트 arch 기반 권장
cargo run -p xtask -- preset x86-64-v3
```

수동 적용도 가능: `cp presets/<name>.toml .cargo/config.toml`.

## 사용 흐름

1. `cargo run -p xtask -- suggest` — 호스트에 맞는 preset 추천
2. `cargo run -p xtask -- preset <name>` — 적용 (기존 config.toml 백업)
3. `cargo build --features stable-portable-simd,preset-<name>` (또는 `nightly-portable-simd`)

## Preset 목록

| Preset | arch | target-feature | 대상 |
|--------|------|----------------|------|
| `baseline` | * | (none) | conservative, no SIMD |
| `x86-64-v2` | x86_64 | sse4.2 popcnt | 2008+ (Nehalem) |
| `x86-64-v3` | x86_64 | avx2 fma bmi2 | 2013+ (Haswell) |
| `x86-64-v4` | x86_64 | avx512f avx512bw avx512vl avx512dq | 2017+ (Skylake-X) |
| `aarch64-baseline` | aarch64 | neon | ARMv8.0 |
| `aarch64-v8.2` | aarch64 | v8.2a fp16 | Apple M1, Graviton2 |
| `aarch64-sve` | aarch64 | sve | Graviton3, A64FX |
| `wasm-simd` | wasm32 | simd128 | 현대 브라우저/WASI |
| `rv64gcv` | riscv64 | v | RVV 1.0 |
| `ppc64-power8` | powerpc64 | vsx power8-vector | POWER8+ |
| `ppc64-power9` | powerpc64 | vsx power9-vector | POWER9+ |

## Workload 매핑 (참고용 가이드)

`xtask suggest` 의 출력 외에 use case별 권장 조합:

- **현대 서버 (Linux, x86_64)**: `preset-x86-64-v3` 또는 `v4`. AVX-512 미지원 환경에서 v4 쓰지 말 것.
- **Apple Silicon Mac**: `preset-aarch64-v8.2`.
- **AWS Graviton2**: `preset-aarch64-v8.2`. Graviton3 이상은 `preset-aarch64-sve`.
- **모바일 (iOS/Android ARM64)**: `preset-aarch64-baseline`. 대개 충분.
- **웹/WASM**: `preset-wasm-simd`. 구형 브라우저 fallback이 필요하면 `baseline`.
- **임베디드 (RISC-V/PowerPC/SPARC)**: 칩 사양 확인 후 적절히. 모르면 `baseline`.

## 새 preset 추가 방법

1. `presets/<name>.toml` 생성 (헤더 첫 줄에 `# 짧은 설명`)
2. `[build] rustflags = ["-C", "target-feature=+..."]` 또는 `[target.<cfg>]` 형태
3. 해당 crate의 `Cargo.toml`에 `preset-<name>` Cargo feature 추가
4. `build.rs`에 target-feature 검증 추가
