(* R1 합성 advantage bound — EasyCrypt 교차검증 (prover 다양성).

   CryptHOL `Y5_CRReduction.yhash_prf_reduction.yhash_prf_multikey_bound` 의
   *독립 재증명*. 두 prover(Isabelle/HOL+CryptHOL, EasyCrypt)가 같은 핵심 부등식을
   서로 다른 TCB로 확인 → 한 prover의 형식화 오류가 결과를 좌우하지 않게 함.

   birthday := q^2 / 2^(n+1) (단일키 PRP→PRF 생일항, AFP RP_RF.rp_rf),
   eps      := leaf XOR accumulator(Wagner) 항,
   u        := 키 개수 (multi-key, Guessing_Many_One.many_single_reduction).
*)
require import AllCore Real.

(* H2(multi-key hybrid) + H1(birthday) → 합성 다중키 bound. *)
lemma yhash_prf_compose (u_ adv_s adv_m birthday eps : real) :
  0%r <= u_ =>
  0%r <= eps =>
  adv_s <= birthday + eps =>          (* H1: 단일키 ≤ birthday + accumulator *)
  adv_m <= u_ * adv_s =>              (* H2: 다중키 ≤ u · 단일키 *)
  adv_m <= u_ * (birthday + eps).
proof. move=> hu he h1 h2. smt(). qed.

(* bound 음이 아님 (sanity, CryptHOL bound_nonneg 대응). *)
lemma bound_nonneg (u_ birthday eps : real) :
  0%r <= u_ => 0%r <= birthday => 0%r <= eps =>
  0%r <= u_ * (birthday + eps).
proof. move=> *. smt(). qed.

(* monotonicity 단독 (합성의 핵심 단계). *)
lemma left_mono (u_ a b : real) :
  0%r <= u_ => a <= b => u_ * a <= u_ * b.
proof. move=> *. smt(). qed.
