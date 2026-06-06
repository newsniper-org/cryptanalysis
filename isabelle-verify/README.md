# Isabelle/HOL 형식 검증 — YSC4/5 α-primitivity

본 디렉토리는 NOTE-orthomorphism-roll-coincidence.md §6의 가정 Q1·Q2를 **Isabelle/HOL의 `by eval`** (code-generation reflection)로 *kernel-checked* 증명한다.

## 검증 대상

### Q1 — α는 GF(2⁶⁴)의 primitive element
- 정의: `GF(2⁶⁴) = GF(2)[x] / p(x)`, `p(x) = x⁶⁴ + x⁴ + x³ + x + 1`
- `α = x mod p(x)` (= 64-bit 워드 `2` 값)
- 주장: `α`의 곱셈 차수는 정확히 `2⁶⁴ − 1 = 18,446,744,073,709,551,615`
- 전략 (Pohlig–Hellman의 표준 primitivity test):
  - `2⁶⁴ − 1`의 소인수 분해: `3 · 5 · 17 · 257 · 641 · 65537 · 6,700,417` (7개)
  - 각 소인수 `q`에 대해 `α^((2⁶⁴-1)/q) ≠ 1` 검증
  - 추가로 `α^(2⁶⁴ − 1) = 1` 확인 (Fermat 형 정리)
- 결과: `Q1_primitive_certificate` theorem.

### Q2 — k ∈ {1..16}에 대한 `α^k` 차수 분포
- 정리: `ord(α^k) = (2⁶⁴ − 1) / gcd(k, 2⁶⁴ − 1)`
- 각 k에 대해 `gcd(k, 2⁶⁴ − 1)` 계산:
  - k = 1,2,4,7,8,11,13,14,16 → gcd = 1 → α^k도 primitive (차수 N)
  - k = 3,6,9,12 → gcd = 3 → 차수 N/3
  - k = 5,10 → gcd = 5 → 차수 N/5
  - k = 15 → gcd = 15 → 차수 N/15 (16개 중 최저)
- 최저 차수도 `N/15 > 2⁶⁰` 임을 별도 확인 → 실용 한계를 압도.
- 결과: `Q2_gcd_table`, `Q2_ysc4_min_order_lower_bound`, `Q2_all_orders_practical`.

## 파일 구조

| 파일 | 내용 |
|------|------|
| `ROOT` | session 정의 (parent: HOL-Library) |
| `GF64.thy` | GF(2⁶⁴) 산술 (64-bit Word 기반, code-generation 호환) |
| `Q1_Primitivity.thy` | Q1 증명 |
| `Q2_Cycles.thy` | Q2 증명 |
| `LOG.md` | 빌드·증명 결과 |

## 빌드 방법

```bash
cd /home/ybi/cryptanalysis/isabelle-verify
/opt/isabelle/bin/isabelle build -D .
```

## 신뢰 기반 (TCB)

`by eval` 증명 방법은 다음을 신뢰한다:
1. Isabelle 커널 (LCF-style minimal kernel)
2. Isabelle 코드 생성기 (HOL → SML)
3. PolyML 런타임 (SML 컴파일러)

이는 abstract 수학 정의(예: `Polynomial.IsPrimitive`)에 의존하지 않고 *계산의 결과*를 신뢰한다. 본 task가 본질적으로 "단일 다항식의 primitivity"라는 *계산 가능한 사실*이므로 이 접근이 충분하다.

더 강한 신뢰를 원하면:
- `Polynomial_Factorization` 등 AFP entry로 abstract 정의와 우리 bit-level 구현의 등가성 증명 (별도 작업)
- mathlib의 `GaloisField.IsPrimitive` 처럼 추상 정리 활용

본 task는 Q1·Q2가 NOTE의 *전제*로 쓰이는 단계의 검증이므로, `by eval` 수준이 적절.
