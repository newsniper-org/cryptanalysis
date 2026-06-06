(*
  Y1_TreeEncoding.thy
  YHash의 tree-positional 인코딩이 단사임을 형식 증명.

  핵심 통찰: 추상 단계에서 encode를 sum-type 생성자로 정의하면 단사성은 datatype에서 자명.
  구체 byte layout (16-byte little-endian 등)이 추상 encode의 단사성을 *손실하지 않으면*
  실제 구현도 단사. 후자는 (필요시) 별도 theory에서 증명.
*)

theory Y1_TreeEncoding
  imports Main
begin

(* Level 태그. INTERNAL n carries level l. *)
datatype level_tag =
    LEAF
  | INTERNAL nat
  | ROOT

(* 추상 인코딩 결과 — 직접 (level, pos, idx) 정보를 sum-type으로 보존.
   실제 구현은 이 추상값과 같은 정보 내용을 갖는 byte sequence를 사용. *)
datatype encoded =
    ENC_LEAF nat nat       (* pos, idx *)
  | ENC_INTERNAL nat nat nat (* level, pos, idx *)
  | ENC_ROOT nat nat       (* pos, idx *)

definition encode :: "level_tag \<Rightarrow> nat \<Rightarrow> nat \<Rightarrow> encoded" where
  "encode lt pos idx = (case lt of
       LEAF \<Rightarrow> ENC_LEAF pos idx
     | INTERNAL l \<Rightarrow> ENC_INTERNAL l pos idx
     | ROOT \<Rightarrow> ENC_ROOT pos idx)"

(* Y1 main — datatype constructors는 distinct + injective *)
theorem Y1_encode_injective:
  assumes "encode lt1 pos1 idx1 = encode lt2 pos2 idx2"
  shows "lt1 = lt2 \<and> pos1 = pos2 \<and> idx1 = idx2"
  using assms
  by (cases lt1; cases lt2; simp add: encode_def)

(* inj_on 형태 — set-based formulation *)
theorem Y1_encode_inj:
  "inj (\<lambda>(lt, pos, idx). encode lt pos idx)"
  apply (rule injI)
  apply clarsimp
  using Y1_encode_injective by blast

end
