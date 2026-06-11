# YSC2 / AuxCrypt 스트림 암호 Cryptanalysis 보고서

- 대상 저장소: <https://github.com/newsniper-org/ysc2>
- 분석일: 2026-06-06
- 분석 범위: `ysc2` 크레이트의 스트림 암호 모드 및 `auxcrypt` 보조 스트림 암호
- 첨부 PoC: `/home/ybi/cryptanalysis/attack/` (모든 공격은 release 빌드에서 검증 완료)

---

## 0. 요약 (TL;DR)

각 결함은 **[사양]** (specification-level — 알고리즘 정의 자체의 결함, 어떤 정확한 구현에서도 발생) 또는 **[구현]** (implementation-level — 사양은 무사하나 본 저장소의 Rust 코드에서 발생) 으로 분류한다.

| 번호 | 분류 | 결함 | 영향 | 검증 PoC |
|------|------|------|------|----------|
| **V1** | **사양** | YSC2 스트림 암호가 **순열 출력 1024비트 전체**를 키스트림으로 노출 | 128바이트 KPA → **내부 상태 즉시 복구** | `recover_ysc2_state` |
| **V2** | **사양** | 순열이 가역적 + 초기화도 같은 순열 → **키 복구** | 128바이트 KPA → **512/1024비트 키 완전 복구** | `recover_ysc2_key` |
| **V3** | **사양** | AuxCrypt의 "비선형" 함수 `f(x) = ¬x ⊕ rot(x,19) ⊕ rot(x,41)`이 **affine** | 라운드 수(14·20)와 무관, **전체 순열이 affine** | `auxcrypt_linear` |
| **V4** | **사양** | V1·V3 결합 → AuxCrypt도 동일한 KPA 키 복구 | 128바이트 → **AuxCrypt 키 완전 복구** | `recover_auxcrypt_key` |
| V5 | **사양** | `g(x) = x ⊕ ((x≪13) & (x≪37))`의 차분 확산이 약함 | 1비트 차분 → 평균 2비트만 변화 | `diff_analysis` |
| V6 | **사양** | 라운드 상수 RC = `[0,1,…,15]`로 단순 | 비선형 라운드라면 큰 문제 없으나, AuxCrypt에선 결합되어 affine 상수 항으로 흡수 | 분석 |
| V7 | **구현** | AuxCrypt SIMD 백엔드가 **비트 회전 대신 레인 회전**(`rotate_elements_left`) 사용 | soft ≠ simd, 상호운용 실패. SIMD 변종은 한층 약한 함수. | 코드 검토 |
| V8 | **구현** | `Ysc2StreamCore`·`AuxCryptCore`에 `Zeroize`/`ZeroizeOnDrop` 미적용 | 키·내부 상태가 메모리에 잔존 (cold-boot, 메모리 덤프 위험) | 코드 검토 |
| V9 | **구현** | `ysc2/src/lib.rs` 최상단에 `#![cfg(feature = "ysc2_simd")]` | 기본 기능에서 **크레이트가 빈 상태로 컴파일**됨 (사용자가 발견 못 한 빌드 결함) | 코드 검토 |
| V10 | **사양 + 구현** | AEAD 흐름에서 도메인 분리자가 명세되지 않고(`AEAD_NONCE_DOMAIN` 등 선언은 있으나 사용 안 됨) `0x01` 단일비트 패딩만 사용 | 일부 경계 조건에서 nonce/AD 경계 모호 | 분석 |

### 분류 요약
- **사양 결함 (P0/P1 핵심)**: V1, V2, V3, V4, V5, V6. **저장소를 그대로 재구현해도** 동일하게 재현됨. 알고리즘 자체를 수정해야 함.
- **구현 결함**: V7, V8, V9. 사양은 유지한 채 본 저장소의 Rust 코드만 패치하면 해결.
- **혼합**: V10 — 사양에 도메인 분리 단계가 빠져 있고, 구현은 선언된 라벨을 사용하지 않음.

#### PoC 위치와 분류의 일관성
`/home/ybi/cryptanalysis/attack/src/ysc2_ref.rs`는 *저장소의 라이브러리에 의존하지 않고* `backends/soft.rs`의 사양을 직접 재구현했다. V1~V6의 모든 공격이 이 재구현 위에서 성공한다는 사실이 **사양 결함이라는 분류의 근거**다 (구현 버그가 아닌 사양 그 자체의 문제).

**결론**: 이 스위트는 임의의 라운드 수에서도 **128바이트의 알려진 평문(KPA)** 만으로 키가 풀린다. 라이브러리는 *암호학적으로* 부적합하며 **즉시 사용 중단** 권고. 양자 내성 128/256비트 주장은 무효.

---

## 1. 대상 알고리즘 개요

### 1.1 공통 상태
- **상태**: 16 × `u64` = 1024비트.
- **출력 블록**: 1024비트 (128바이트).
- **카운터**: 단일 `u64`.

### 1.2 YSC2 순열 (1라운드)
```text
1) state[0] ^= RC[r]                                   // RC = [0,1,…,15]
2) Lai-Massey-유사 비선형 계층:
     temp[i]      = g(state[i])           ;  i = 0..7
     state[i+8] ^= temp[i]                ;  R' = R ⊕ g(L)
     state[i]   ^= state[i+8]             ;  L' = L ⊕ R'  = L ⊕ R ⊕ g(L)
3) 워드 순열: new_state[i] = state[P[i]] ;  P = [0,5,10,15,4,9,14,3,8,13,2,7,12,1,6,11]
   여기서 g(x) = x ⊕ ((x ≪ 13) & (x ≪ 37))
```
- 라운드 수: 두 변종 모두 12.

### 1.3 AuxCrypt 순열 (1라운드)
```text
1) state[0] ^= RC[r]                                   // RC = [0,1,…,19]
2) 4차원 Lai-Massey: dim1/2/3/4 순서로 lai_massey_round(a, b) 호출
     diff = f(state[a] ⊕ state[b])
     state[a] ^= diff ; state[b] ^= diff
3) 동일한 워드 순열 P
   여기서 f(x) = ¬x ⊕ (x ≪ 19) ⊕ (x ≪ 41)
```
- 라운드 수: 512비트=14, 1024비트=20.

### 1.4 키스트림 생성 (양쪽 동일 패턴)
```rust
counter += 1
working = state
working[0] ^= counter
permutation(working)
output[16 워드 전체] = working
```

### 1.5 초기화
- `state[0..key/8] = key 워드들`, `state[8..16] = nonce 워드들` (1024비트 키는 8..16에 key 후반부를 nonce와 XOR).
- 그 다음 정방향 순열 한 번 적용 → 비밀 `state` 확정.

---

## 2. 결정적 결함 (V1, V2): YSC2 키 복구 — *분류: 사양 단계*

### 2.1 핵심 관찰
`gen_ks_block`이 1024비트 순열의 **출력 16개 워드 전부**를 키스트림 블록으로 사출한다. Salsa20/ChaCha20처럼 “원래 상태 ⊕ 순열(상태)” 식의 feed-forward가 **없다**. 즉,

```
keystream_block_n  =  permutation(state ⊕ (n at word 0))
```

### 2.2 순열의 가역성
세 계층 모두 가역:
- AddRoundConstant: XOR이므로 자기 자신이 역.
- Lai-Massey-유사: 출력 (L', R') = (L ⊕ R ⊕ g(L), R ⊕ g(L)) → **L = L' ⊕ R'**, **R = R' ⊕ g(L)**. 비선형 함수 g를 풀 필요가 **전혀 없다** (L' ⊕ R' 자체가 L).
- 워드 순열: 단순 치환의 역.

따라서 전체 12라운드 순열에 대해 효율적 역함수 `P⁻¹`이 존재.

### 2.3 공격 절차
**128바이트의 알려진 평문**(KPA)만으로:
1. `S' = P(state ⊕ n@[0])` (출력 그대로 16개 u64)
2. `working = P⁻¹(S')`
3. `state[0] = working[0] ⊕ n`, `state[1..16] = working[1..16]` ← **상태 완전 복구**
4. (선택) `loaded = P⁻¹(state)` → `state[0..8]` = key 워드, `state[8..16]` = nonce 워드(또는 nonce⊕key_back). 논스는 공격자에게 공개값이므로 **키 그대로 복구**.

비용: 순열 역연산 1~2회 = **O(12·16) u64 연산** ≈ 수 μs.

### 2.4 PoC 실행 결과
```
=== 공격 1: 1블록의 키스트림으로부터 YSC2 내부 상태 복구 ===
[OK] 1024비트 비밀 상태 완전 복구 — 128바이트 KPA로 충분
[OK] 임의의 미래/과거 블록 예측 가능 (블록 2 일치 확인)

=== 공격 2-a: YSC2-512 키 복구 (KPA, 128바이트) ===
  원본 키 (앞 16바이트): c3f6a95c17cafdb06b1ed184bf7225d8
  복구 키 (앞 16바이트): c3f6a95c17cafdb06b1ed184bf7225d8

=== 공격 2-b: YSC2-1024 키 복구 (KPA, 128바이트) ===
  원본 키 (앞 16바이트): f0b9622bd49d460fb8612ad39c450eb7
  복구 키 (앞 16바이트): f0b9622bd49d460fb8612ad39c450eb7
```

### 2.5 시사점
- **양자 내성 128/256비트** (README 주장) 무효. 고전 컴퓨터에서 마이크로초 안에 풀림.
- ROUNDS 값을 무한히 키워도 무용지물 — 순열이 가역인 한 키스트림 = 비밀 상태.
- 시드/카운터 변경, IV 재사용 회피 같은 운용 권고로도 막을 수 없음 (한 번의 정상 통신으로 풀림).

---

## 3. AuxCrypt의 선형성 결함 (V3, V4) — *분류: 사양 단계*

### 3.1 핵심 관찰: `f`는 affine
```
f(x) = ¬x ⊕ rot(x, 19) ⊕ rot(x, 41)
     = (x ⊕ 0xFF…FF) ⊕ rot(x, 19) ⊕ rot(x, 41)
     = (I ⊕ R₁₉ ⊕ R₄₁) · x  ⊕  (0xFF…FF)
```
즉 GF(2) 위에서 **rank-3 선형 변환 + 상수**. **비선형 게이트가 단 한 개도 없다**.

### 3.2 Lai-Massey 라운드의 affinity
`a' = a ⊕ f(a ⊕ b)`, `b' = b ⊕ f(a ⊕ b)` 는 affine. 워드 순열·RC XOR·각 라운드 합성도 affine. 따라서:

```
permutation_AuxCrypt(x)  =  M · x  ⊕  c       (M ∈ GF(2)^{1024×1024})
```

PoC `auxcrypt_linear`로 다음을 실험 검증함:
- `P(x) ⊕ P(y) ⊕ P(x⊕y) = P(0)` (affinity 정의)에 대해 16개의 (x,y) 쌍·14 라운드·20 라운드 모두 통과.
- 표준 기저 1024개에 대해 `M`의 열을 추출하고 임의 입력에 대해 `M·x ⊕ c`가 정확히 `permutation(x)`와 일치.

### 3.3 키 복구 환원
키스트림 한 블록만으로:
```
ks = M' · (key ∥ nonce) ⊕ c'
```
- 128바이트(=1024비트)의 ks와 공개된 nonce(8 워드)가 주어지면, 미지수는 key(512 또는 1024비트).
- 정사각 또는 과결정 GF(2) 선형계 → 가우스 소거로 즉시 풀이.
- 본 PoC는 더 단순한 방법인 **두 번의 inverse_permutation 적용**으로 같은 결과 획득.

### 3.4 PoC 실행 결과
```
[A] 14 라운드: 16개의 (x,y) 쌍에 대해 affine 성질 통과
    20 라운드: 16개의 (x,y) 쌍에 대해 affine 성질 통과
[B] 20라운드 순열 = M·x ⊕ c. 검증 완료.

=== 공격 4-a: AuxCrypt-512 키 복구 (14 라운드) ===  [OK]
=== 공격 4-b: AuxCrypt-1024 키 복구 (20 라운드) ===  [OK]
```

### 3.5 시사점
- README의 “독자적 구조 + 추가 보안 계층” 주장 — 사실은 **단 한 개의 AND/곱셈도 없는 선형 함수**로 어떤 라운드 수에서도 무력화됨.
- 4D Lai-Massey 구조는 *선형 함수*를 비선형으로 만들지 못함.

---

## 4. 비선형 함수 `g`의 차분 특성 (V5) — *분류: 사양 단계*

`g(x) = x ⊕ ((x≪13) & (x≪37))`은 진정한 비선형이지만 확산이 약하다.

`diff_analysis` PoC 결과:
- 단일 비트 입력 차분 → 출력 평균 해밍 무게 ≈ **2비트**. 1비트가 g 안에서 최대 2개의 AND 게이트에만 영향 (rotate 13, 37의 역방향 영향).
- 워드 내 확산은 가능하나, 16워드 간 확산은 **워드 단위 순열 P**와 Lai-Massey의 단일 “R ⊕ g(L)” 단계에만 의존.

YSC2가 만약 적절한 feed-forward를 도입해 V1, V2를 막더라도, 다음 라운드까지 살아남는 단일 비트 트레일을 추적하는 **차분 공격**의 출발점이 된다. 본 보고서의 결정적 공격이 더 강력하므로 우선 순위는 낮으나 설계 보강 시 함께 다뤄야 함.

---

## 5. 추가 결함 (혼합)

> 5.1은 **사양 단계**, 5.2~5.4는 **구현 단계**, 5.5는 **혼합**.

### 5.1 V6 — 단순 IOTA 라운드 상수 *(사양 단계)*
`RC = [0, 1, …, 15(또는 19)]`. 비선형 라운드가 충실하면 영향이 제한적이나, AuxCrypt에서는 affine 결합에 흡수되어 별도 의미를 부여하지 못함. 회전 대칭/슬라이드 공격을 명시적으로 막기 위한 비대칭 상수가 필요.

### 5.2 V7 — AuxCrypt SIMD ≠ AuxCrypt soft *(구현 단계)*
`auxcrypt/src/backends/simd.rs:39-42`:
```rust
let rot_a = x.rotate_elements_left::<{ ROT_A as usize }>();
let rot_b = x.rotate_elements_left::<{ ROT_B as usize }>();
(!x) ^ rot_a ^ rot_b
```
이는 **레인 회전**(u64 4개의 위치를 회전)이며, soft 백엔드의 **u64 내부 비트 회전**과 본질적으로 다른 연산. 결과:
- `feature = auxcrypt_simd`로 컴파일된 라이브러리는 같은 키/논스에서도 다른 키스트림을 생성. 테스트 `auxcrypt_simd_vs_soft_consistency`가 SIMD 활성화 시 실패하도록 작성돼 있어 사실상 의도된 동작이 아님.
- SIMD 변종은 비트 회전의 GF(2)-rank가 사라지고, 19 mod 4 = 3, 41 mod 4 = 1의 레인 순환 + bitwise NOT/XOR → **모두 affine 상태가 그대로 유지** + 함수 다양성은 더 줄어듦. 보안 면에서 더 나쁨.

### 5.3 V8 — 메모리 안전 미흡 *(구현 단계)*
- `ysc2/src/stream.rs::Ysc2StreamCore`: `Zeroize`/`ZeroizeOnDrop` 미적용. 1024비트 상태(키-등가 비밀)가 `Drop` 후에도 힙/스택에 잔존.
- `auxcrypt/src/stream.rs::AuxCryptCore`: 동일.
- `sponge.rs`, `aead.rs`는 적용되어 있어 대비됨.

### 5.4 V9 — 빌드 시스템 결함 *(구현 단계)*
`ysc2/src/lib.rs:4`와 `auxcrypt/src/lib.rs:9`에 **크레이트 최상단** `#![cfg(feature = "<X>_simd")]`가 있어, 기본 빌드(`cargo build`)에서는 **두 크레이트가 모두 빈 상태**로 컴파일됨. 사용자는 컴파일 에러로 인지하지 못한 채 “정상”이라고 오해할 수 있음. 의도는 `#![cfg_attr(feature = "ysc2_simd", feature(portable_simd))]` 형태였을 것.

### 5.5 V10 — AEAD 패딩의 도메인 모호성 *(사양 + 구현)*
`aead.rs::absorb_padded_data`는 `0x01` 단일 비트 패딩만 사용. nonce·AD·ciphertext 사이의 **명시적 도메인 분리자** 없이 단지 “별도 absorb 호출”로 구분. 일부 경계 조합 (예: 빈 AD + 특정 nonce ≡ 다른 빈 입력)에서 충돌은 어렵지만, 도메인 라벨(`"NONCE"`, `"AD"`, `"CT"`)이 `Ysc2Variant`에 선언만 되어 있고 실제 흡수 흐름에서 사용되지 않음. 형식적 분리는 유지되나 설계 의도 부분이 누락.

---

## 6. 사이드채널 평가 — *주로 구현 단계, 일부 사양 단계*

### 6.1 타이밍·캐시 (구현 레벨)
- **양호**: 회전 상수가 컴파일타임 상수(`ROT_A`, `ROT_B`)이므로 변수 회전 타이밍 누설 없음.
- **양호**: S-Box·테이블 룩업 없음 → 캐시-타이밍 부채널 없음(FHE 친화 설계의 의도된 이점).
- **양호**: 모든 비밀-의존 분기가 부재. 루프 경계는 라운드 수/워드 수 등 공개 상수.
- **양호**: AEAD 태그 비교 `ct_compare`는 fold 기반 상수시간 비교(O(n) but no early exit).

### 6.2 누설 가능한 부채널
*(메모리 잔존·AEAD zero out — 구현 단계 / 카운터 위치 결정 — 사양 단계)*
- **V8 메모리 잔존**: `Ysc2StreamCore` Drop 후 키-등가 상태가 메모리에 남음. 같은 프로세스의 다른 스레드/할당이 슬랩을 회수하면 평문 노출.
- **AEAD 실패 시 평문 노출 가능성**: `decrypt_in_place_detached`에서 태그 검증 실패 시 `buffer.iter_mut().for_each(|b| *b = 0)`로 zero out 하지만, **이미 복호화된 버퍼가 같은 메모리 영역**임. 다음 (1) 컴파일러가 zero를 dead-store로 제거할 수 있음 (휘발성·`zeroize::Zeroize` 사용해야 안전), (2) 인-플레이스 디크립션은 호출자가 받은 `&mut [u8]`을 zeroize하는데 이미 일부 누설된 후일 가능성.
- **카운터 사이클 누설(이론적)**: 카운터를 word 0에만 XOR해 같은 키/논스에서 1, 2, 3… 사이 차이가 매우 작음. V1 결함이 이미 fatal이라 부수적이지만, 만약 V1을 고친 뒤에도 카운터를 단일 워드 LSB에 두면 차분 공격 진입점이 됨.

### 6.3 결합·전력 분석 (이론적) — *사양 단계*
- AND 게이트가 `g(x)` 안에 비트당 1개 → 전력 측정 시 해밍 무게 누설 패턴이 단순함 (소프트웨어 HW 누설 모델에서 PoC 가능). FHE-친화 설계 목적상 작은 비트 곱이 의도이지만, 마스킹 친화성과 부채널 저항은 **별도 설계 항목**이며 본 라이브러리는 마스킹 어댑터를 제공하지 않음.
- 1024비트 와이드 상태는 측정 채널을 *공간적으로* 확산시키나, 단일 비밀 워드 단위 측정은 그대로 적용 가능.

### 6.4 종합
구현 수준 *상수시간 보장*은 비교적 양호하지만, 메모리 위생(V8)·zero out 실효성 검증 부재가 즉각적 문제. 부채널 저항은 *알고리즘 자체의 fatal 결함이 우선 해결되어야 의미가 있음*.

---

## 7. 해결 방안

각 결함에 대해 **구체적·실행 가능한** 패치 방향을 제시한다.

### 7.1 [V1, V2] 스트림 모드 자체 재설계 — **최우선**

다음 중 하나로 교체:

**옵션 A (권장): Salsa/ChaCha 스타일 feed-forward**
```rust
fn gen_ks_block(state, counter) -> [u8; OUT_BYTES] {
    let mut w = state;
    w[0] ^= counter;
    permutation(&mut w);
    // CRITICAL: 출력 = w + state (또는 XOR)
    for i in 0..16 { w[i] = w[i].wrapping_add(state[i]); }
    serialize(w)
}
```
- 순열 가역성에도 불구하고 출력에서 원래 `state` 회수 불가 (입력의 일부가 알려져 있어도 차분 불변량 존재 필요).
- ChaCha20과 동일한 가정 하에 보안 환원이 알려짐.
- 단점: AES/ARX 라이브러리들의 `cipher` 트레잇 호환 외에 별도 추가 작업 없음.

**옵션 B (스펀지 모드)**
- `RATE_BYTES = 64` (현재 sponge.rs와 동일)만 출력하고, 나머지 64바이트는 capacity로서 비밀 유지.
- 출력 = `state[0..8]`의 LE 바이트화 (현 sponge `Reader::read_block`과 동일 패턴).
- 키스트림 효율은 50%로 줄지만, 1024비트 capacity로 양자 내성 주장이 다시 가능해짐.

**옵션 C: 의사난수 추출기 추가**
- 키스트림 = `Truncate_k(M · permutation(state ⊕ counter) ⊕ N · state)` 같은 추출 함수 도입.
- 구현이 더 복잡하므로 옵션 A·B 권장.

추가: **카운터의 위치/확산**. `state[0]`에만 XOR하지 말고, 카운터를 도메인 분리자 + nonce hash와 결합해 다수 워드에 흩뿌릴 것 (예: `working[0] ^= ctr; working[8] ^= ctr.rotate_left(32);`).

### 7.2 [V3, V4] AuxCrypt의 `f` 비선형화

현재 `f(x) = ¬x ⊕ rot(x,19) ⊕ rot(x,41)`는 affine. 두 옵션:

**옵션 A: AND 도입** (FHE 친화 유지)
```rust
fn f(x: u64) -> u64 {
    let a = x.rotate_left(19);
    let b = x.rotate_left(41);
    (!x) ^ a ^ b ^ (a & b)        // ← AND 추가
}
```
- 라운드당 비트당 AND 게이트 1개 추가. FHE 비용 증가 미미.
- 또는 ChaCha의 ARX 패턴(`a += b; d ^= a; d <<<= n`)을 채택. 모듈러 덧셈은 FHE에서 비싸지만 비선형성을 단번에 확보.

**옵션 B: 다중 AND**
```rust
fn f(x: u64) -> u64 {
    let r1 = x.rotate_left(17);
    let r2 = x.rotate_left(29);
    let r3 = x.rotate_left(43);
    x ^ (r1 & r2) ^ (r2 & r3)
}
```
- 비선형 차수 = 2, 차분/선형 특성을 보강하기 위해 회전 상수를 보안 분석으로 선정.

옵션 A 권장 (1개 AND 추가). YSC2 `g`와 같은 패턴을 가져오는 것도 자연스러움 (단, V5 문제까지 함께 고려).

### 7.3 [V5] g(x) 확산 강화

옵션:
- 회전 상수 (13, 37) 외 추가 회전 사용 → `g(x) = x ⊕ ((x≪α) & (x≪β)) ⊕ ((x≪γ) & (x≪δ))` 형태.
- 또는 단일 워드 g 호출 후 **워드 간 추가 믹싱** 단계를 한 줄 도입 (예: MDS 비슷한 GF(2) 행렬을 한 라운드마다 적용).
- 워드 순열 P를 **bit-level rotation을 곁들인 형태**로 교체해 라운드당 워드 간 확산 향상.

차분 트레일을 MILP/CP 도구(Gurobi + GF(2) 모델)로 12라운드에서 최소 활성 워드 ≥ 16, 활성 비트 ≥ 200 정도가 되도록 회전 상수와 P를 함께 선정해야 함.

### 7.4 [V6] 라운드 상수 재설계

- IOTA가 아닌 **비대칭·고엔트로피 상수**(예: π 또는 e의 비트, Salsa의 `expand 32-byte k` 스타일 도메인 라벨)를 사용.
- 슬라이드 공격을 명시적으로 방어하려면 각 라운드에서 서로 다른 워드 인덱스에 XOR 하는 것도 권장.

### 7.5 [V7] SIMD 백엔드 수정

`auxcrypt/src/backends/simd.rs::f_vec`을 ysc2의 패턴으로 교체:
```rust
fn f_vec(x: u64x4) -> u64x4 {
    let rot_a = (x << Simd::splat(ROT_A as u64))
              | (x >> Simd::splat(64 - ROT_A as u64));
    let rot_b = (x << Simd::splat(ROT_B as u64))
              | (x >> Simd::splat(64 - ROT_B as u64));
    (!x) ^ rot_a ^ rot_b
}
```
또한 SIMD ↔ Soft 일관성을 검증하는 단위 테스트가 CI에서 항상 실행되도록 `cargo test --all-features` 매트릭스 구축.

### 7.6 [V8] 메모리 위생

```rust
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc2StreamCore<V: Ysc2Variant> {
    pub(crate) state: [u64; 16],
    pub(crate) counter: u64,
    #[zeroize(skip)]
    pub(crate) _variant: PhantomData<V>,
}
```
- `AuxCryptCore`에도 동일 적용.
- AEAD 디크립트 실패 시 `buffer.zeroize()` 사용 (현재 단순 loop는 컴파일러가 dead-store로 제거할 수 있음).

### 7.7 [V9] 빌드 결함 수정

`ysc2/src/lib.rs`·`auxcrypt/src/lib.rs`의 잘못된 cfg를 다음으로 교체:
```rust
#![cfg_attr(feature = "ysc2_simd", feature(portable_simd))]
// 크레이트 자체를 cfg로 가두지 말 것
```
또한 CI에서 `cargo build` (no features)와 `cargo build --features ysc2x` 두 케이스를 모두 빌드하도록 강제.

### 7.8 [V10] AEAD 도메인 분리

각 `absorb_padded_data` 호출 전 `Ysc2Variant`의 `AEAD_NONCE_DOMAIN` / `AEAD_AD_DOMAIN` / `AEAD_CT_DOMAIN` 문자열을 명시적으로 흡수.
```rust
absorb_padded_data::<V>(&mut state, V::AEAD_NONCE_DOMAIN.as_bytes());
absorb_padded_data::<V>(&mut state, nonce);
absorb_padded_data::<V>(&mut state, V::AEAD_AD_DOMAIN.as_bytes());
absorb_padded_data::<V>(&mut state, associated_data);
// …(CT 블록도 마찬가지)
```
또한 패딩은 SHA-3의 10*1 (시작 0x06, 마지막 0x80) 또는 길이-기반 명시적 표기로 교체해 경계 모호성 제거.

### 7.9 [부채널] 추가 권고

- `gen_ks_block`이 SIMD 벡터를 사용할 때 zeroize는 `Simd` 타입에도 적용되도록 zeroize crate의 `simd` 기능 사용.
- AEAD 디크립션 실패 시 ZERO out을 `core::sync::atomic::compiler_fence(SeqCst)`로 보호, 또는 `subtle`/`zeroize::Zeroizing` 사용.
- 카운터 위치 분산(7.1 끝부분 권고)으로 부채널 단순화 회피.

### 7.10 우선순위 매트릭스 (사양/구현 구분 포함)

| 우선순위 | 분류 | 항목 | 사유 |
|---------|------|------|------|
| **P0**  | 사양 | V1, V2 (스트림 모드 재설계) | 즉시 키 노출. 패치 전 *모든 사용 금지* 권고 |
| **P0**  | 사양 | V3, V4 (AuxCrypt 비선형화) | 즉시 키 노출 |
| **P1**  | 구현 | V7 (SIMD 정합성) | 데이터 일관성 + 보안 모두 영향 |
| **P1**  | 구현 | V9 (빌드 결함) | 사용자에게 잘못된 컴파일 상태를 제공 |
| **P2**  | 사양 | V5 (확산), V6 (라운드 상수) | P0 패치 후 보안 마진 향상 |
| **P2**  | 구현 | V8 (Zeroize) | 메모리 위생 |
| **P2**  | 혼합 | V10 (AEAD 도메인) | 사양에서 라벨을 정의했으나 흐름에 누락 |

#### 사양 vs 구현 패치 분리 방침
- **사양 패치** (V1·V2·V3·V4·V5·V6, 일부 V10): 새로운 알고리즘 사양을 정의하고 (예: YSC2 v2) 외부 학계의 검토 후 반영. 본 v1과 *바이너리 호환이 깨짐*.
- **구현 패치** (V7·V8·V9, 일부 V10): 현 사양을 유지한 채 본 저장소의 Rust 소스를 수정하는 것으로 해결. 기존 사용자 영향 최소.
- 본 라이브러리는 두 패치 묶음을 **동시에 릴리스 (메이저 버전 업)** 해야만 의미가 있다 — 구현만 수정해도 사양 결함이 그대로 남아 키가 풀리기 때문이다.

---

## 8. 재현 가이드

```bash
cd /home/ybi/cryptanalysis/attack
cargo build --release
./target/release/recover_ysc2_state    # 공격 1
./target/release/recover_ysc2_key      # 공격 2 (512/1024)
./target/release/auxcrypt_linear       # 공격 3 (affine 검증)
./target/release/recover_auxcrypt_key  # 공격 4
./target/release/diff_analysis         # g(x) 차분 표본
```
- 모든 PoC는 **라이브러리에 의존하지 않고**, `attack/src/ysc2_ref.rs`의 사양 구현(`backends/soft.rs`의 1:1 이식)에 대해 동작. V9의 빌드 결함과 무관히 사양 자체가 결함임을 보장한다.

---

## 9. 결론

`ysc2` / `auxcrypt`는 “FHE 친화·양자 내성” 설계 의도를 가지나, **사양 단계에서** 스트림 출력에 feed-forward를 결여했고(V1·V2), **사양 단계에서** AuxCrypt 비선형 함수가 affine이며(V3·V4), **사양 단계에서** g(x) 확산이 약하다(V5). 이 세 가지 모두 **128바이트의 KPA**(혹은 정상 통신 한 블록 캡처)로 즉시 키 복구로 이어진다.

구현 단계의 결함(V7·V8·V9)은 보조적이지만, V7은 SIMD 변종을 더 약한 함수로 만들고, V9는 라이브러리를 사실상 빈 상태로 컴파일시키며, V8은 메모리 위생을 해친다.

해결을 위해서는 §7의 P0 항목(사양 단계 — 스트림 출력 구조 변경, AuxCrypt 비선형화)과 P1 항목(구현 단계 — SIMD/빌드)을 **함께** 적용해야 하며, 그 이전에는 *모든 환경에서 사용하지 말 것*을 권고한다. 사양 패치 후에도 라이브러리는 외부 학계의 차분/선형 분석을 거쳐 정식 보안 평가를 받아야 한다.

— *분석자 메모: 라이브러리의 “비선형 함수”라는 명칭에 속지 말 것. AuxCrypt의 `f`는 단순 affine이며, 이는 코드만 봐도 분명하다 (¬·rot·XOR 조합).*

---

## 10. 후속 작업 (Follow-up)

본 cryptanalysis 보고서 이후, 다음의 *재설계 + 형식 검증 + 사양화* 작업이 수행되었다:

### 10.1 YSC3 — ChaCha/NORX 기반 GFN sponge
- §7.1 P0 권고를 *generalized Feistel network (GFN)*로 구현.
- NORX H 함수 + ChaCha column/diagonal 더블 라운드.
- `ysc3/` 디렉토리. 18개 테스트 통과. 처리량 576 MB/s.
- 사양: `ysc3/SPEC.md` (확장), `ysc3/SPEC.typ` (Typst 요약본).

### 10.2 YSC4 — σ-Generalized Lai-Massey
- 사용자가 GFN 외에 *Lai-Massey의 generalization*도 탐색하길 원함.
- 16-branch σ-GLM (Vaudenay 의미의 σ-orthomorphism 적용).
- σ = $"GF"(2^{64})$ 곱 (= multiplication by primitive element $α = x$ in
  $"GF"(2)[x]/(x^{64} + x^4 + x^3 + x + 1)$).
- FHE AND 카운트 1/6 절감 (블록당 2,048 vs YSC3의 12,288).
- `ysc4/` 디렉토리. 24개 테스트 통과.

### 10.3 YSC5 — Farfalle 구조
- `farfalle-gen/META.md`에서 Farfalle 일반화 메타-task 수행 — 6개 직교 설계축 분해.
- 발견: *YSC4의 σ-orthomorphism이 Farfalle의 mask-roll 요구를 동시에 만족* (`NOTE-orthomorphism-roll-coincidence.md`).
- YSC5 = YSC4-p 순열 + Farfalle 구조 + 4-튜플 입력 (Key, Nonce, AD, PT).
- 블록간 *완전 병렬* (sponge의 직렬과 대조), incremental compression 지원.
- RustCrypto convention 채택 (`cipher::StreamCipher`, `aead::AeadInPlace`, `digest::{Update, ExtendableOutput, Mac}`).
- `ysc5/` 디렉토리. 26개 테스트 통과. 19-페이지 Typst 사양서 (`ysc5/SPEC.pdf`).

### 10.4 Isabelle/HOL 형식 검증
- `isabelle-verify/` 디렉토리. Isabelle2025-2 `YSC_Probe` session.
- **Q1**: α는 $"GF"(2^{64})^*$의 primitive element (`Q1_primitive_certificate`).
- **Q2**: 모든 $k ∈ \{1..16\}$에 대해 $"ord"(α^k) > 2^{60}$ (`Q2_all_orders_practical`).
- **Q3**: γ roll의 1-단계 결과가 distinct (`Q3_roll_distinct_for_ones`).
- 모든 정리 `by eval` (code-generation reflection)로 kernel-checked.

### 10.5 MILP 차분 분석
- `milp/` 디렉토리. GLPK 기반 워드-수준 활성 트레일 분석.
- R∈{8,12,16}에서 최소 trail = 2 active words/round (`milp/analysis.md`).
- *워드-수준만으로는 보수적*이며 정식 보안 평가에는 bit-level MILP 필요.

### 10.6 YHash 패밀리 — σ-GLM 순열의 해시 함수 재사용
- YSC4-p / σ-GLM 순열을 *Farfalle-tree 해시*로 재사용:
  - **yhash** (`yhash/`) — 256-bit digest, 1024-bit 상태 (YSC4-p 순열).
  - **ypsilenti** (`ypsilenti/`) — 128-bit digest, 256-bit 상태 (8×u32 σ-GLM 축소판).
- `no_std` + `forbid(unsafe_code)`, `core::hash::BuildHasher` + RustCrypto `digest` 호환.
- 형식 검증: `yhash-verify/`, `ypsilenti-verify/` (Q1'~, Y1'~).

**성능 최적화** (이번 작업):
- **Level B SIMD** — 단일 순열이 아니라 leaf의 독립 블록 8개를 SIMD lane에 싣는
  inter-block batch. 초기 Level A(상태를 한 벡터에)는 가로 reduce + σ-층 lane
  추출로 *회귀*(0.6~0.7×)였고, Level B로 교체해 실이득 전환.
  - leaf 압축: ypsilenti nightly **3.9×** / stable **2.6×**, yhash **2.2×** / **1.8×**.
  - 백엔드 2종: nightly `core::simd`, stable `wide` crate (안정 채널).
- **멀티스레드** — `Spawner` trait(`no_std` 추상화; Serial/StdThread/Rayon) 위에
  leaf 계산 + **트리 빌드를 divide-and-conquer 병렬화**. rayon 스케일 **~8–10×**
  (16 thread). std-thread는 active-thread 캡으로 thread 폭증 회귀 해소.
  - 트리 병렬 빌드는 `TreeBuilder`의 binary-counter 형태를 재귀로 정확히 복제 →
    직렬과 비트단위 동일 (leaf 수 1..=40 전수 검증).
- **종합** (x86_64, 16 thread): ypsilenti scalar 1-thread 200 MB/s →
  SIMD+rayon **~3.2 GB/s (~16×)**. 멀티스레드에서 K12를 ~3.4× 추월.
  단 BLAKE3(단일 ~6.3 GB/s, rayon ~40 GB/s)와는 본질적 격차 — 원인은 ISA가 아니라
  라운드당 연산량(GF α-곱 + 24R 마스크 유도). 상세: `yhash-bench/SIMD_MT_RESULTS.md`,
  `yhash-bench/SECURE_HASH_COMPARISON.md`. SIMD preset 인프라는 `xtask/`+`presets/`,
  WASM 가이드는 `WASM.md`.

### 10.7 외부 검토 요청
- 본 v1.0 cryptanalysis 보고서의 V1~V10 검증.
- YSC3/YSC4/YSC5 사양과 형식 검증의 적정성.
- bit-level MILP, CryptHOL formal multi-key proof, FHE 백엔드 실측.
- 자세한 사항: 저장소 최상위 `README.md`.

본 follow-up은 *v1.0 시점*의 외부 분석을 위한 것이며, 정식 학술 발표·표준화는 별도 단계.
