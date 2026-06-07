# WASM 빌드 가이드 — YHash / ypsilenti / YSC4

YHash 패밀리(`yhash`, `ypsilenti`)와 그 기반 순열(`ysc4`)을 WebAssembly로
빌드하는 방법. 모든 핵심 crate는 `no_std` + `forbid(unsafe_code)`이므로 WASM
타깃과 잘 맞는다.

## 1. 타깃 설치

```bash
rustup target add wasm32-unknown-unknown            # 브라우저/임베드 (no_std)
rustup target add wasm32-wasip2                      # WASI (std 가능; 구 wasip1도 OK)
# nightly SIMD 경로를 쓸 경우 nightly 툴체인에도 타깃 추가:
rustup +nightly target add wasm32-unknown-unknown
```

- `wasm32-unknown-unknown` — 브라우저, JS embed. `std` 없음 → `default`(no_std) 또는
  `alloc` feature까지만.
- `wasm32-wasip2` (또는 `wasm32-wasip1`) — WASI 런타임(wasmtime, wasmer). `std` 사용 가능.

## 2. SIMD (simd128)

WASM SIMD128은 2021년 이후 모든 주요 브라우저/WASI 런타임에서 안정화되었다.
`presets/wasm-simd.toml`이 `-C target-feature=+simd128`을 설정한다.

```bash
# preset 적용 (해당 crate 디렉토리에서)
cd yhash
cargo run --manifest-path ../xtask/Cargo.toml -- preset wasm-simd
# → .cargo/config.toml 생성 (target.'cfg(target_arch="wasm32")'에 +simd128)
```

또는 수동:

```bash
RUSTFLAGS="-C target-feature=+simd128" \
  cargo build --target wasm32-unknown-unknown --features nightly-portable-simd
```

### nightly vs stable

| feature | 툴체인 | SIMD 경로 |
|---------|--------|-----------|
| `nightly-portable-simd` | nightly | `core::simd` Level B (leaf 8-block batch) — 실제 가속 |
| `stable-portable-simd` | stable | 현재 scalar fallback (TODO: `wide` 또는 wasm intrinsics) |
| (없음) | any | scalar |

> SIMD는 *단일 순열*이 아니라 leaf의 *독립 블록 8개*를 lane에 실어 가속한다
> (Level B). 벤치에서 ypsilenti 약 3.9×, yhash 약 2.2× (leaf 압축 기준).

> **주의:** `+simd128` target-feature만 켜고 `nightly-portable-simd`를 켜지 않으면
> 자동 벡터화에만 의존한다. 명시적 SIMD 경로를 쓰려면 nightly + feature가 필요하다.

## 3. 빌드 예시

```bash
# ypsilenti, no_std, SIMD128, nightly (브라우저)
cd ypsilenti
RUSTFLAGS="-C target-feature=+simd128" \
  cargo +nightly build --release \
  --target wasm32-unknown-unknown \
  --no-default-features --features alloc,nightly-portable-simd

# yhash, WASI, stable, scalar
cd yhash
cargo build --release --target wasm32-wasip2 --features std
```

> 위 두 조합 모두 이 저장소에서 빌드 검증됨 (ypsilenti no_std+alloc+simd128 nightly,
> yhash WASI std). `zeroize`가 유일한 외부 의존성이며 wasm 호환된다.

## 4. 멀티쓰레딩 (Spawner)

병렬 해시(`parallel::hash_parallel`)는 `Spawner`로 추상화된다.

- **기본 (`SerialSpawner`)** — 항상 동작. WASM 단일 쓰레드 환경의 기본 선택.
- **`std-thread` / `rayon`** — WASM에서는 *기본적으로 동작하지 않는다*. 브라우저에서
  쓰레드를 쓰려면 `wasm32-unknown-unknown` + atomics + bulk-memory + Web Worker
  기반 쓰레드 풀(예: `wasm-bindgen-rayon`) 설정이 별도로 필요하다.

즉 **브라우저 기본 경로에서는 `SerialSpawner`만 활성화하라.** SIMD(Level A)는
단일 쓰레드에서도 효과가 있으므로, WASM에서는 *SIMD 우선, 멀티쓰레딩은 선택*.

```rust
use yhash::{YHashBuilder, parallel::hash_parallel, spawner::SerialSpawner};

let builder = YHashBuilder::unkeyed();
let digest = hash_parallel(&builder, data, &SerialSpawner); // 단일 쓰레드 OK
```

## 5. 테스트 (wasmtime)

```bash
cargo install wasmtime-cli   # 또는 시스템 패키지
# WASI 타깃 테스트는 runner 지정으로 직접 실행 가능
CARGO_TARGET_WASM32_WASIP2_RUNNER=wasmtime \
  cargo test --target wasm32-wasip2 --features std
```

브라우저 검증은 `wasm-pack test --headless --firefox` 등을 사용.

## 6. 크기 최적화 (선택)

```toml
# .cargo/config.toml 또는 Cargo.toml [profile.release]
[profile.release]
opt-level = "z"   # 코드 크기 우선 (또는 "s")
lto = true
codegen-units = 1
panic = "abort"
```

`no_std` + `alloc`만 쓰면 의존성이 작아 WASM 바이너리가 수십 KB 수준으로 떨어진다.
`std-thread`/`rayon`은 WASM에서 코드 크기를 키우므로 명시적으로 켜지 않는 한 제외된다.
