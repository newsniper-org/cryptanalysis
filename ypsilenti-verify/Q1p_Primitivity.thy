(*
  Q1p_Primitivity.thy
  α = x ∈ GF(2^32) = GF(2)[x] / (x^32 + x^22 + x^2 + x + 1)  [reduction 0x400007]
  가 primitive (= 차수 2^32 - 1) 인지 검증.  (다항식은 GF32.thy의 reduction과 일치.)

  2^32 - 1 = 4,294,967,295 = 3 × 5 × 17 × 257 × 65537 (5 소인수).
*)

theory Q1p_Primitivity
  imports GF32
begin

definition N32 :: nat where
  "N32 = (2::nat)^32 - 1"

theorem N32_value:
  "N32 = 4294967295"
  unfolding N32_def by eval

theorem N32_factorization:
  "N32 = 3 * 5 * 17 * 257 * 65537"
  unfolding N32_def by eval

(* 각 소인수 q에 대해 α^(N32/q) ≠ 1 검증 *)

theorem Q1p_alpha_pow_N_div_3:     "gf_pow alpha (N32 div 3) \<noteq> 1"     unfolding N32_def by eval
theorem Q1p_alpha_pow_N_div_5:     "gf_pow alpha (N32 div 5) \<noteq> 1"     unfolding N32_def by eval
theorem Q1p_alpha_pow_N_div_17:    "gf_pow alpha (N32 div 17) \<noteq> 1"    unfolding N32_def by eval
theorem Q1p_alpha_pow_N_div_257:   "gf_pow alpha (N32 div 257) \<noteq> 1"   unfolding N32_def by eval
theorem Q1p_alpha_pow_N_div_65537: "gf_pow alpha (N32 div 65537) \<noteq> 1" unfolding N32_def by eval

(* α^N32 = 1 (Fermat) *)
theorem Q1p_alpha_pow_N32_eq_one:
  "gf_pow alpha N32 = 1"
  unfolding N32_def by eval

(* 종합 — α primitive certificate *)
theorem Q1p_primitive_certificate:
  "gf_pow alpha (N32 div 3) \<noteq> 1
   \<and> gf_pow alpha (N32 div 5) \<noteq> 1
   \<and> gf_pow alpha (N32 div 17) \<noteq> 1
   \<and> gf_pow alpha (N32 div 257) \<noteq> 1
   \<and> gf_pow alpha (N32 div 65537) \<noteq> 1
   \<and> gf_pow alpha N32 = 1"
  unfolding N32_def by eval

end
