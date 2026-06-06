(*
  GF64.thy
  GF(2^64) = GF(2)[x] / p(x),  p(x) = x^64 + x^4 + x^3 + x + 1.
  64-bit word arithmetic. Code-generation compatible (by eval).

  Uses Bit_Operations.xor / Bit_Operations.and as prefix functions
  because the infix AND/XOR syntax does not parse in Isabelle 2025-2's
  HOL-Library.Word without additional setup.
*)

theory GF64
  imports
    Main
    "HOL-Library.Word"
begin

abbreviation bxor :: "64 word \<Rightarrow> 64 word \<Rightarrow> 64 word" where
  "bxor a b \<equiv> Bit_Operations.xor a b"

abbreviation band :: "64 word \<Rightarrow> 64 word \<Rightarrow> 64 word" where
  "band a b \<equiv> Bit_Operations.and a b"

definition reduction :: "64 word" where
  "reduction = 27"

definition alpha :: "64 word" where
  "alpha = 2"

definition alpha_mul :: "64 word \<Rightarrow> 64 word" where
  "alpha_mul y =
     (let top  = drop_bit 63 y;
          mask = - top
      in bxor (push_bit 1 y) (band mask reduction))"

fun gf_mul_iter :: "nat \<Rightarrow> 64 word \<Rightarrow> 64 word \<Rightarrow> 64 word \<Rightarrow> 64 word" where
  "gf_mul_iter 0 a b acc = acc"
| "gf_mul_iter (Suc n) a b acc =
     gf_mul_iter n
       (alpha_mul a)
       (drop_bit (Suc 0) b)
       (if odd b then bxor acc a else acc)"

definition gf_mul :: "64 word \<Rightarrow> 64 word \<Rightarrow> 64 word" where
  "gf_mul a b = gf_mul_iter 64 a b 0"

fun gf_pow_iter :: "nat \<Rightarrow> 64 word \<Rightarrow> nat \<Rightarrow> 64 word \<Rightarrow> 64 word" where
  "gf_pow_iter 0 base e acc = acc"
| "gf_pow_iter (Suc n) base e acc =
     gf_pow_iter n
       (gf_mul base base)
       (e div 2)
       (if odd e then gf_mul acc base else acc)"

definition gf_pow :: "64 word \<Rightarrow> nat \<Rightarrow> 64 word" where
  "gf_pow base e = gf_pow_iter 80 base e 1"

lemma alpha_squared: "alpha_mul alpha = 4"
  by (simp add: alpha_def alpha_mul_def reduction_def)

lemma gf_pow_zero: "gf_pow base 0 = 1"
  by (simp add: gf_pow_def)

lemma gf_pow_one_alpha: "gf_pow alpha 1 = alpha"
  by eval

end
