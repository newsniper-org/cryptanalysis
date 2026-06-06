(*
  Y3_DomainSeparation.thy
  maskMid의 도메인 분리: LEAF/INTERNAL/ROOT 사이 어떤 충돌도 일어나지 않음.
  Sakura-style framing의 핵심.
*)

theory Y3_DomainSeparation
  imports Y1_TreeEncoding
begin

definition T_MAX :: nat where "T_MAX = 8"

definition maskMid :: "level_tag \<Rightarrow> nat \<Rightarrow> encoded" where
  "maskMid lt pos = encode lt pos T_MAX"

theorem Y3_leaf_vs_internal:
  "maskMid LEAF pos1 \<noteq> maskMid (INTERNAL l) pos2"
  unfolding maskMid_def encode_def by simp

theorem Y3_leaf_vs_root:
  "maskMid LEAF pos1 \<noteq> maskMid ROOT pos2"
  unfolding maskMid_def encode_def by simp

theorem Y3_internal_vs_root:
  "maskMid (INTERNAL l) pos1 \<noteq> maskMid ROOT pos2"
  unfolding maskMid_def encode_def by simp

(* 종합 도메인 분리: distinct level tag → distinct maskMid *)
theorem Y3_domain_separation:
  assumes "lt1 \<noteq> lt2"
  shows "maskMid lt1 pos1 \<noteq> maskMid lt2 pos2 \<or>
         (\<exists>l1 l2. lt1 = INTERNAL l1 \<and> lt2 = INTERNAL l2 \<and> l1 \<noteq> l2)"
proof (cases lt1)
  case LEAF
  with assms show ?thesis
    by (cases lt2; simp add: maskMid_def encode_def)
next
  case (INTERNAL l1)
  with assms show ?thesis
  proof (cases lt2)
    case LEAF then show ?thesis using `lt1 = INTERNAL l1`
      by (simp add: maskMid_def encode_def)
  next
    case (INTERNAL l2)
    with assms `lt1 = INTERNAL l1` have "l1 \<noteq> l2" by simp
    then show ?thesis using `lt1 = INTERNAL l1` `lt2 = INTERNAL l2` by blast
  next
    case ROOT then show ?thesis using `lt1 = INTERNAL l1`
      by (simp add: maskMid_def encode_def)
  qed
next
  case ROOT
  with assms show ?thesis
    by (cases lt2; simp add: maskMid_def encode_def)
qed

end
