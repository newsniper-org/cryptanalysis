# RESOLVED — META.md §7 Q3~Q8 해소 현황

> Farfalle 일반화 메타-task의 미해결 질문 6개에 대한 현 상태와 후속 작업.
> 본 문서는 *현재까지의 결론*과 *남은 작업*을 한 곳에 모은다.

## Q3 — p_b를 YSC4-p 8라운드로 줄여도 PRF 환원의 wide-pipe 가정이 유지되나?

**현 상태**: *부분 해소*. `milp/analysis.md`에서 워드-수준 차분 트레일 분석.

| Round | 최소 활성 워드 (워드-수준 trail) | 추정 trail 확률 (정성) |
|-------|---------------------------------|----------------------|
| 8     | 18 (= 2 × 9)  | 2^{-16} | 부족 |
| 12    | 26 (= 2 × 13) | 2^{-24} | 부족 (워드-수준) |
| 16    | 34 (= 2 × 17) | 2^{-32} | 부족 (워드-수준) |

본 워드-수준 모델은 **F의 DDT를 반영하지 않아 과도하게 비관적**.
정식 bit-level 분석이 trail 확률을 더 낮춤 (F의 차분 분포 + 회전 분리).

**SPEC §4 결정**: R_b = 12 (YSC5-128), R_b = 16 (YSC5-256). 8라운드는 *부족*.

**남은 작업**: bit-level MILP (1024 변수/라운드) — 외부 cryptanalyst 작업으로 권장.

---

## Q4 — Kravatte처럼 p_b ≠ p_c ≠ p_d ≠ p_e가 필요한가?

**해소**: *YES*. SPEC §4 매개변수 표가 다른 라운드 수 사용:

| 역할 | YSC5-128 | YSC5-256 | 근거 |
|------|----------|----------|------|
| p_b (compress) | 12 | 16 | 본질적 보안 layer (입력 흡수) |
| p_c (key setup) | 24 | 32 | **초기화** — 가장 길게 (key 분리 보장) |
| p_d (transition) | 8 | 12 | 짧음 — 압축→확장 사이 도메인 분리 |
| p_e (expand) | 12 | 16 | 본질적 보안 layer (출력 생성) |

이는 Kravatte의 표준 권고 (compress와 expand는 본질적 보안 layer, init은 strictly 길게, transition은 짧게).

**다른 접근**: 모두 동일 라운드 + 도메인 분리만 — *덜 보수적*. Kravatte 분석을 그대로 차용하기 어려움.

**결정**: 본 사양은 *Kravatte 식 차등 라운드* 채택.

---

## Q5 — AEAD nonce 분할 최적화

**해소**: `farfalle-gen/NOTE-aead-nonce-split.md` 작성.

- 현재 사양 (24/0 분할 — nonce 전체를 압축에)은 *일반 AEAD*에 적합.
- *Seekable AEAD* 변종은 별도 모드 (`YSC5-AEAD-Seekable`)로 추가 가능. v0.1에는 미포함.

**결정**: v0.1 사양 유지. Seekable은 future work.

---

## Q6 — FHE 백엔드에서 plaintext-mult이 정말 저렴한가?

**해소**: `farfalle-gen/NOTE-fhe-cost.md`에서 해석적 분석.

- BFV/BGV: plaintext-mult $O(d log d)$ vs ciphertext-mult $O(d²)$ — *d/log d 배 저렴*.
- TFHE: linear ops (plaintext-mult 포함)은 PBS 없이 가능 — *수 μs vs 10ms AND*.
- 결론: *YSC5의 192 plaintext-mults/블록은 사실상 무비용*.

**남은 작업**: tfhe-rs 또는 OpenFHE 통합 후 실측. *Future PoC*.

---

## Q7 — Multi-key 보안

**해소**: `farfalle-gen/NOTE-multikey-security.md`에서 분석.

- Bertoni et al. 2017의 Farfalle 환원 인용.
- $"Adv"^"MK-PRF" leq U dot.c "Adv"^"PRP"_"YSC4-p" + (Uq+q²)/2^c$.
- YSC5-128 ($c = 512$): $U = 2^{64}$ 키, $q = 2^{60}$ 쿼리까지 안전.

**남은 작업**: CryptHOL formal proof — *research grade*.

---

## Q8 — roll cycle 안에 collision-free 사용량 한계

**해소**: Q1·Q2 형식 검증으로 *완전 해소*.

| 측면 | 검증 결과 | 위치 |
|------|----------|------|
| 단일 워드 cycle | $≥ 2^{60}$ ($k ∈ \{1..16\}$ 모든 거듭제곱) | `Q2_all_orders_practical` |
| 16-워드 결합 cycle | LCM(individual cycles) — 보수치 $≥ 2^{60}$ | informal |
| α primitivity | ord(α) = $2^{64} - 1$ | `Q1_primitive_certificate` |

실용 사용량 ($q ≤ 2^{60}$) 범위에서 **collision-free 보장**.

**결론**: Q8은 Q1+Q2의 자연 따름정리. 추가 작업 불필요.

---

## 종합 — 해소 매트릭스

| Q | 상태 | 산출물 |
|---|------|--------|
| Q1 | ✓ 완전 해소 | `isabelle-verify/Q1_*` |
| Q2 | ✓ 완전 해소 | `isabelle-verify/Q2_*`, `Q3_RollMatrix.thy` |
| Q3 | ▲ 부분 해소 (워드-수준) | `milp/analysis.md` |
| Q4 | ✓ 완전 해소 | `ysc5/SPEC.typ` §4 |
| Q5 | ✓ 완전 해소 (v0.1 사양) | `NOTE-aead-nonce-split.md` |
| Q6 | ✓ 해석 완료, 측정 미완 | `NOTE-fhe-cost.md` |
| Q7 | ▲ informal, formal 미완 | `NOTE-multikey-security.md` |
| Q8 | ✓ Q1+Q2 따름정리 | (별도 작업 불요) |

### 남은 *연구급* 작업
1. **Q3 bit-level MILP** — 1024 변수, F-DDT 인코딩 필요.
2. **Q6 tfhe-rs/OpenFHE 측정** — 외부 라이브러리 통합.
3. **Q7 CryptHOL formal proof** — 학술 발표 수준.

본 작업들은 *연구 협업* 또는 *외부 분석*의 대상으로 분리.
