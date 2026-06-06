(*
  Y4p_MaskUniqueness.thy
  distinct (level, pos, idx) ⇒ distinct mask.
*)

theory Y4p_MaskUniqueness
  imports Y1p_TreeEncoding
begin

locale mask_derivation =
  fixes P_y :: "encoded \<Rightarrow> 'a"
    and IV_xor :: "encoded \<Rightarrow> encoded"
  assumes P_y_inj: "inj P_y"
      and IV_xor_inj: "inj IV_xor"
begin

definition mask :: "level_tag \<Rightarrow> nat \<Rightarrow> nat \<Rightarrow> 'a" where
  "mask lt pos idx = P_y (IV_xor (encode lt pos idx))"

theorem Y4p_mask_inj:
  assumes "mask lt1 pos1 idx1 = mask lt2 pos2 idx2"
  shows "lt1 = lt2 \<and> pos1 = pos2 \<and> idx1 = idx2"
proof -
  from assms have "P_y (IV_xor (encode lt1 pos1 idx1)) = P_y (IV_xor (encode lt2 pos2 idx2))"
    unfolding mask_def by simp
  hence "IV_xor (encode lt1 pos1 idx1) = IV_xor (encode lt2 pos2 idx2)"
    using P_y_inj injD by metis
  hence "encode lt1 pos1 idx1 = encode lt2 pos2 idx2"
    using IV_xor_inj injD by metis
  thus ?thesis using Y1p_encode_injective by blast
qed

end

end
