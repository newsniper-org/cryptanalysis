# NOTE — YSC4 orthomorphism 요구와 Farfalle roll 요구의 동시 충족 구조

> **요지.** YSC4 σ-GLM에서 σ가 Vaudenay 의미의 orthomorphism이 되기 위한 조건과,
> Farfalle에서 mask roll γ가 만족해야 하는 조건이 모두 **GF(2⁶⁴)에서 α(=x)가 primitive element**라는 *하나의 사실*로 귀결된다.
> 이 노트는 그 이유와 거기서 도출되는 11개 결론을 한 곳에 정리한다.

---

## 1. 두 요구사항의 형식적 정의

### 1.1 YSC4 σ-GLM의 orthomorphism 요구 (Vaudenay 1999)
σ가 *orthomorphism* 이려면 두 조건이 동시에 성립:
* **(O1)** σ가 bijection.
* **(O2)** `x ↦ x ⊕ σ(x)`도 bijection.

(O2)가 핵심 — classical Lai-Massey의 `L⊕R = const` 불변량을 깨는 데 정확히 이 성질이 쓰임.

### 1.2 Farfalle roll γ의 요구 (Bertoni–Daemen 2017)
roll `γ`가 *adequate*이려면:
* **(R1)** γ는 bijection (mask가 자기 자신으로 무한히 반복되지 않도록).
* **(R2)** γ의 **cycle 길이** ≫ 실제 사용량 (= mask collision-free 사용 가능).
* **(R3)** 연속한 마스크 `{γ⁰(k), γ¹(k), …, γⁿ(k)}`이 *충분한 선형 독립성*을 가짐 (PRF 환원의 wide-pipe 가정).

---

## 2. 두 요구가 *같은 한 가지 사실*로 환원되는 이유

YSC4와 본 사양은 σ = γ = `α-mult`, 즉 `GF(2⁶⁴) = GF(2)[x]/p(x)`에서 `x`(생성원 후보)로 곱하기를 채택했다.
이 선택만으로:

### 2.1 (O1) — σ가 bijection
α가 GF(2⁶⁴)의 *비제로 원소*이면, 곱셈 `x ↦ α·x`는 GF(2⁶⁴)*에서 bijection. ✓ (단위원이므로 자명)

### 2.2 (O2) — `x ↦ x ⊕ α·x = (α+1)·x`도 bijection
`α+1`이 GF(2⁶⁴)의 *비제로 원소*이면 마찬가지로 bijection.

**핵심 보조사실**: `α+1 = (x+1) mod p(x)`. p(x)가 64차 *기약*다항식이고 (x+1)은 1차이므로, p(x) ∤ (x+1) → `α+1 ≠ 0` in GF(2⁶⁴). ✓

여기서 멈추면 (O2)는 *p(x)가 기약*이라는 약한 조건만 요구한다.

### 2.3 (R1) — γ가 bijection
α가 비제로이면 자명. (O1)과 동일. ✓

### 2.4 (R2) — cycle 길이 ≫ 사용량
이제 *primitive*가 등장한다. `α-mult`의 cycle 길이는 곱셈군 ⟨α⟩의 order. GF(2⁶⁴)* 자체는 cycle 길이 `2⁶⁴ − 1`인 순환군이지만, ⟨α⟩의 order는 `2⁶⁴ − 1`의 약수.

* p(x)가 단순히 *기약*이면 α의 order는 ≥ 2 (= 2⁶⁴−1의 약수 중 1보다 큰 것).
* p(x)가 *primitive* (irreducible + α가 GF(2⁶⁴)* 생성원)이면 α의 order = **2⁶⁴ − 1 ≈ 1.84 × 10¹⁹**.

**YSC4 사양의 채택**: p(x) = x⁶⁴ + x⁴ + x³ + x + 1. 이 다항식이 *primitive*인지가 (R2) 충족의 결정 요인.

(이는 META Q1에서 PoC로 확인할 항목이지만, p(x)는 ISO-3309 CRC-64 다항식으로 표준 참조에서 primitive로 분류된다.)

### 2.5 (R3) — 연속 mask의 선형 독립성
`α`가 primitive이면 `{1, α, α², …, α⁶³}`이 GF(2⁶⁴)를 GF(2)-vector space로 본 *기저*. 따라서 첫 64개의 마스크 `{k, αk, α²k, …, α⁶³k}` (k ≠ 0)도 선형 독립. Kravatte/Farfalle 환원이 요구하는 wide-pipe 조건을 자동 충족. ✓

---

## 3. 왜 *하나의 다항식*으로 모든 요구를 충족하는가

| 요구 | 어떤 조건으로 환원되나 | p(x)에 부과하는 조건 |
|------|------------------------|---------------------|
| (O1) σ bijection | α ≠ 0 in GF(2⁶⁴) | p(x) 기약이면 자동 |
| (O2) (α+1) bijection | α+1 ≠ 0 in GF(2⁶⁴) | p(x) 기약이면 자동 (deg(x+1) < deg(p)) |
| (R1) γ bijection | α ≠ 0 in GF(2⁶⁴) | p(x) 기약이면 자동 |
| (R2) ord(α) ≫ 사용량 | α primitive | **p(x) primitive** |
| (R3) 64-차원 선형 독립 | α primitive | **p(x) primitive** |

⇒ p(x) = x⁶⁴ + x⁴ + x³ + x + 1 이 **primitive irreducible**이라는 *하나의 사실*이 (O1)~(R3)을 전부 충족.

→ YSC4가 σ로 채택한 함수와 Farfalle가 γ로 요구하는 함수가 **수학적으로 같은 함수**여서 호환되는 것이 아니라, **같은 다항식 한 줄로 두 요건이 동시 환원되어 가능**.

---

## 4. 도출되는 결론 11가지

### C1. 하나의 primitive로 두 역할
같은 `alpha(y)` 함수가 σ-layer (YSC4)와 roll-mask (YSC5/Farfalle)에서 **동일 코드**로 재사용된다. 구현 단일화 + 검증 단일화.

### C2. YSC5는 새 primitive를 도입할 필요 없음
YSC4의 `gf2_64.rs::alpha`를 그대로 import 하면 됨. 새 수학적 객체 없음.

### C3. 마스크 cycle은 실용적으로 무한
`2⁶⁴ − 1 ≈ 1.84 × 10¹⁹` masks/워드. 10⁹ blocks/s × 100년 ≈ 3.15 × 10¹⁸ < cycle. 실제 시스템 운영 수명을 *몇 자릿수 초과*한 안전 마진.

### C4. 처음 64개 마스크는 GF(2)-기저
Kravatte의 LFSR이 갖는 wide-pipe 성질을 자동으로 가짐 → PRF 환원이 그대로 적용 가능.

### C5. 16 워드 × distinct α^k 트랙
YSC5 (16-워드 상태)에서 마스크는 워드별 `α^(i+1) · k_i` (i = 0..15). 각 워드가 *서로 다른 cycle 시작점*을 가지면서도 같은 primitive 사용. 결합 cycle은 LCM(개별 cycle)로 (2⁶⁴ − 1)¹⁶ 까지 가능 → 단어 capacity 요구치 `2^c/2 = 2^256`을 압도.

### C6. FHE에서 roll은 사실상 무료
α-mult은 plaintext × ciphertext 곱이므로 BFV/TFHE의 *부트스트래핑 불필요*. 16개 워드를 동시에 roll 해도 AND 카운트 증가량 = **0**. Farfalle의 압축 단계 비용이 순수히 `p_b` 비용으로 환원.

### C7. 분기 없는 상수시간
α-mult = `(y << 1) ^ ((y >> 63) * 0x1B)`. 데이터 의존 분기·메모리 접근 모두 없음. 즉 *cache-timing/branch-prediction*에 면역. YSC4의 부채널 등급을 그대로 계승.

### C8. 결정적·이식 가능
GF(2⁶⁴) 곱은 잘 정의된 대수 연산. 플랫폼 종속 동작 없음 (signed-shift 의존도 없음, mask 형식이 명확). musl/wasm32/임베디드 모두 동일.

### C9. 최적의 선형 roll
정보이론 관점에서, primitive α에 의한 곱은 **최대 주기 (2⁶⁴−1) LFSR과 동등**. 64-비트 단어에 대해 *어떤 선형 roll도 이보다 더 긴 cycle을 가질 수 없다*. 결정적으로 *상한이 달성된* 선택.

### C10. AEAD 모드 확장 무비용
Farfalle-SANE/SANSE의 AEAD 변종도 roll γ를 그대로 사용. YSC5에서 별도 변경 없이 모드 확장이 가능. (META §3.F의 F1+F2+F3 통합 사양이 가능한 이유.)

### C11. 사양 자유도 축소
YSC5 사양에서 남은 결정사항은 다음으로 압축됨:
* p_b / p_c / p_d / p_e 의 라운드 수 (4개 자연수)
* 도메인 분리자 문자열 (Stream/AEAD/Hash 용)
* 매개변수 집합 (128-bit / 256-bit 보안)

순열 자체(YSC4-p), roll 함수(α-mult), 상태 폭(1024), 마스크 스킴, orthomorphism은 **모두 이미 결정됨**.

---

## 5. 사양 결정 *직전* 단계의 함의

| 결정 사항 | 본 노트가 시사하는 바 |
|----------|---------------------|
| α 선택 | x ∈ GF(2)[x]/p(x), p(x) = x⁶⁴+x⁴+x³+x+1. 변경 불가 (수학적 최적). |
| roll γ | `roll(k_0, k_1, …, k_{15}) = (α^1·k_0, α^2·k_1, …, α^{16}·k_{15})`로 *워드별 distinct power*. |
| 마스크 초기화 | YSC4 sponge 초기화처럼 `k = p_c(key)`로 단일 init. roll은 그 이후 단계. |
| Roll 적용 횟수 | 압축 i번째 블록 = `roll^i(k)` 사용. cycle 문제 무시 가능. |

---

## 6. 추후 검증 (PoC) 항목

본 노트의 결론들은 다음 *가정*에 의존하므로 사양 작성 직전에 한 번 더 수치 검증 권장:

| 가정 | 검증 방법 | META 항목 |
|------|-----------|----------|
| p(x) = x⁶⁴ + x⁴ + x³ + x + 1 이 primitive (= ord(α) = 2⁶⁴−1) | 2⁶⁴−1의 prime divisor q마다 `α^((2⁶⁴-1)/q) ≠ 1` 확인 | **Q1** |
| `α^k` for k ∈ {1, …, 16}이 모두 distinct primitive (서로 cycle 동일) | 작은 PoC | **Q2** |
| Roll cycle (2⁶⁴−1)¹⁶이 실제로 collision-free 사용 한계 ≥ 2²⁵⁶ | 이론적으로 자명, 수치 확인 불요 | — |
| α-mult이 FHE 백엔드에서 진짜 plaintext-mult로 컴파일 | BFV/TFHE 라이브러리에서 직접 측정 | **Q6** |

---

## 7. 한 줄 요약

> **YSC4가 Lai-Massey 구조의 약점을 메우려고 도입한 “σ = GF(2⁶⁴) 곱” 한 줄이,
> 동시에 Farfalle의 mask-roll 요구사항(cycle, 선형 독립, FHE 비용)을 *수학적으로 최적*으로 충족한다.
> 즉 YSC5는 별도의 새 primitive 도입 없이 YSC4-p × Farfalle 만으로 정의 가능하다.**

본 노트는 *코드를 만들기 전 단계*의 정리이며, 사양 작성 시 §4의 결론 11개와 §6의 검증 항목을 인용해 사용한다.
