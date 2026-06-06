(*
  Y4_MaskUniqueness.thy
  마스크 유일성: distinct (level, pos, idx) ⇒ distinct mask
*)

theory Y4_MaskUniqueness
  imports Y1_TreeEncoding
begin

(* 추상화된 mask derivation locale *)
locale mask_derivation =
  fixes P_y :: "encoded \<Rightarrow> 'a"
    and IV_xor :: "encoded \<Rightarrow> encoded"
  assumes P_y_inj: "inj P_y"
      and IV_xor_inj: "inj IV_xor"
begin

definition mask :: "level_tag \<Rightarrow> nat \<Rightarrow> nat \<Rightarrow> 'a" where
  "mask lt pos idx = P_y (IV_xor (encode lt pos idx))"

(* Y4 main — mask는 (lt, pos, idx)에 대해 단사 *)
theorem Y4_mask_inj:
  assumes "mask lt1 pos1 idx1 = mask lt2 pos2 idx2"
  shows "lt1 = lt2 \<and> pos1 = pos2 \<and> idx1 = idx2"
proof -
  from assms have "P_y (IV_xor (encode lt1 pos1 idx1)) = P_y (IV_xor (encode lt2 pos2 idx2))"
    unfolding mask_def by simp
  hence "IV_xor (encode lt1 pos1 idx1) = IV_xor (encode lt2 pos2 idx2)"
    using P_y_inj injD by metis
  hence "encode lt1 pos1 idx1 = encode lt2 pos2 idx2"
    using IV_xor_inj injD by metis
  thus ?thesis using Y1_encode_injective by blast
qed

end (* locale *)

(* 메모: 실제 구현 (YSC4-p 8-라운드)은 bijection이고, IV-XOR도 자명히 bijection.
   따라서 본 locale의 가정이 만족되어 Y4_mask_inj가 성립. *)

end
