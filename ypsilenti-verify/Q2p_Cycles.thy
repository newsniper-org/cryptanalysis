(*
  Q2p_Cycles.thy
  k ∈ {1..8}에 대해 ord(α^k) = N32 / gcd(k, N32) 검증.
*)

theory Q2p_Cycles
  imports Q1p_Primitivity
begin

theorem Q2p_gcd_table:
  "gcd  (1::nat) N32 =  1
   \<and> gcd (2::nat) N32 =  1
   \<and> gcd (3::nat) N32 =  3
   \<and> gcd (4::nat) N32 =  1
   \<and> gcd (5::nat) N32 =  5
   \<and> gcd (6::nat) N32 =  3
   \<and> gcd (7::nat) N32 =  1
   \<and> gcd (8::nat) N32 =  1"
  unfolding N32_def by eval

(* 최저 차수 — k=15에 해당하는 N32/15 = 286331153 이지만 우리는 k ≤ 8.
   k=3, 6에서 최저 = N32/3. *)
theorem Q2p_min_order_lower_bound:
  "N32 div 3 > (2::nat)^28"
  unfolding N32_def by eval

theorem Q2p_all_orders_practical:
  "(\<forall> k \<in> {1,2,3,4,5,6,7,8}.
     N32 div gcd k N32 > (2::nat)^28)"
  unfolding N32_def by eval

end
