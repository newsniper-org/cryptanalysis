(*
  Y2p_XORDecomposition.thy
  ypsilenti는 32-bit word로 작업. 본 정리는 u32에 대한 XOR 분해.
*)

theory Y2p_XORDecomposition
  imports Main "HOL-Library.Word"
begin

abbreviation bxor :: "32 word \<Rightarrow> 32 word \<Rightarrow> 32 word" (infixl "\<oplus>" 65) where
  "bxor a b \<equiv> Bit_Operations.xor a b"

fun acc :: "32 word list \<Rightarrow> 32 word" where
  "acc []      = 0"
| "acc (v # vs) = v \<oplus> acc vs"

lemma bxor_assoc: "(a \<oplus> b) \<oplus> c = a \<oplus> (b \<oplus> c)"
  by (simp add: xor.assoc)

lemma acc_append:
  "acc (xs @ ys) = acc xs \<oplus> acc ys"
proof (induction xs)
  case Nil show ?case by simp
next
  case (Cons x xs)
  have "acc ((x # xs) @ ys) = x \<oplus> acc (xs @ ys)" by simp
  also have "... = x \<oplus> (acc xs \<oplus> acc ys)" using Cons.IH by simp
  also have "... = (x \<oplus> acc xs) \<oplus> acc ys" using bxor_assoc by simp
  also have "... = acc (x # xs) \<oplus> acc ys" by simp
  finally show ?case .
qed

theorem Y2p_decomposition:
  "acc (xs @ ys) = acc xs \<oplus> acc ys"
  by (rule acc_append)

end
