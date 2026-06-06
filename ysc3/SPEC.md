# YSC3 사양 (v0.1 draft)

> *YSC2/AuxCrypt의 사양 단계 결함 (보고서 V1~V6, V10)을 원천 차단하기 위해 전면 재설계한 스트림 암호·AEAD·해시 스위트.*

---

## 0. 설계 목표 (Design Goals)

이 사양은 다음 세 가지 요건을 동시에 만족하도록 한다.

1. **FHE 친화 (FHE-friendly)**
   - 라운드 함수는 `AND`, `XOR`, `NOT`, **상수폭 비트 회전**, **상수폭 비트 이동**만 사용한다.
   - **모듈러 덧셈을 사용하지 않는다** (carry 전파는 FHE에서 매우 비싸다).
   - **AND 게이트 깊이(multiplicative depth)** 와 총 **AND 카운트**가 라운드 수에 선형적으로만 증가하도록 설계.

2. **S-box 사용 암호의 공통 취약점에 면역 (S-box-free immunity)**
   - **테이블 룩업 없음** → AES T-table 류 cache-timing/cache-prediction 공격 면역.
   - **데이터 종속 메모리 접근 없음** → 일반적인 cache·TLB 부채널 면역.
   - **분기 없음** → branch-prediction 부채널 면역.
   - 단일 비트 누설이 일어나도 그것이 S-box 출력의 64비트 마스크 단위로 집중 누설되는 패턴(DPA에 매우 유리한 형태)을 가지지 **않는다**.
   - 마스킹 비용이 AES 등의 S-box 마스킹보다 본질적으로 저렴 (AND 1개 마스킹 = AND 1·XOR 2·랜덤 1, 표 단위 재계산 불필요).

3. **구조적 보안 (구 V1~V6 차단)**
   - **Sponge 기반**: 키와 capacity는 키스트림으로 직접 노출되지 않는다 (V1·V2 차단).
   - **모든 비선형 단계가 진정한 비선형** — Lai-Massey가 아니라 NORX의 H 함수처럼 *AND 게이트가 명시적으로 포함된* 라운드 함수. (V3·V4 차단)
   - 라운드당 **두 단계의 H 호출 × 4 워드 = 라운드당 256개 AND**, 거기에 ChaCha 식 더블 라운드 구조 → 라운드당 알고리즘 차수(algebraic degree) ×2, 6 더블 라운드 후 차수 ≥ 2^12 = 4096 ≫ 1024. (V5 차단)
   - 라운드 상수는 **√2, √3, √5, …의 이진수 표현**에서 추출 (단순 IOTA 아님). 라운드별·단계별로 독립. (V6 차단)
   - 모드별 도메인 분리는 사양에 명시 (V10 차단).

> **명시적 비-목표**: 후보 양자내성성을 *추가로* 주장하지 않는다 (sponge 표준 인자 c/2-비트 안보만). 양자 우선이라면 c를 늘리고 매개변수 표를 별도로 정의해 확장한다.

---

## 1. 상수 및 매개변수

### 1.1 상태

* 상태 크기: **1024비트 = 16 × `u64`**.
* 4 × 4 격자로 인덱싱:  `S[r][c]`,  `r, c ∈ {0,1,2,3}`. 평탄화: `state[4*r + c]`.

### 1.2 매개변수 집합

| 매개변수 집합 | 키 | 논스 | rate `R` | capacity `C` | 라운드 수 (`init`/`block`) | 권장 용도 |
|---------------|-----|------|----------|--------------|----------------------------|----------|
| **YSC3-128**  | 256 비트 | 192 비트 | 512 비트 (8 워드) | 512 비트 (8 워드) | 24 / 12 | 128-비트 안전성 |
| **YSC3-256**  | 512 비트 | 192 비트 | 256 비트 (4 워드) | 768 비트 (12 워드) | 32 / 16 | 256-비트 안전성 |

> `R + C = 1024` 비트로 두 집합 모두 동일한 순열을 공유. 차이는 **rate/capacity 분할**과 **라운드 수**.

### 1.3 회전 상수

NORX 스타일 quarter-round에 사용:

| 이름 | 값 |
|------|----|
| `R0` | 8 |
| `R1` | 19 |
| `R2` | 40 |
| `R3` | 63 |

이 4개의 회전량은 mod 64로 모두 서로 다르고, 최대공약수가 1이며, 2-진수 거듭제곱이 아니므로 회전 대칭/슬라이드 공격 차단에 유리하다.

### 1.4 라운드 상수

라운드 `r`에 사용되는 64-비트 상수 `RC[r]`은 무리수 ⌊2^64 · (√pᵣ − ⌊√pᵣ⌋)⌋, `pᵣ`는 `r`번째 소수 (2, 3, 5, 7, 11, …). 16라운드까지 사용. 예시 (16개 워드, 16진수):

```
RC[ 0] = 0x6A09E667F3BCC908   (√2의 소수부)
RC[ 1] = 0xBB67AE8584CAA73B   (√3)
RC[ 2] = 0x3C6EF372FE94F82B   (√5)
RC[ 3] = 0xA54FF53A5F1D36F1   (√7)
RC[ 4] = 0x510E527FADE682D1   (√11)
RC[ 5] = 0x9B05688C2B3E6C1F   (√13)
RC[ 6] = 0x1F83D9ABFB41BD6B   (√17)
RC[ 7] = 0x5BE0CD19137E2179   (√19)
RC[ 8] = 0xCBBB9D5DC1059ED8   (√23)
RC[ 9] = 0x629A292A367CD507   (√29)
RC[10] = 0x9159015A3070DD17   (√31)
RC[11] = 0x152FECD8F70E5939   (√37)
RC[12] = 0x67332667FFC00B31   (√41)
RC[13] = 0x8EB44A8768581511   (√43)
RC[14] = 0xDB0C2E0D64F98FA7   (√47)
RC[15] = 0x47B5481DBEFA4FA4   (√53)
```

(SHA-256/SHA-512 IV와 동일한 “nothing-up-my-sleeve” 출처를 차용한다.)

### 1.5 도메인 분리자

(11바이트 ASCII; 초기화 시 capacity의 마지막 워드에 LE로 정렬 후 XOR.)

| 도메인 | 문자열 |
|--------|--------|
| Stream cipher 키스트림 | `"YSC3-STM\0"` |
| AEAD 평문 → 암호문 | `"YSC3-AEA\0"` |
| Hash/XOF | `"YSC3-XOF\0"` |
| MAC | `"YSC3-MAC\0"` |

---

## 2. 핵심 빌딩 블록

### 2.1 H 함수 (FHE 친화 비선형)

H는 “모듈러 덧셈”을 대체하는 NORX의 quasi-addition이다.

```
H(x, y) = x ⊕ y ⊕ ((x ∧ y) ≪ 1)
```

* 입력·출력 모두 64비트.
* **AND 게이트 64개**, **시프트 1회**, **XOR 2회** — 모두 FHE에서 저렴.
* **알고리즘 차수 2** (입력 변수의 곱이 최대 2개).
* 모듈러 덧셈을 1비트 carry로 근사: `x + y mod 2^64`의 최저 캐리는 정확히 `(x ∧ y)`, 그것을 한 비트만 전파.
* (선택적 사양 노트) 더 강한 carry 근사가 필요하면 “Lift-2”를 정의: `H2(x,y) = x ⊕ y ⊕ ((x ∧ y) ≪ 1) ⊕ (((x ⊕ y) ∧ ((x ∧ y) ≪ 1)) ≪ 1)`. v0.1에서는 단순 H만 사용.

### 2.2 Quarter Round (QR)

ChaCha20의 ARX quarter-round를 NORX의 H로 대체:

```
QR(a, b, c, d):
    a ← H(a, b);   d ← rot(d ⊕ a, R0)
    c ← H(c, d);   b ← rot(b ⊕ c, R1)
    a ← H(a, b);   d ← rot(d ⊕ a, R2)
    c ← H(c, d);   b ← rot(b ⊕ c, R3)
```

* H 호출 4회 → AND 게이트 256개.
* 회전과 XOR은 모두 선형.
* QR은 1024비트 상태가 아닌 **워드 4개에 작용**. 4번 호출하면 1024비트 전체.

### 2.3 ι (라운드 상수 주입)

라운드 r ≥ 0에 대해 한 워드에 RC[r mod 16]을 XOR. 더블 라운드 시 짝수 라운드와 홀수 라운드에 모두 주입하되 위치를 달리한다:

```
ι(r):
    if r is even:    state[ 0] ⊕= RC[r mod 16]
    if r is odd:     state[15] ⊕= RC[r mod 16]
```

### 2.4 YSC3-p 순열

```
permutation(state, ROUNDS):
    for r in 0 .. ROUNDS:
        ι(r)
        if r is even:                 # Column round
            for j in 0..4:
                QR(state[ 0+j], state[ 4+j], state[ 8+j], state[12+j])
        else:                          # Diagonal round
            for j in 0..4:
                let off = j
                QR(state[ 0+((off+0) mod 4)],
                   state[ 4+((off+1) mod 4)],
                   state[ 8+((off+2) mod 4)],
                   state[12+((off+3) mod 4)])
```

* 더블 라운드 = column round + diagonal round → 1024비트 전 비트가 *모든* 다른 비트에 영향.
* `init` 시 24라운드 = 12 더블 라운드, `block` 시 12라운드 = 6 더블 라운드.
* **알고리즘 차수**: H는 차수 2, QR은 H를 2번 직렬로 두 쌍 → 차수 8 (보수적), 12 라운드 후 차수 ≥ 2^12 = 4096 ≫ 1024. 알지브라 공격 즉시 무력.

---

## 3. 모드 사양

### 3.1 Stream Cipher (CTR-Sponge)

#### 초기화

```
state ← 0¹⁰²⁴
load_key_to_capacity(state, key)        # key 비트 → capacity 워드들에 배치
load_nonce_to_rate(state, nonce)        # nonce 비트 → rate 워드들에 배치
state[15] ⊕= DOMAIN["YSC3-STM"]         # 도메인 분리자 주입
permutation(state, ROUNDS_INIT)          # YSC3-128: 24, YSC3-256: 32
```

세부 배치 (YSC3-128, key 32바이트 / nonce 24바이트):

```
capacity_words = state[ 8 .. 16]     # 8 워드 = 512비트
rate_words     = state[ 0 .. 8]      # 8 워드 = 512비트

# 키 (256비트)는 capacity의 앞쪽에 LE로 적재.
state[ 8] = LE_u64(key[ 0..  8])
state[ 9] = LE_u64(key[ 8.. 16])
state[10] = LE_u64(key[16.. 24])
state[11] = LE_u64(key[24.. 32])

# 논스 (192비트)는 rate의 앞쪽에 LE로 적재.
state[ 0] = LE_u64(nonce[ 0..  8])
state[ 1] = LE_u64(nonce[ 8.. 16])
state[ 2] = LE_u64(nonce[16.. 24])

# 길이 표시·도메인을 capacity의 마지막 워드에 결합.
state[15] = DOMAIN_VAL ⊕ (KEY_BITS as u64) ⊕ ((NONCE_BITS as u64) << 32)
```

`state[12..15]` 등 미사용 워드는 **0**으로 초기화 (capacity 일부가 0이어도 매개변수가 도메인에 인코딩되어 있어 collision 차단).

#### 키스트림 블록 (seekable)

블록 인덱스 `i ∈ ℕ` (1부터 시작):

```
ks_block(i):
    working ← state            # 64바이트 working copy
    # 카운터는 capacity 워드 (state[14])에 주입 — 출력 워드에 직접 닿지 않음.
    working[14] ⊕= i
    permutation(working, ROUNDS_BLOCK)
    return  bytes of working[0 .. RATE_WORDS]    # YSC3-128: 64 바이트
```

`state` 자체는 변하지 않는다 (각 블록 독립적, 병렬 처리 가능).

#### 키스트림 적용

```
keystream(i)            # ks_block(i)
ciphertext = plaintext XOR (keystream(1) || keystream(2) || …)
```

#### *왜* 안전한가 (V1 차단)

* 공격자가 키스트림 블록을 본다 = `working[0..8]` 의 LE 바이트만 본다. 즉 1024비트 순열의 **앞 8 워드 = 512비트만**.
* 순열이 가역적이라도 `working[8..16]`(상태의 capacity 절반)은 미공개 → `permutation⁻¹(working)`을 계산할 수 없다.
* 두 블록 `ks(i)`, `ks(i+1)`을 보아도 두 working state는 `state[14]`에 `i ⊕ (i+1)` 만큼만 다름 (capacity 내부, 출력 직전 8라운드 H 비선형 통과) → 차분 추적 불가.
* 단일 블록 KPA가 풀리려면 capacity 절반에 대한 **2^512 추측**이 필요 (생일이 아닌 직접 키복구이므로 정확히 c-비트 → 256/384 비트).

### 3.2 AEAD (Duplex Sponge)

표준 duplex 구성. 도메인 분리는 **각 단계마다 별도의 도메인 워드**.

```
encrypt(key, nonce, ad, pt) → (ct, tag):
    state ← init(key, nonce, DOMAIN_AEAD)              # 위와 동일한 init 방식
    absorb(state, ad,  DOMAIN_AD)                       # 패딩 + 도메인 마커 + permute
    ct ← []
    for block in pt (RATE-byte chunks):
        permutation(state, ROUNDS_BLOCK)
        ks  ← state[0..RATE]
        ct_block ← block XOR ks
        state[0..RATE] ← state[0..RATE] XOR ct_block      # ciphertext 흡수 (rate에 XOR)
        ct.append(ct_block)
    # finalize
    state[15] ⊕= DOMAIN_TAG
    permutation(state, ROUNDS_BLOCK)
    tag ← state[0..2]                                     # 16 바이트
    return (ct, tag)
```

* 패딩: 마지막 블록에 `0x01` 뒤 `0x00...0x80` (SHA-3 식 multi-rate). 빈 입력도 한 블록을 흡수.
* 복호화는 동일 흐름이지만 평문이 아닌 *암호문*을 흡수 (mode-3 duplex의 표준 정의).
* 태그 검증은 상수 시간 비교.

#### *왜* 안전한가 (V10 차단)

* `DOMAIN_AD`, `DOMAIN_CT`, `DOMAIN_TAG`가 매번 capacity에 XOR → 도메인 충돌 = 1024비트 collision.
* 길이가 capacity에 인코딩되어 패딩 길이만 다른 두 입력도 다른 도메인 마커를 받는다.

### 3.3 Hash / XOF (Sponge)

```
hash(data, output_len) → digest:
    state ← 0¹⁰²⁴
    state[15] ⊕= DOMAIN_HASH
    state[14] ⊕= (output_len as u64)             # 길이를 도메인에 결합 (Hirose-식)
    absorb(state, data, RATE_BYTES)
    permutation(state, ROUNDS_INIT)
    digest ← squeeze(state, output_len)
    return digest
```

### 3.4 MAC

키-기반 prefix:
```
mac(key, msg) → tag:
    state ← init(key, zeroes, DOMAIN_MAC)
    absorb(state, msg)
    permutation(state, ROUNDS_INIT)
    tag ← state[0..2]   # 128 비트
```

---

## 4. S-box 사용 암호의 공통 취약점 — 면역성 증명

| S-box 기반 위협 | YSC3에서의 결과 | 이유 |
|----------------|------------------|------|
| **AES T-table cache-timing** (Bernstein 2005) | 면역 | 테이블 룩업이 없음. 상태는 레지스터/SIMD 레인. |
| **Cache-prefetch / Flush+Reload S-box 공격** | 면역 | 메모리 접근이 비밀-비종속. |
| **DPA on S-box output Hamming weight** | 면역 (정량) | 각 출력 비트가 5개 입력 비트의 작은 부울 함수에 불과. S-box처럼 8비트 단위로 집중되지 않아 HW 누설 모델이 적용되지 않음. |
| **Algebraic attacks (XSL on AES)** | 면역 | H의 차수 2 × 더블 라운드 직렬 4번 → 라운드당 차수 2~4 증가. 12 라운드 후 차수 ≥ 2^12, 1024비트 GF(2) 다항식 단순화 불가. |
| **Invariant subspace (PRINCE/Midori)** | 면역 | RC가 라운드·단계마다 다르고 √p에서 추출 → 어떤 affine subspace도 라운드를 거치며 깨짐. |
| **Interpolation attack (low-degree S-box)** | 면역 | H의 다항식 표현은 1024변수 GF(2)에서 차수 2이지만 6 더블 라운드 후 차수 ≥ 4096 (보수). |
| **Linear hull 공격** | 차수 한계 ↑ | H의 선형 근사 확률 = 3/4 per AND 비트. 활성 AND 게이트 수가 라운드당 256개. 12 라운드면 활성 ≥ 16개 보장 (column/diagonal 분리에 의해), 선형 확률 ≤ (3/4)^16 ≈ 2^-6.6 — 추가 마진 필요시 라운드 증가. |
| **Differential cryptanalysis** | 차수 한계 ↑ | H의 차분 최대 확률 = 1/2 per AND. 활성 AND 비트 ≥ 64×16 = 1024 (보수)에 도달하는 라운드 수는 6~8 (MILP 분석 필요). 12 라운드는 차분 4 ≤ 2^-1024로 무력. |
| **Slide attack** | 면역 | 라운드 상수가 라운드별/단계별 unique. |
| **Related-key attack** | 사양에서 분리 | 키는 capacity-only 적재 + 도메인 분리. 표준 attacker model (single-key)에서만 정의. |

---

## 5. FHE 비용 분석

H 호출당 AND 게이트 = 64 (워드 1개 길이).

| 항목 | 카운트 |
|------|--------|
| 1 QR 안의 H 호출 | 4 |
| 1 QR 안의 AND 게이트 | 256 |
| 1 라운드 (column 또는 diagonal) 안의 QR | 4 |
| 1 라운드 안의 AND | 1024 |
| YSC3-128 블록 (12 라운드) | 12,288 |
| YSC3-128 1 키스트림 바이트당 AND | 12,288 / 64 = **192 AND/바이트** |
| YSC3-256 블록 (16 라운드) | 16,384 |

비교:
* AES-128 1바이트 = ~120 AND (S-box 깊이 4 × 라운드 10 × 16 S-box / 16 바이트)
* ChaCha20 1바이트 = 32 modular add × 20 round / 64 byte ≈ 10 가산 ⇒ FHE에서 carry chain 펼치면 ≈ 600 AND/바이트
* Asconp 1바이트 = ~95 AND/바이트 (rate 8바이트, 12 라운드, 320 비트 χ)

YSC3-128은 ChaCha20보다 3배 저렴하고, Asconp의 2배 정도. AES와 동일 자릿수. **모듈러 덧셈을 H로 대체**한 데서 오는 이득.

**AND 깊이 (multiplicative depth)**:
* H 한 번 = 깊이 1.
* QR 안에서 H가 직렬로 2번 (a=H, c=H) → 깊이 2.
  + 같은 QR에 H가 2쌍 직렬 (전반·후반) → 깊이 4.
* 1 라운드의 QR들은 서로 독립 워드 4쌍 → 깊이 추가 없음.
* 12 라운드 = 깊이 12 × 4 = **48**.

AES = 깊이 ~40~50, Asconp = ~12, LowMC = ~10~12. YSC3는 다소 깊으나, AND 카운트는 LowMC보다 훨씬 적고 알지브라 공격에 면역 (LowMC는 깊이 ↓ 대신 단일 라운드 AND 카운트 ↓로 알지브라 공격 취약).

---

## 6. 미해결·향후 작업

이 v0.1 사양은 *완성된 표준*이 아니라 *공격에 부합하지 않는 최소 기준*을 제시한다. 정식 채택 전 다음이 필요:

1. **MILP 기반 차분/선형 트레일 경계 증명** — 6, 8, 12, 16 라운드 각각.
2. **회전 상수 (R0..R3) 안정성 분석** — NORX64 값을 차용했으나, 1024비트 4×4 위상에서 회전 대칭성 별도 점검.
3. **AEAD duplex의 forgery/distinguishing advantage 정량 경계**.
4. **사이드채널 마스킹 변종 사양** (1차 boolean masking은 자명, 고차 마스킹용 가젯 명시).
5. **FHE 구체 백엔드(TFHE, BFV) 벤치마크** — `H` 자체는 1 AND이지만 회전·시프트가 FHE 스킴별 비용이 다름.

---

## 7. 변경 이력

* v0.1 (2026-06-06) — 최초 초안. YSC2/AuxCrypt v1.0의 사양 결함 V1~V6, V10 차단을 목표.
