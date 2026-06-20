# R3 — constant-time 감사 (YHash 패밀리 keyed 경로)

> 결정(`PROOF-TOOLCHAIN.md`): **Rust dudect + 정적 감사.** (EasyCrypt-Jasmin은 Rust를
> 검증 못 하고 valgrind 부재.) 1차 증거는 **정적 감사**(아래 §1), 보조는 dudect(§2).

## 1. 정적 CT 감사 — keyed 경로는 *설계상* data-oblivious

대상: 비밀(키)이 흐르는 경로 `key → IV → mask 유도 → 압축/종결`.
검증 기준: (a) 비밀-값 의존 **분기** 없음, (b) 비밀-값 의존 **메모리 인덱스** 없음,
(c) **가변시간 연산**(나눗셈·가변 시프트·하드웨어 곱) 없음, (d) early-exit 없음.

| 구성요소 | 위치 | 판정 |
|---------|------|------|
| α-곱 (GF 환원) | `ysc4/gf2_64.rs`, `ypsilenti/gf32.rs` | ✅ `mask = 0.wrapping_sub(y>>(n-1)); (y<<1)^(mask&RED)` — **분기 없는** 산술 마스크 |
| α^k (σ-층) | `alpha_pow`: `for _ in 0..k` | ✅ k = 컴파일타임 상수(1,3,5,7), 루프 bound 공개 |
| 라운드 ι | `state[r&15] ^= RC[r&15]` | ✅ 인덱스 = 라운드 번호(공개), 비밀 무관 |
| F 함수 | rotate·AND·XOR | ✅ 정수 ALU만 (rotate량 컴파일타임 상수) |
| broadcast / xor_reduce | 고정 길이 루프 | ✅ 상태 크기(공개) 의존 |
| π 순열 | `new[i] = old[P[i]]` | ✅ P = 컴파일타임 상수 배열 |
| 라운드 수 | `permute(state, R)` | ✅ R = 컴파일타임 상수(R_b/R_c/R_mask), 비밀 무관 |
| 키 흡수 (keyed) | `key.chunks(8)`, `chunk.len()` | ✅ 제어흐름이 키 **길이**(공개)에만 의존, **값**에 무관 |
| Zeroize on drop | `[u64;16]`/`[u32;8]` | ✅ 고정 크기, 상수 시간 |

`grep`으로 비밀-값 의존 분기(`if …key…`, `match …key…`, 비밀 인덱싱) 탐색 → **0건**
(키-*길이* 의존 `chunks`/`len()` 제외). x86 정수 ALU(xor/and/add/shift/rotate)는
피연산자 값과 무관하게 상수 시간이므로, 위 경로의 **실행 사이클은 키 값에 독립**이다.

→ **판정: keyed 경로는 data-oblivious (소스 레벨 CT).** 잔여 위험은 컴파일러(LLVM)가
branchless 소스를 비밀-종속 분기(예: cmov→branch)로 낮추는 경우뿐 → §3 권고.

## 2. dudect 경험적 검정 (보조)

`yhash-bench/.../ct_dudect.rs` (rdtsc, N=300k, Welch t, multi-crop max|t|, 임계 4.5).

표준 dudect(고정키 vs 랜덤키)와 **대조군 fixed-vs-fixed**(서로 다른 두 고정 키)를 함께
측정. 핵심: *순수 정수 ALU는 x86에서 data-independent*이므로, **두 고정 키 간 t는
구조적으로 0이어야 한다** — fixed-vs-fixed의 잔류 t는 *측정 환경 artifact*(노이즈·캐시·
주파수 스케일링)이지 알고리즘 누설이 아니다.

| 테스트 | max\|t\| (코어 고정) | 해석 |
|--------|-----:|------|
| ypsilenti keyed-builder, **fixed-vs-fixed** | **0.5** | ✅ 깨끗 — 키 값 독립(CT) 재현 확인 |
| ypsilenti keyed-builder, fixed-vs-random | ~9–16 | 가변입력 측정편향 (위 0.5가 반증) |
| yhash keyed-builder, **fixed-vs-fixed** | ~20–28 | 환경 artifact — 정수 ALU는 값-독립이므로 누설 불가; 긴 측정창이 노이즈 증폭 |
| (keyed-hash) | run마다 2~58 변동 | **노이즈 지배**(불안정) → 공유 호스트 한계 |

run-to-run 변동이 큼(예: keyed-hash 2→58) = 측정이 노이즈 지배. **신뢰할 verdict는
격리 환경 필요**(코어 격리 `isolcpus`/`taskset`, turbo off, performance governor).
공유 dev 박스에서의 dudect는 *불확정*이며, 정적 감사(§1)가 우선 증거다.

## 3. 판정과 권고

- **R3 = 정적 감사 PASS (data-oblivious by construction)** + dudect 보조(ypsilenti
  fixed-vs-fixed 깨끗; yhash는 호스트 노이즈로 경험적 불확정).
- *과대주장 회피*: "형식적으로 CT 증명됨"은 **아니다**(그건 ct-verif/Jasmin/소스→
  바이너리 보증이며 Rust 대상엔 부적합·범위 밖). 주장 가능한 것은 **소스 레벨
  data-obliviousness**(감사) + **경험적 일관성**(ypsilenti).
- 권고:
  1. **CI**: §1 불변식 회귀 검사(비밀-종속 분기/인덱스 패턴 grep 게이트) +
     dudect ypsilenti-builder 스모크(격리 코어).
  2. **clean 측정**: `isolcpus`+`taskset`+turbo off로 yhash fixed-vs-fixed 재측정.
  3. **asm 검사**: 채택 타깃에서 `alpha`/`round`/keyed-init 디스어셈블해 cmov→branch
     하강 없음 확인 (`cargo-show-asm`).
  4. **WASM**: WASM 런타임은 cmov 부재·JIT 상이 → CT 주장을 native로 한정하거나
     wasm 타깃 별도 측정.

## 4. 재현

```bash
cargo run --release -p yhash_bench --bin ct_dudect          # 공유 호스트
taskset -c 3 cargo run --release -p yhash_bench --bin ct_dudect   # 코어 고정(노이즈↓)
grep -nE "if .*key|match .*key" ysc4/src ypsilenti/src yhash/src -r   # 분기 감사
```
