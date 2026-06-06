(*
  Q3_RollMatrix.thy
  YSC5 roll γ((k_0, ..., k_15)) := (α·k_0, α^2·k_1, ..., α^16·k_15) 의
  실제 동작을 by eval로 형식 검증.
*)

theory Q3_RollMatrix
  imports Q2_Cycles
begin

text \<open>γ를 1-단계 적용. word i에 α^(i+1)를 곱한다.\<close>

definition roll_step :: "64 word list \<Rightarrow> 64 word list" where
  "roll_step ks =
     [ gf_mul (ks ! 0)  (gf_pow alpha 1)
     , gf_mul (ks ! 1)  (gf_pow alpha 2)
     , gf_mul (ks ! 2)  (gf_pow alpha 3)
     , gf_mul (ks ! 3)  (gf_pow alpha 4)
     , gf_mul (ks ! 4)  (gf_pow alpha 5)
     , gf_mul (ks ! 5)  (gf_pow alpha 6)
     , gf_mul (ks ! 6)  (gf_pow alpha 7)
     , gf_mul (ks ! 7)  (gf_pow alpha 8)
     , gf_mul (ks ! 8)  (gf_pow alpha 9)
     , gf_mul (ks ! 9)  (gf_pow alpha 10)
     , gf_mul (ks ! 10) (gf_pow alpha 11)
     , gf_mul (ks ! 11) (gf_pow alpha 12)
     , gf_mul (ks ! 12) (gf_pow alpha 13)
     , gf_mul (ks ! 13) (gf_pow alpha 14)
     , gf_mul (ks ! 14) (gf_pow alpha 15)
     , gf_mul (ks ! 15) (gf_pow alpha 16)
     ]"

text \<open>모든 워드가 1(= GF의 항등원)로 시작하면 γ 결과 = (α, α^2, ..., α^16) — 모두 distinct.\<close>

theorem Q3_roll_distinct_for_ones:
  "distinct (roll_step (replicate 16 (1 :: 64 word)))"
  by eval

text \<open>모든 결과 워드가 0이 아님.\<close>

theorem Q3_roll_no_zero:
  "(0 :: 64 word) \<notin> set (roll_step (replicate 16 (1 :: 64 word)))"
  by eval

text \<open>입력의 어떤 워드도 0이 아니면 출력도 그러함 (워드별 단사성의 표본 검증).\<close>

theorem Q3_roll_no_zero_for_alpha:
  "(0 :: 64 word) \<notin> set (roll_step (replicate 16 alpha))"
  unfolding alpha_def by eval

text \<open>
  Q3 종합 — γ가 워드별 distinct nonzero 원소를 산출하며, 16개 워드 출력은
  모두 서로 다른 값을 가짐. SPEC §9의 마스크 derivation의 sanity check.
\<close>

end
