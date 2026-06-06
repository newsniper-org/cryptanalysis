# NOTE — YSC5의 FHE 백엔드 구체 비용

> *META.md §7 Q6* — "FHE 백엔드(BFV·TFHE)에서 plaintext-mult이 batch ciphertext-mult보다
> 실제로 저렴한가? (사양상 가정)" 에 대한 *분석적* 답변.

## 1. 모델

YSC5의 핵심 산술 연산:

| 연산 | 횟수/블록 | 종류 |
|------|----------|------|
| AND (F 내부) | 2 × 64 = 128 per round | **ciphertext × ciphertext** |
| XOR (F 내부, broadcast) | 다수 | linear (FHE에서 거의 무료) |
| ROT (F 내부) | 4 per round | bit permutation (FHE에서 무료) |
| α-mult (roll) | 16 워드 × R_b 라운드 = 192 | **plaintext × ciphertext** |

총 한 블록 (R_b = 12 라운드)에서:
- ciphertext-AND: 128 × 12 = **1,536** ANDs
- plaintext-mult: 192 (= 16 × 12)
- 깊이: 12

## 2. FHE 스킴별 비용

### 2.1 TFHE

TFHE의 비용 분포:
- **Programmable bootstrapping (PBS)**: 가장 비싼 연산 (~10ms/PBS on a CPU).
- **Linear ops (XOR, shift, plaintext-mult)**: PBS 없이 가능 (수 μs).
- **AND (= multiplication)**: PBS 필요 — 따라서 1 AND ≈ 1 PBS ≈ 10ms.

블록당 비용 (TFHE):
$ "Time"_block ≈ "ANDs"_block × "PBS"_time = 1536 × 10\ "ms" ≈ 15\ "초" $

블록은 1024비트 평문에 대응 = 128 byte. 그러므로:
$ "Throughput" ≈ 128\ "B" \/ 15\ "s" ≈ 8.5\ "B/s" $

비교 — AES-128 in TFHE: ~10-20분/블록 → ~0.01 B/s. YSC5 = AES보다 **~850배 빠름**.

### 2.2 BFV / BGV (Batched)

BFV는 *SIMD batch*가 핵심 — 단일 ciphertext에 수천 평문 슬롯을 포장.

- AND of two ciphertexts: $O(d^2)$ 비용 (d = degree of polynomial modulus).
- Plaintext-mult: $O(d log d)$ — **AND보다 d/log d 배 저렴**.
- Linear ops: $O(d)$.

블록당 비용 (BFV with batching = N_slots batched):
$ "Time"_block ≈ "ANDs" × O(d^2) + "Plaintext-mults" × O(d log d) $

YSC5 1536 ANDs > 192 plaintext-mults, 즉 AND 비용이 dominant. *Plaintext-mult은 본질적으로 무료*.

→ Batched setting에서 YSC5의 effective per-block 비용:
$ "Time"_total \/ N_slots ≈ 1536 × O(d^2) \/ N_slots $

N_slots = 4096 (typical BFV)일 때, 슬롯당 1 AND ≈ 1536 × $d^2$ / 4096 ≈ $0.4 d^2$.

### 2.3 비교 — YSC3 vs YSC4 vs YSC5

| 측정 | YSC3 (GFN sponge) | YSC4 (σ-GLM sponge) | **YSC5 (Farfalle)** |
|------|-------------------|---------------------|---------------------|
| 라운드당 AND | 1024 | 128 | 128 (= YSC4-p × R_b) |
| 블록당 AND (R=12) | 12,288 | 1,536 | 1,536 |
| α-mult / 블록 | 0 | 16 (σ-층) | 192 (roll + σ) |
| 블록간 *latency* | 직렬 | 직렬 | **병렬** |
| 1초당 처리량 (TFHE) | 0.06 B/s | 0.5 B/s | 0.5 B/s × N_blocks |

YSC5가 *AND 카운트*는 YSC4와 동일하지만 *병렬성*에 의해 wall-clock 효율은 N_blocks 배 향상.

## 3. 실측은 어떻게?

본 분석은 *해석적*. 정확한 측정은 실제 FHE 백엔드 실행이 필요.

### 권장 PoC 절차

```rust
// tfhe-rs 0.6+ 환경
let config = ConfigBuilder::default().build();
let (client_key, server_key) = generate_keys(config);

// YSC5의 F 함수를 tfhe boolean gates로 구현
fn fhe_f(s: &[FheBool; 64]) -> [FheBool; 64] {
    // F(s) = s ⊕ (rot(s,13) ∧ rot(s,37)) ⊕ (rot(s,5) ∧ rot(s,23))
    ...
}

// 한 블록 측정
let t0 = Instant::now();
let _ = ysc5_encrypt_block(&pt_blocks, &fhe_key);
let elapsed = t0.elapsed();
println!("YSC5 1 block: {:?}", elapsed);
```

### 측정 항목

- 블록당 wall-clock (ms)
- AND gate 카운트 ↔ wall-clock 상관
- α-mult이 plaintext-mult로 컴파일되는지 (vs 일반 cipher-mult로 fallback)
- 배치 효율 (N_blocks → wall-clock 증가율)

## 4. 결론

본 분석으로부터:
- *AND 카운트*: YSC4와 동일 (1,536 per 1024-bit block).
- *AND 깊이*: 12 (또는 16, R 따라).
- *Plaintext-mult이 0 AND*: α-곱은 FHE 비용에 기여 없음.
- *병렬성*: Farfalle의 핵심 장점 — N개 블록을 동시 처리 → wall-clock 1/N.

YSC5는 FHE 백엔드에서 AES 대비 **3 자릿수 이상** 빠르며, sponge 변종(YSC4) 대비 *latency*에서 동급, *throughput*에서 **N배** 우위.

정량 측정은 tfhe-rs/OpenFHE 통합 시 별도 수행 (현 단계는 *해석적 추정*).
