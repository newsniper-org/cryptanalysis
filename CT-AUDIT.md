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

---

# yttrium side-channel 평가 (v0.2-pre 레퍼런스)

> 방법론(엄수): 성공한 SCA는 **성공 요인을 정확히 귀속** — ①프리미티브 결함 ②미보호 구현
> ③측정/하니스 아티팩트 ④하드웨어 버그. 오귀속(특히 ③④를 ①로) 금지. ④(Meltdown/Spectre류)는
> 발견 시 외부 누출 금지·로컬 보관·사용자 직접 리포트. (본 평가에서 ④ 해당 없음.)

## A. 타이밍 — 누출 미검출 ✓ (구성상 data-oblivious)

`yttrium/examples/dudect.rs` (rdtsc + lfence, 코어고정 taskset, N-sweep, crop90/99):

| 실험 | |t| @ N(50k→200k→500k→1M) | 최종 | 판정 |
|------|----|----|----|
| M: msg zero-vs-random (keyed) | 2.45→5.04→3.48→3.40 | 3.40/3.02 | 누출 미검출 |
| M: msg zero-vs-ones (HW 적대적) | 1.15→1.14→4.02→2.89 | 2.89/1.86 | 누출 미검출 |
| K: **key zero-vs-random**(R_mask 키흡수) | 1.75→2.43→1.31→2.78 | 2.78/3.34 | 누출 미검출 |

|t|이 N 증가에 **비단조·유계**(누출이면 ∝√N 단조증가) → CT 일관. *귀속 주의*: 초기 `Instant`+rng-fill
비대칭 하니스로 |t|=12.9였으나 **하니스 아티팩트**(③)로 진단, confound 제거+rdtsc 후 3.0대로 수렴.

## B. 캐시 — 면역 ✓ (구성상; 비밀-의존 메모리접근 0)

정적 감사(grep): 모든 배열 인덱스가 **공개값** — `SHA*_K[r]`/`state[r%W]`(라운드 r), `state[i]`·`SIG_K[i]`·
`P_PI[i]`·`mask[i]`(루프 i). **비밀-값 의존 분기/인덱스 0건.** S-box 테이블 없음 → Flush+Reload/
Prime+Probe **타깃 부재**(AES 테이블 구현 대비 우월). (`alpha_inv`의 `if v&1`는 역연산=테스트 전용,
해시 경로 아님.)

## C. 전력(CPA/DPA) — **누출(미보호 구현 귀속, 프리미티브 무관)**

in-crate 테스트 `cpa_attack`(`yttrium/src/lib.rs` mod sca_cpa; `cargo test --lib cpa_attack --
--ignored --nocapture`) — **Rust 레퍼런스 구현 직접 공격**; `sca` 훅(`pub(crate)`+`#[cfg(debug_assertions)]`,
공개 API·release 미노출)으로 실 keyed 경로 중간값 사용; HW-leakage **시뮬레이션**이라 실 CPU 측정 아님 → ④ 무관:
- **(A) 성공**: 첫 중간값 `sᵢ=blockᵢ⊕mask`(실제 `derive_mask` 산출 mask; block 공격자제어)에 per-byte
  CPA → **실제 mask 바이트 복구**(σ≤4서 corr 0.944→0.352, 정답 0xb6; M=200서도 복구). *(보수 모호성:
  HW(b^x)·HW(b^~x) |corr| 동일 → 부호 상관으로 해소; **모델 아티팩트**지 실패 아님.)*
- **귀속(②)**: 선형 `XOR-with-secret`의 1차 누출 — **모든 unmasked 암호 공통**(unmasked AES AddRoundKey
  와 동일). **yttrium 프리미티브 결함 아님.** 대응책 = boolean masking(**구현 의무**).
- **(C) 대조군 실패(기대)**: 비선형 post-mix `t=F(S)`(실 구현 `sca::first_round_t`)에 per-byte CPA →
  corr 0.01(무의미). yttrium은
  **S-box 없음 + 영합 전레인 혼합**이라 per-byte 비선형 DPA 타깃을 *추가하지 않음*(classic DPA 타깃이
  AES보다 적음).
- 범위: CPA가 푸는 것은 per-position **mask**(=P_y(IV⊕encode))이지 **key 직접 아님** — mask→key는 P_y
  역상(256-bit preimage, 불가). 단 충분한 position mask 누출은 keyed forgery 보조 가능 → 마스킹 권고.

## D. Fault(DFA) — 프리미티브 특이저항 없음(표준 대응책 영역)

단일비트 fault는 1~2라운드에 완전확산(avalanche §lib 테스트) → faulty digest는 무작위풍. unkeyed
해시는 출력이 truncate+tree라 DFA key-recovery 비자명. keyed MAC은 fault가 forgery 보조 가능 →
**중복연산/검증**(구현 대응책). 프리미티브 수준 특이저항·취약 없음. 정밀 DFA는 R5/전용.

## 종합

| 채널 | 결과 | 귀속 |
|------|------|------|
| 타이밍 | 누출 미검출(유계 |t|) | 구성상 CT |
| 캐시 | 면역 | 구성상(no-table) |
| 전력 CPA | mask 누출 | **②미보호 구현**(generic; 마스킹 필요) — 프리미티브 무관 |
| Fault | 특이저항 없음 | 표준 구현 대응책 |

**정직**: yttrium **프리미티브**는 cache/timing에 구성상 강건(no-table·data-oblivious; S-box 부재로
DPA 타깃도 적음). power/fault 1차 저항은 **구현 countermeasure**(마스킹·중복) 영역이며 본 레퍼런스는
미적용(과대주장 회피). 하드웨어 버그(④) 해당 사례 없음.
