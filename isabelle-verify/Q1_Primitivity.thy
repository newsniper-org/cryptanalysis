(*
  Q1_Primitivity.thy
  Verify that alpha = x in GF(2^64) = GF(2)[x] / (x^64 + x^4 + x^3 + x + 1)
  is a primitive element of GF(2^64)*, i.e. has multiplicative order 2^64 - 1.

  Strategy: For each prime divisor q of (2^64 - 1), check that
  alpha^((2^64-1) / q) != 1. All seven such checks pass => order = 2^64 - 1.
*)

theory Q1_Primitivity
  imports GF64
begin

definition N :: nat where
  "N = (2::nat)^64 - 1"

theorem N_value:
  "N = 18446744073709551615"
  unfolding N_def by eval

(* 2^64 - 1 = 3 * 5 * 17 * 257 * 641 * 65537 * 6700417 *)
theorem N_factorization:
  "N = 3 * 5 * 17 * 257 * 641 * 65537 * 6700417"
  unfolding N_def by eval

theorem Q1_alpha_pow_N_div_3:        "gf_pow alpha (N div 3) \<noteq> 1"        unfolding N_def by eval
theorem Q1_alpha_pow_N_div_5:        "gf_pow alpha (N div 5) \<noteq> 1"        unfolding N_def by eval
theorem Q1_alpha_pow_N_div_17:       "gf_pow alpha (N div 17) \<noteq> 1"       unfolding N_def by eval
theorem Q1_alpha_pow_N_div_257:      "gf_pow alpha (N div 257) \<noteq> 1"      unfolding N_def by eval
theorem Q1_alpha_pow_N_div_641:      "gf_pow alpha (N div 641) \<noteq> 1"      unfolding N_def by eval
theorem Q1_alpha_pow_N_div_65537:    "gf_pow alpha (N div 65537) \<noteq> 1"    unfolding N_def by eval
theorem Q1_alpha_pow_N_div_6700417:  "gf_pow alpha (N div 6700417) \<noteq> 1"  unfolding N_def by eval

theorem Q1_alpha_pow_N_eq_one:
  "gf_pow alpha N = 1"
  unfolding N_def by eval

theorem Q1_primitive_certificate:
  "gf_pow alpha (N div 3) \<noteq> 1
   \<and> gf_pow alpha (N div 5) \<noteq> 1
   \<and> gf_pow alpha (N div 17) \<noteq> 1
   \<and> gf_pow alpha (N div 257) \<noteq> 1
   \<and> gf_pow alpha (N div 641) \<noteq> 1
   \<and> gf_pow alpha (N div 65537) \<noteq> 1
   \<and> gf_pow alpha (N div 6700417) \<noteq> 1
   \<and> gf_pow alpha N = 1"
  unfolding N_def by eval

end
