(*
  Y2_XORDecomposition.thy
  Farfalle 압축의 핵심 성질: acc(xs @ ys) = acc xs XOR acc ys.
  트리 구조 (left/right subtree)의 누산 분리 가능성 보장.
*)

theory Y2_XORDecomposition
  imports Main "HOL-Library.Word"
begin

abbreviation bxor :: "64 word \<Rightarrow> 64 word \<Rightarrow> 64 word" (infixl "\<oplus>" 65) where
  "bxor a b \<equiv> Bit_Operations.xor a b"

(* fold-style XOR over list *)
fun acc :: "64 word list \<Rightarrow> 64 word" where
  "acc []      = 0"
| "acc (v # vs) = v \<oplus> acc vs"

lemma bxor_assoc: "(a \<oplus> b) \<oplus> c = a \<oplus> (b \<oplus> c)"
  by (simp add: xor.assoc)

lemma bxor_commute: "a \<oplus> b = b \<oplus> a"
  by (simp add: xor.commute)

lemma bxor_left_commute: "a \<oplus> (b \<oplus> c) = b \<oplus> (a \<oplus> c)"
  by (simp add: xor.left_commute)

(* 핵심 — append 분해 *)
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

(* Y2 main *)
theorem Y2_decomposition:
  "acc (xs @ ys) = acc xs \<oplus> acc ys"
  by (rule acc_append)

(* 인접 swap *)
lemma acc_swap_consecutive:
  "acc (x # y # rest) = acc (y # x # rest)"
proof -
  have "acc (x # y # rest) = x \<oplus> y \<oplus> acc rest"
    by (simp add: bxor_assoc)
  also have "... = y \<oplus> x \<oplus> acc rest"
    by (simp add: bxor_commute)
  finally show ?thesis by (simp add: bxor_assoc)
qed

text \<open>
  본 theory에서 증명되지 않은 *부수* 성질:
  - 전체 list permutation invariance — append 분해로부터 유도되지만 별도 증명 필요.
  - 본 Y2의 *핵심* 의무는 left/right subtree 분리이며 acc_append로 충족.

  Tree 누산의 ⊕_{j ∈ left ∪ right} f(j) = ⊕_{j ∈ left} f(j) ⊕ ⊕_{j ∈ right} f(j) 는
  `acc_append`의 직접 적용.
\<close>

end
