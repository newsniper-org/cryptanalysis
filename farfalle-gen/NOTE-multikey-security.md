# NOTE — YSC5 Multi-key 보안 분석

> *META.md §7 Q7* — "YSC5가 멀티-키 보안 (multi-key indistinguishability)를 어떻게 보장하나?"
> Mennink-style 분석의 초기 작업.

## 1. 모델

### Single-key PRF-IND
표준 PRF distinguishing game: 어드버서리 *A* 가 oracle `O_K = YSC5_PRF(K, .)`와
*진짜 랜덤 함수* `R` 사이를 구분하는 advantage:
$ "Adv"^"PRF"_"YSC5"(A) := abs(Pr[A^{O_K} = 1] - Pr[A^R = 1]) $

### Multi-key PRF-IND
$U$개의 *독립 키* `K_1, …, K_U`를 동시에 부여:
$ "Adv"^"MK-PRF"_"YSC5"(A, U) := abs(Pr[A^{O_{K_1}, …, O_{K_U}} = 1] - Pr[A^{R_1, …, R_U} = 1]) $

Multi-key 환원의 핵심 질문: $"Adv"^"MK-PRF"(A, U) ≤ U dot.c "Adv"^"PRF"(A')$?

표준 키-격리 (key-isolation) 환원으로 *대략적 한계*가 보장됨:
$ "Adv"^"MK-PRF"(A, U) ≤ U dot.c "Adv"^"PRF"(A) + (q^2/2) \/ 2^c $

여기서 $q$ = 총 queries, $c$ = capacity 비트. *YSC5-128*: $c = 512$, 따라서 생일 항은 $q^2 \/ 2^{512}$.

## 2. Farfalle-specific 환원 (Bertoni et al. 2017)

Farfalle의 multi-key 환원은 다음 두 단계:

1. **Mask seed의 multi-key 분리**: 각 키 $K_u$에서 mask seed $k_u = p_c(K_u)$. 
   서로 다른 키의 mask seed가 *분리됨* (= XOR-누적이 다름) → 압축 단계에서 *cross-key* leak 없음.

2. **Cycle 길이 보장에 의한 collision-free**: γ-roll의 cycle ≥ $2^{c/2}$ (= 2^256 for YSC5-128).
   서로 다른 $u$의 mask trajectory가 collision-free.

Mennink-style 한계 (lemma 4 in Farfalle paper, adapted):
$ "Adv"^"MK-PRF"_"YSC5"(A, U) ≤ "Adv"^"PRP"_"YSC4-p_c"(A) + (U q + q^2) \/ 2^c $

여기서 *PRP advantage*는 YSC4-p_c (24 라운드 순열)의 random permutation 거리.

## 3. 가정 검토

| 가정 | 본 사양에서의 상태 |
|------|------------------|
| YSC4-p_c (24 라운드) ≈ random permutation | *가정* (별도 분석 필요 — MILP, sampling) |
| Capacity = 512 비트 (YSC5-128) | 사양 확정 |
| Nonce 24 byte 충돌-free 한계 | $2^{96}$ — 실용적으로 충분 |
| Mask seed 독립 (서로 다른 K_u) | 보장 — 키 적재가 K로부터 결정적 |

## 4. Potential weakness 검토

### W1. Birthday on mask seed
다른 키 K_u, K_v가 *같은* mask seed를 생성할 확률 = $2^{-c}$ (= $2^{-512}$ for c=512).
$U$ 개 키 중 한 쌍이 충돌할 확률 $≈ U^2 / 2^c$. $U = 2^{64}$까지는 $2^{128} / 2^{512} = 2^{-384}$로 무시 가능.

### W2. Cross-key mask collision
같은 키 내에서 mask 시퀀스 $γ^i(k_u)$, $γ^j(k_u)$이 충돌 → 압축 출력에서 cancellation
유도 가능. 차수 분석 (Q2)로 ord($γ^k$) > $2^{60}$ 보장 → 실용적으로 무시 가능.

다른 키 사이의 mask collision: $γ^i(k_u) = γ^j(k_v)$, 즉 $k_v = γ^{i-j}(k_u)$.
$k_v$는 $p_c(K_v)$의 출력으로, $p_c$가 random permutation이면 이 등식이 우연일 확률 $≈ 2^{-c}$.
$U$ 키 × $q$ 쿼리 ≈ $Uq / 2^c$ → multi-key 한계의 $Uq/2^c$ 항.

### W3. Related-key 공격
공격자가 $K, K \oplus Δ$ 같은 관련 키 쌍에 접근 가능하다면:
- $p_c(K) \oplus p_c(K \oplus Δ)$ 가 작은 차분일 확률.
- YSC4-p_c (24 라운드)의 차분 저항 ≥ $2^{-c}$로 추정 (별도 분석).
- 본 사양은 *single-key model*만 정의 — related-key는 *out of scope*.

## 5. CryptHOL 형식 증명 skeleton

```isabelle
theory YSC5_MultiKey
  imports CryptHOL.CryptHOL
begin

text \<open>
  multi-key PRF game. U = #keys, q = #queries per key.
\<close>

definition mk_prf_advantage :: "nat \<Rightarrow> ... \<Rightarrow> real" where
  "mk_prf_advantage U q adv = ..."

theorem mk_prf_reduction:
  fixes A :: "..."
  shows "mk_prf_advantage U q (Adv_MK A) \<le>
         single_prf_advantage A + (real (U * q + q^2)) / (real (2 ^ capacity_bits))"
  sorry  \<comment> \<open>증명 미완 — 별도 연구과제\<close>

end
```

위 skeleton의 `sorry` 자리를 채우는 정식 증명은 *research-grade* 작업으로
별도 학술 발표/검증의 대상.

## 6. 권고

| 항목 | 권고 |
|------|------|
| 본 v0.1 사양에서 multi-key claim | *informal* 으로 명시 (Farfalle 환원 + capacity 한계) |
| Formal proof | CryptHOL로 별도 진행 — 연구 산출물 수준 |
| 공격자 모델 | *single-key* 만 보장 (related-key는 future work) |
| Nonce 안전 | $≥ 2^{96}$ 메시지 안전 (collision 확률 negligible) |

## 7. 결론

YSC5의 multi-key 보안은 Farfalle의 표준 환원에 의해 *큰 한계*까지 보장됨:
$ "Adv"^"MK-PRF" leq U dot.c "Adv"^"PRP"_"YSC4-p" + (U q + q^2) \/ 2^c $

본 v0.1에서는 *informal claim*으로 두고, 정식 CryptHOL 증명은 future work으로 분리.

핵심 가정 (`YSC4-p_c ≈ random permutation`)의 정량 평가는 MILP/SAT 기반 cryptanalysis로
별도 보장 (milp/analysis.md 참조).
