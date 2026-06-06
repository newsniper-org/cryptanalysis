(*
  Y1p_TreeEncoding.thy
  ypsilenti의 tree-positional 인코딩이 단사임을 형식 증명.
  YHash의 Y1과 같은 구조 (sum-type 추상화).
*)

theory Y1p_TreeEncoding
  imports Main
begin

datatype level_tag =
    LEAF
  | INTERNAL nat
  | ROOT

datatype encoded =
    ENC_LEAF nat nat
  | ENC_INTERNAL nat nat nat
  | ENC_ROOT nat nat

definition encode :: "level_tag \<Rightarrow> nat \<Rightarrow> nat \<Rightarrow> encoded" where
  "encode lt pos idx = (case lt of
       LEAF \<Rightarrow> ENC_LEAF pos idx
     | INTERNAL l \<Rightarrow> ENC_INTERNAL l pos idx
     | ROOT \<Rightarrow> ENC_ROOT pos idx)"

theorem Y1p_encode_injective:
  assumes "encode lt1 pos1 idx1 = encode lt2 pos2 idx2"
  shows "lt1 = lt2 \<and> pos1 = pos2 \<and> idx1 = idx2"
  using assms
  by (cases lt1; cases lt2; simp add: encode_def)

theorem Y1p_encode_inj:
  "inj (\<lambda>(lt, pos, idx). encode lt pos idx)"
  apply (rule injI)
  apply clarsimp
  using Y1p_encode_injective by blast

end
