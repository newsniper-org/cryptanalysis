# Farfalle 일반화 — YSC5 설계를 위한 meta-task

> 이 문서는 *코드를 작성하기 전 단계*다. Farfalle 구성을 직교 설계축으로 분해하고,
> 각 축의 선택지를 정리한 뒤 YSC5가 점할 수 있는 좌표를 식별한다.
> 최종 사양은 본 문서의 결론을 토대로 별도 작성한다.

---

## 1. Farfalle baseline

Bertoni–Daemen–Hoffert–Peeters–Van Assche–Van Keer가 ToSC 2017에 제안한 **permutation-based PRF construction**.
설계 모토: *“입력은 동시에 압축, 출력은 동시에 확장”*. 즉 sponge처럼 순차가 아닌 **bow-tie/butterfly 형태**의 데이터 흐름.

### 1.1 구성 요소

| 기호 | 의미 |
|------|------|
| `b` | 상태 비트 폭 (Kravatte: 1600) |
| `p_b` | **압축 단계 permutation** (b-bit) |
| `p_c` | 키 → 마스크 변환 permutation |
| `p_d` | 압축 → 확장 전이 permutation |
| `p_e` | **확장 단계 permutation** |
| `γ_c, γ_e` | **roll 함수** (b-bit linear shift류) |
| `K` | 마스터 키 |
| `k = p_c(K∥pad)` | 작업용 마스크 시드 |

### 1.2 PRF 호출 흐름

```
PRF(K, M_0 ∥ M_1 ∥ … ∥ M_{n-1}):
    k  = p_c(K∥pad)                                     # 키 확장 (한 번)
    Y  = ⊕_{i=0..n-1}  p_b( M_i ⊕ γ_c^i(k) )            # ← 압축 (병렬)
    Y' = p_d(Y) ⊕ γ_e^0(k')                              # 전이
    for j = 0, 1, 2, …:
        Z_j = p_e( Y' ⊕ γ_e^j(0) )                      # ← 확장 (병렬)
        output Z_j
```

* 압축 단계는 **i에 대해 완전 병렬**이며 incremental (블록 추가만 하면 누적).
* 확장 단계도 **j에 대해 완전 병렬**.
* 한 번 압축한 `Y`로부터 임의 길이의 출력 시퀀스를 만들 수 있음.
* roll 함수 `γ`는 매우 저렴 (1-비트 LFSR류). 보안은 `p_*`가 담당.

### 1.3 Kravatte instantiation (1 예)

| 컴포넌트 | 값 |
|---------|-----|
| `b`     | 1600 |
| `p_b`   | Keccak-p[1600, 6 라운드] |
| `p_c`   | Keccak-p[1600, 6 라운드] |
| `p_d`   | Keccak-p[1600, 4 라운드] |
| `p_e`   | Keccak-p[1600, 4 라운드] |
| `γ_c, γ_e` | 1600-비트 LFSR (Keccak의 lane 단위 회전 + 비트 시프트) |

→ **하나의 기본 순열(Keccak-p)을 라운드 수만 달리하여 4개의 역할에 재사용**.

### 1.4 Farfalle의 매력 (왜 YSC5의 후보인가)

| 특성 | Sponge (YSC3/YSC4) | **Farfalle** |
|------|---------------------|--------------|
| 압축 | 순차 absorb | **병렬 XOR-sum** |
| 출력 | 순차 squeeze | **병렬 expand** |
| Incremental update | 어려움 (재시작 필요) | 자명 (블록 누적) |
| FHE bootstrapping | 블록간 직렬 | **블록간 독립 → batch 가능** |
| SIMD/멀티코어 | 한 cipher 인스턴스 내 부분 병렬 | **광역 병렬** |
| 보안 환원 | sponge indifferentiability | Farfalle dedicated 환원 (Mennink-style) |

FHE 백엔드와 멀티코어 환경에서 *근본적으로 다른* 성능 특성을 보임. YSC5가 이를 차용하면 v3·v4 사용 시나리오를 모두 흡수 가능.

---

## 2. 독립 설계축 (orthogonal axes)

Farfalle를 분해하면 다음 6개의 직교 결정으로 환원된다.

| 축 | 무엇을 결정하나 | Farfalle 기본값 |
|----|----------------|-------------|
| **A. Input model** | 입력의 모양 (단일 메시지 vs 다중 채널) | 단일 메시지 |
| **B. Mask scheme** | 마스크 `k_i`를 어떻게 만드나 | 선형 roll `γ^i(k)` |
| **C. Compression op** | `n`개 블록을 어떻게 누적하나 | XOR-sum |
| **D. Permutation reuse** | `p_b, p_c, p_d, p_e` 관계 | 다른 라운드 수의 같은 primitive |
| **E. Expansion op** | 출력 블록 생성 방식 | rolling state + `p_e` |
| **F. Security target** | PRF, AEAD, hash, … | PRF (확장으로 다른 모드) |

각 축은 다른 축의 선택과 **무관하게 변경 가능** (단, 보안 환원은 조합별로 재증명 필요).

---

## 3. 각 축의 일반화 선택지

### 3.A — 입력 모델

| 선택지 | 정의 | 보안/사용성 함의 |
|--------|------|----------------|
| **A1** | 단일 메시지 `M_0∥…∥M_{n-1}` | 기본 PRF |
| **A2** | (Key, Nonce, AD, Plaintext)의 4-튜플 | AEAD 자연. 각 채널별 도메인 분리자 |
| **A3** | 트리/세트 구조 (집합 멤버십, 다대다) | hashed proofs, set-membership PRF |
| **A4** | Streaming online (전체 길이 미리 모름) | live encryption, 통신 stream |

YSC5 권장: **A2** — AEAD가 주 용도. 도메인 분리는 mask offset으로 구현 가능.

### 3.B — 마스크 derivation `k → k_i`

| 선택지 | 정의 | 비용 | 보안성 | FHE 비용 |
|--------|------|------|--------|---------|
| **B1** | 선형 roll `k_i = γ^i(k)` (LFSR) | 매우 저렴 | 검증됨 (Farfalle) | 매우 저렴 (선형) |
| **B2** | 순열-반복 `k_i = p_c^i(k)` | 비쌈 | 자명히 안전 | 비쌈 (라운드마다 AND) |
| **B3** | **GF(2⁶⁴) 곱셈** `k_i = α^i · k` (워드별) — YSC4의 σ를 차용 | 저렴 (plaintext-mult) | orthomorphism, cycle 2⁶⁴−1 | **사실상 0 AND** |
| **B4** | 해시 `k_i = XOF(k, i)` | 비쌈 | 강함 | 비쌈 |
| **B5** | 독립 랜덤 마스크 (one-time pad식) | 비실용적 (저장 비용) | 정보이론적 | 무의미 (저장만) |

**핵심 관찰 (YSC4 ↔ Farfalle 다리)**:
* YSC4의 σ-mult가 마침 **GF(2⁶⁴)의 orthomorphism**.
* 단일 워드(64비트)에 대해 cycle 길이 `2⁶⁴ − 1` 보장.
* 1024-비트 상태에 대해서는 **워드별 독립 α-곱**으로 확장: `roll(k) = (α·k_0, α²·k_1, …, α¹⁶·k_{15})`.
  → 각 워드가 독립 LFSR로 doubling. 전체 상태의 cycle은 워드별 cycle의 LCM에 가까움.
* YSC5는 B3 채택이 자연스러움 — *YSC4의 σ가 그대로 Farfalle의 γ가 됨*.

### 3.C — 압축 연산

| 선택지 | 정의 | 병렬성 | 보안성 |
|--------|------|--------|--------|
| **C1** | `Y = ⊕ᵢ p_b(M_i ⊕ k_i)` (Farfalle) | 완전 병렬 | 표준 PRF 증명 |
| **C2** | `Y = Σᵢ p_b(M_i ⊕ k_i) mod 2^b` | 완전 병렬 | FHE에서 carry 비용 |
| **C3** | Lai-Massey reduce: `Y = ⊕ᵢ (k_i, p_b(M_i ⊕ k_i)) via σ-broadcast` | 완전 병렬 | YSC4 스타일이지만 단계 복잡 |
| **C4** | Sequential sponge absorb | **직렬** | sponge 환원 |

YSC5 권장: **C1** — Farfalle의 XOR-sum이 가장 단순하고 FHE-친화.

### 3.D — 순열 재사용 방식

| 선택지 | 정의 | 비고 |
|--------|------|------|
| **D1** | 4개 독립 permutation `p_b, p_c, p_d, p_e` | 큰 설계 부담 |
| **D2** | 같은 primitive, 라운드 수 다르게 (Kravatte) | 합리적 절충 |
| **D3** | **같은 primitive, 같은 라운드, 도메인 분리자만 다름** | 가장 깔끔, 보안 분석은 더 까다로움 |
| **D4** | 하나의 permutation을 horizon-extension만 다르게 (라운드 자릿수 동적) | 실용성 낮음 |

YSC5 권장: **D2** — `p_c` (init용)는 충분히 많은 라운드(예 24), `p_b`/`p_e`는 더 적게(예 12). YSC4-p를 라운드 수만 달리.

### 3.E — 확장 (출력 생성)

| 선택지 | 정의 | 비고 |
|--------|------|------|
| **E1** | `Z_j = p_e(Y' ⊕ γ_e^j(0))` (Farfalle) | 표준 |
| **E2** | `Z_j = p_e(Y') ⊕ γ_e^j(0)` (rolling 후처리) | 더 약함, 분석 필요 |
| **E3** | CTR-style: `Z_j = p_e(Y' ∥ counter_j)` | 카운터를 상태 일부에 주입 |
| **E4** | Sponge squeeze | 직렬 |

YSC5 권장: **E1** — Farfalle 그대로. roll γ_e는 B3(σ-mult)을 재사용.

### 3.F — 보안 타깃

| 모드 | Farfalle 위 정의 | 비고 |
|------|------------------|------|
| **F1** | PRF (default Farfalle) | (key, msg) → tag/stream |
| **F2** | Stream cipher | F1의 expansion만 사용, nonce 입력 |
| **F3** | AEAD (Kravatte-SANE, -SANSE) | duplex-Farfalle hybrid |
| **F4** | Wide-block cipher (Kravatte-WBC) | F1 + Feistel layer |
| **F5** | Hash/XOF | unkeyed Farfalle |
| **F6** | Tweakable PRP | F1 + tweak slot |

YSC5 권장: **F1 + F2 + F3** — 한 사양서 안에 세 모드를 제공 (Kravatte 스타일).

---

## 4. YSC4 σ-mult ↔ Farfalle roll의 정합성

이 절은 *수치 검증이 필요한 핵심 가설*이다. 사양 작성 전에 PoC 실험을 한 번 더 돌려 확인할 항목들.

### 4.1 가설

> **(H1)** YSC4의 `α-mult(y) = (y<<1) ⊕ (mask & 0x1B)`은 GF(2⁶⁴)의 단위원 곱이며 cycle 길이는 `ord(α) | 2⁶⁴ - 1`. α가 generator라면 정확히 `2⁶⁴ - 1`.

> **(H2)** 1024-비트 상태에 대해 워드별로 α-mult을 적용하면 (각 워드가 같은 α로 multiply), 전체 상태의 roll cycle은 `ord(α)`와 같다 — 모든 워드가 동시 같은 cycle.

> **(H3)** 워드 i에 대해 `α^(i+1)`-mult을 적용하는 (= YSC4의 σ-layer 패턴), `roll`은 각 워드의 cycle 길이가 `ord(α) / gcd(ord(α), i+1)`이고, 전체 cycle은 워드별 cycle의 LCM.

> **(H4)** Farfalle의 `γ_c^i(k)` 시퀀스에서 “마스크들이 충돌하지 않아야” 라는 요구사항은 cycle 길이 ≫ 사용량으로 충족.

### 4.2 검증해야 할 수치
* `α`가 `GF(2⁶⁴) = GF(2)[x]/(x⁶⁴+x⁴+x³+x+1)`에서 generator인지 (= ord(α) = 2⁶⁴ − 1).
  - 만약 generator가 아니면 `α^k`로 generator 후보를 탐색.
* 1024-비트 상태에서 `roll` 한 번의 비용 (소프트웨어 cycles, FHE AND).
* 마스크가 평탄(uniform-looking)한지 — 통계적 NIST suite 일부 통과 확인 (사양 시점 이후 작업).

### 4.3 PoC 안

별도 코드 작성 — `farfalle-gen/probe/`에 작은 Rust bin을 두고:
```rust
fn main() {
    // 1) α의 order in GF(2^64) 확인
    // 2) 워드별 α^k-mult의 cycle 측정
    // 3) Farfalle roll로 사용했을 때 collision-free 길이 한계
}
```

이 항목은 **§7 미해결 질문**으로 보관 — 사양 결정 직전에 PoC 돌릴 것.

---

## 5. YSC5의 설계 공간 내 좌표

위 축들에서 YSC5의 *권장 좌표*는 다음과 같다. 각 좌표는 별도 사양서에서 정량화한다.

| 축 | YSC5 권장 좌표 | 근거 |
|----|----------------|------|
| **A** Input model | A2 (Key + Nonce + AD + PT 4-튜플) | AEAD가 주 용도 |
| **B** Mask scheme | **B3 (GF(2⁶⁴) α-mult, 워드별)** | YSC4 σ-mult과 동일 primitive → 구현 통일성 |
| **C** Compression | C1 (XOR-sum of `p_b`) | Farfalle 표준 |
| **D** Permutation reuse | D2 (YSC4-p, 라운드 수만 다름) | YSC4 재사용으로 코드/분석 비용 절감 |
| **E** Expansion | E1 (rolling state + `p_e`) | Farfalle 표준 |
| **F** Security target | F1 + F2 + F3 (PRF, stream, AEAD) | Kravatte 스타일 통합 사양 |

### 5.1 YSC5 캔디데이트 매개변수 (잠정)

| 항목 | 값 | 비고 |
|------|----|----|
| 상태 비트 폭 `b` | 1024 (YSC4와 동일) | 단일 primitive 재사용 |
| `p_b` 라운드 | 12 | 압축 (FHE 비용 부담) |
| `p_c` 라운드 | 24 | 초기 키 확장 |
| `p_d` 라운드 | 8 | 짧은 전이 |
| `p_e` 라운드 | 12 | 확장 |
| `γ_c`, `γ_e` | 워드별 α-mult (B3) | YSC4 σ 그대로 |
| 키 크기 | 256 비트 | YSC4-128과 동등 |
| Nonce 크기 | 192 비트 | YSC4와 동등 |
| Tag 크기 | 128 비트 | 표준 |

### 5.2 사양화 시 차별점 (YSC4 대비)

| 항목 | YSC4 (Sponge) | **YSC5 (Farfalle)** |
|------|---------------|---------------------|
| 압축 모델 | 직렬 absorb | **병렬 XOR-sum** |
| 확장 모델 | 직렬 squeeze | **병렬 expand** |
| 한 메시지 N블록 FHE 비용 | `N × AND(p_b)` (직렬) | `N × AND(p_b)` (배치) — *동일 AND이지만 wall-clock은 1/N* |
| 멀티 메시지 batch | 별개 인스턴스 | **하나의 expansion에서 N개 출력** |
| 코드 재사용 | sponge 모드 | Farfalle 모드 (sponge와는 다른 API) |
| 추천 시나리오 | 짧은 일회성 통신 | 긴 메시지, 다채널 batch, FHE |

---

## 6. 보안 환원 노트

Farfalle의 PRF 증명 (Bertoni et al. 2017, Mennink et al. 2018)은 다음 가정에 의존:
1. `p_b, p_c, p_d, p_e`가 **public random permutation** (PRP-distinguishable이 됨).
2. roll function `γ`가 **충분히 비-자명한 cycle** (≥ `2^c/2`)을 가져야 (c = capacity).
3. 키 확장 단계의 입력이 distinct (nonce 재사용 금지).

YSC5 변경점이 환원에 미치는 영향:
- **B3 (σ-mult roll)**: γ가 선형(B1)에서 GF(2⁶⁴) 곱(B3)로 바뀜. roll의 cycle이 더 길어지므로 (`2⁶⁴-1` per word) collision 확률 ↓. 환원은 그대로 적용되되, γ의 "linear independence of consecutive masks" 조건을 확인해야 함.
- **D2 (다른 라운드 수 같은 primitive)**: Kravatte와 같은 채택이므로 기존 환원이 그대로.

→ 별도의 형식 증명 없이도 “Kravatte 스타일 안전성”을 주장 가능.

---

## 7. 미해결 질문 (사양 작성 전 PoC로 풀 것)

| # | 질문 | 검증 방법 |
|---|------|-----------|
| Q1 | YSC4의 `α = x in GF(2)[x]/(x⁶⁴+x⁴+x³+x+1)`가 generator인가? (ord(α) = 2⁶⁴−1 ?) | 작은 PoC: `pow(α, (2⁶⁴-1)/q) ≠ 1` for each prime divisor q of 2⁶⁴−1 |
| Q2 | 워드별 `α^k`-mult이 16개 워드에서 모두 distinct cycle을 주는가? | `α^k`의 order 추적 (k=1,3,5,7,…,33) |
| Q3 | `p_b`를 YSC4-p 라운드 8로 줄여도 PRF 환원의 wide-pipe 가정이 유지되나? | 차분 트레일 MILP (별도 분석) |
| Q4 | Kravatte처럼 `p_b ≠ p_c ≠ p_d ≠ p_e`가 필요한가, 아니면 단일 라운드 카운트 + 도메인 분리로 충분한가? | 형식 증명 또는 attempted distinguisher |
| Q5 | AEAD 모드에서 nonce 일부를 압축에, 나머지를 확장 roll seed에 넣는 최적 분할은? | Kravatte-SANE 분석 차용 |
| Q6 | FHE 백엔드(BFV·TFHE)에서 plaintext-mult이 batch ciphertext-mult보다 실제로 저렴한가? (사양상 가정) | 외부 FHE 라이브러리로 즉정 |
| Q7 | YSC5가 멀티-키 보안 (multi-key indistinguishability)를 어떻게 보장하나? | Mennink-style 분석 |
| Q8 | roll의 cycle 한 바퀴(`2⁶⁴` 마스크) 안에 collision-free 사용량 한계는? | rho-method 추정 |

---

## 8. 다음 단계

1. **Q1, Q2 PoC 실행** — `farfalle-gen/probe/` 만들어 `α`의 order, `α^k`의 cycle 측정.
2. **사양서 작성** — 본 META의 §5 좌표를 기반으로 `ysc5/SPEC.md`를 단독 작성.
3. **모드별 분리** — Stream(F2) / AEAD(F3) / Hash(F5) 각각의 wrapper API.
4. **MILP 분석 (Q3)** — 별도 작업. YSC4의 분석을 라운드 카운트만 바꿔서 재사용 가능할 가능성.
5. **참조 구현** — YSC4와 같은 패턴 (`no_std`, musl, zeroize, `[features]`).

---

## 9. 메타-요약

* **Farfalle는 sponge와 직교** — 압축·확장 모두 병렬화. FHE/멀티코어 환경의 게임체인저.
* **YSC4의 σ-mult이 그대로 Farfalle roll로 작동** — 두 사양 사이의 *natural bridge*.
* **YSC5 = (YSC4-p 순열) × (Farfalle 구조) × (4-튜플 입력)** — 세 결정을 곱한 좌표.
* 메타 작업 결과 사양 결정에 남은 자유도는 **라운드 수 (`p_b`/`p_c`/`p_d`/`p_e`)와 도메인 분리자 구체값** 뿐.

본 문서는 *코드 작성 이전 단계*임을 명시. PoC와 사양서는 별도 작업.
