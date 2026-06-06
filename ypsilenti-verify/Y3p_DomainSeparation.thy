(*
  Y3p_DomainSeparation.thy
  ypsilenti maskMid: LEAF/INTERNAL/ROOT 도메인 분리.
*)

theory Y3p_DomainSeparation
  imports Y1p_TreeEncoding
begin

definition T_MAX :: nat where "T_MAX = 8"

definition maskMid :: "level_tag \<Rightarrow> nat \<Rightarrow> encoded" where
  "maskMid lt pos = encode lt pos T_MAX"

theorem Y3p_leaf_vs_internal:
  "maskMid LEAF pos1 \<noteq> maskMid (INTERNAL l) pos2"
  unfolding maskMid_def encode_def by simp

theorem Y3p_leaf_vs_root:
  "maskMid LEAF pos1 \<noteq> maskMid ROOT pos2"
  unfolding maskMid_def encode_def by simp

theorem Y3p_internal_vs_root:
  "maskMid (INTERNAL l) pos1 \<noteq> maskMid ROOT pos2"
  unfolding maskMid_def encode_def by simp

end
