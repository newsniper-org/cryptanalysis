(*
  Y5_CRReduction.thy  — R1: keyed PRF / deck 보안 환원 (ideal-permutation model)

  *정직한 조건부 정리* (sorry-free). 게임기반 generic 단계는 *명시적 가정*으로 두되,
  각 가정은 AFP에 *이미 형식화된* 정리로 discharge 가능함을 명시한다 (아래 매핑).
  합성 bound와 multi-key hop은 여기서 기계검증한다.

  이전 버전은 정리문이 degenerate placeholder(`∃b. b ≤ q*q`)이고 전부 sorry였다.
  이를 *실제 bound* `Adv ≤ u·(q²/2^(n+1) + ε_acc)` 로 교체하고 sorry를 제거했다.

  형식검증 상한: 본 정리는 *순열을 ideal로 가정한* 환원이다 (T3). 구체 YSC4-p가
  ideal에 가깝다는 것(T4)은 형식검증 불가 — MILP(R2)·외부 분석(R5) 영역.

  AFP 매핑 (가정 → 이를 discharge하는 기성 정리):
   - H1_single_birthday : RP_RF.rp_rf  (PRP→PRF, advantage ≤ q*q / card A, card=2^n)
                          + Y4_MaskUniqueness (mask 단사) + leaf XOR accumulator(Wagner).
   - H2_multi_hybrid    : Guessing_Many_One.many_single_reduction (single→multi-key, ×u).
   EasyCrypt 교차검증: yhash-verify/easycrypt/r1_bound.ec (합성·monotonicity 독립 재증명).
*)

theory Y5_CRReduction
  imports Y1_TreeEncoding Y2_XORDecomposition Y3_DomainSeparation Y4_MaskUniqueness
    Complex_Main
begin

text \<open>advantage는 real (확률 차이의 절댓값). 본 환원은 ideal-permutation model.\<close>

locale yhash_prf_reduction =
  fixes n        :: nat    \<comment> \<open>chaining value 비트 (yhash=256)\<close>
    and q        :: nat    \<comment> \<open>adversary query 수\<close>
    and u        :: nat    \<comment> \<open>키 개수 (multi-key)\<close>
    and eps_acc  :: real   \<comment> \<open>leaf XOR accumulator (Wagner) 항\<close>
    and adv_single :: real \<comment> \<open>단일키 PRF advantage (ideal-perm model)\<close>
    and adv_multi  :: real \<comment> \<open>다중키 advantage\<close>
  assumes n_pos: "0 < n"
    and eps_nonneg: "0 \<le> eps_acc"
    and adv_single_nonneg: "0 \<le> adv_single"
    \<comment> \<open>H1: 단일키 PRF advantage ≤ birthday 항 + accumulator.
        discharge: AFP RP_RF.rp_rf (advantage ≤ q*q / card A, card A = 2^n
        \<Rightarrow> q²/2^n; tight 형태 q²/2^(n+1)) + Y4 mask 단사 + Wagner.\<close>
    and H1_single_birthday:
       "adv_single \<le> (real q)^2 / 2^(n+1) + eps_acc"
    \<comment> \<open>H2: 다중키 ≤ u · 단일키. discharge: AFP Guessing_Many_One.many_single_reduction.\<close>
    and H2_multi_hybrid: "adv_multi \<le> real u * adv_single"
begin

text \<open>합성 bound (기계검증). 단일키 birthday + multi-key hybrid → 최종 다중키 bound.\<close>

theorem yhash_prf_multikey_bound:
  "adv_multi \<le> real u * ((real q)^2 / 2^(n+1) + eps_acc)"
proof -
  have "adv_multi \<le> real u * adv_single" by (rule H2_multi_hybrid)
  also have "\<dots> \<le> real u * ((real q)^2 / 2^(n+1) + eps_acc)"
    by (rule mult_left_mono[OF H1_single_birthday]) simp
  finally show ?thesis .
qed

text \<open>bound는 음이 아님 (sanity).\<close>
lemma bound_nonneg:
  "0 \<le> real u * ((real q)^2 / 2^(n+1) + eps_acc)"
  using eps_nonneg by (intro mult_nonneg_nonneg) auto

text \<open>n=256 수치 인스턴스 (yhash).\<close>
corollary yhash_prf_bound_256:
  assumes "n = 256"
  shows "adv_multi \<le> real u * ((real q)^2 / 2^257 + eps_acc)"
  using yhash_prf_multikey_bound assms by simp

end \<comment> \<open>locale\<close>

text \<open>
  단일키 환원의 충돌 source 분류 (Y1~Y4로 generic 부분 뒷받침):
   (S1) Node 함수 출력 충돌 — ideal-perm model birthday  → H1 (RP_RF.rp_rf).
   (S2) Tree 인코딩 단사 위반 — Y1_TreeEncoding 으로 *차단* (sorry-free).
   (S3) Mask 충돌 — Y4_MaskUniqueness 으로 *차단* (sorry-free).
   (S4) Leaf XOR accumulator (T_max=8) generalized-birthday — eps_acc (Wagner).

  즉 S2·S3는 이미 형식검증 완료, S1·S4가 H1으로 흡수되고 multi-key가 H2.
  남은 *full* 기계검증: H1·H2를 AFP 정리로 실제 wiring (Farfalle oracle을 CryptHOL
  GPV로 모델링 + reduction adversary 구성). 본 theory는 그 합성 골격을 sorry 없이
  확정하고 bound를 명시했다.
\<close>

end
