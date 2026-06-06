# Isabelle/HOL 형식 검증 빌드 로그

## 환경
- Isabelle 버전: **Isabelle2025-2**
- 위치: `/opt/isabelle/bin/isabelle`
- ML 런타임: `polyml-5.9.2_x86_64_32-linux`

## Session 구성
- 이름: `YSC_Probe`
- 부모 session: `HOL-Library`
- Theory chain: `GF64.thy → Q1_Primitivity.thy → Q2_Cycles.thy`

## 빌드 결과

```
$ /opt/isabelle/bin/isabelle build -D /home/ybi/cryptanalysis/isabelle-verify
Running YSC_Probe ...
Finished YSC_Probe (0:00:03 elapsed time, 0:00:07 cpu time, factor 2.47)
0:00:06 elapsed time, 0:00:07 cpu time, factor 1.23
EXIT=0
```

**모든 `by eval` 증명 통과.** Heap database (`YSC_Probe.db`)와 로그 (`YSC_Probe.gz`)
`~/.isabelle/Isabelle2025-2/heaps/polyml-5.9.2_x86_64_32-linux/log/`에 생성.

## 증명된 정리

### Q1 (`Q1_Primitivity.thy`) — α는 GF(2⁶⁴)의 primitive element

| Theorem | 명제 | 증명 방법 |
|---------|------|----------|
| `N_value` | `N = 18446744073709551615` | `by eval` |
| `N_factorization` | `N = 3·5·17·257·641·65537·6700417` | `by eval` |
| `Q1_alpha_pow_N_div_3` | `gf_pow α (N div 3) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_5` | `gf_pow α (N div 5) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_17` | `gf_pow α (N div 17) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_257` | `gf_pow α (N div 257) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_641` | `gf_pow α (N div 641) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_65537` | `gf_pow α (N div 65537) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_div_6700417` | `gf_pow α (N div 6700417) ≠ 1` | `by eval` |
| `Q1_alpha_pow_N_eq_one` | `gf_pow α N = 1` | `by eval` |
| `Q1_primitive_certificate` | (위 모든 조항의 conjunction) | `by eval` |

→ **α는 GF(2⁶⁴)*의 primitive element. 곱셈 차수 정확히 2⁶⁴−1.** (Pohlig–Hellman 식 standard primitivity test 완료)

### Q2 (`Q2_Cycles.thy`) — α^k 차수 분포 (k ∈ {1..16})

| Theorem | 명제 | 증명 방법 |
|---------|------|----------|
| `Q2_gcd_table` | k=1..16에 대한 gcd(k, N) 정확값 | `by eval` |
| `Q2_ysc4_min_order_lower_bound` | `N div 15 > 2⁶⁰` | `by eval` |
| `Q2_all_orders_practical` | `∀k∈{1..16}. N div gcd(k, N) > 2⁶⁰` | `by eval` |

**gcd(k, N) 분포** (Q2_gcd_table):

| k | gcd(k, N) | ord(α^k) |
|---|-----------|----------|
| 1 | 1 | N (primitive) |
| 2 | 1 | N (primitive) |
| 3 | 3 | N/3 |
| 4 | 1 | N (primitive) |
| 5 | 5 | N/5 |
| 6 | 3 | N/3 |
| 7 | 1 | N (primitive) |
| 8 | 1 | N (primitive) |
| 9 | 3 | N/3 |
| 10 | 5 | N/5 |
| 11 | 1 | N (primitive) |
| 12 | 3 | N/3 |
| 13 | 1 | N (primitive) |
| 14 | 1 | N (primitive) |
| 15 | 15 | N/15 (k ∈ 1..16의 *최저 차수*) |
| 16 | 1 | N (primitive) |

→ **모든 k ∈ {1..16}에 대해 ord(α^k) > 2⁶⁰.** YSC4의 σ-layer (k ∈ {1,3,5,7})도 모두 ≥ N/5.

## 신뢰 기반 (TCB)

본 검증의 신뢰 기반:
1. Isabelle 커널 (LCF-style, ~3000 LOC ML)
2. Isabelle 코드 생성기 (HOL → SML 변환)
3. PolyML 컴파일러 + 런타임

`by eval`은 명제를 SML 코드로 컴파일·실행하고 결과를 LCF 정리로 reflection. 표준적 trust extension.

## 트러블슈팅 메모 (해결한 시행착오)

1. **Cartouche 파싱 문제** — `‹...›` (U+2039/U+203A) 사용 시 `Malformed command syntax` →
   ASCII-only `(* ... *)` 사용으로 우회.

2. **`AND`/`XOR` 중위 연산자 인식 안 됨** —
   `Bit_Operations.xor` / `Bit_Operations.and` prefix 함수로 대체.

3. **`Code_Target_Nat`/`Code_Target_Numeral` 충돌** —
   `Code_Target_Numeral` 제거. `Code_Target_Nat`만 import.

4. **`odd b` (word) 타입클래스 충돌** —
   `Code_Target_Nat`이 `odd x ≡ ¬ (2 dvd x)` 등식을 도입해 `word :: semidom_modulo`를 요구.
   `bit b 0` (직접 비트 테스트)로 대체.

5. **`gf_pow_zero` lemma의 `simp` 폭주** — 80회 unfolding 불가능 →
   해당 lemma 제거 (Q1·Q2에는 필요 없음).

## 시사

NOTE-orthomorphism-roll-coincidence.md §6의 Q1·Q2 검증 항목이 **기계 검증된 정리**로 격상.
이제 YSC5 사양서에서 다음을 *증명된 가정*으로 인용 가능:
- C3 (cycle 길이 2⁶⁴−1) — Q1로 입증
- C5 (16 워드 distinct cycle) — Q2로 일부 입증 (모든 ord > 2⁶⁰)
- C9 (최대 주기 LFSR과 동등) — Q1로 입증
