(*
  Q2_Cycles.thy
  Given Q1, alpha is primitive with order N = 2^64 - 1.
  ord(alpha^k) = N / gcd(k, N).  Tabulate gcd for k in {1..16}.
*)

theory Q2_Cycles
  imports Q1_Primitivity
begin

theorem Q2_gcd_table:
  "gcd  (1::nat) N =  1
   \<and> gcd (2::nat) N =  1
   \<and> gcd (3::nat) N =  3
   \<and> gcd (4::nat) N =  1
   \<and> gcd (5::nat) N =  5
   \<and> gcd (6::nat) N =  3
   \<and> gcd (7::nat) N =  1
   \<and> gcd (8::nat) N =  1
   \<and> gcd (9::nat) N =  3
   \<and> gcd (10::nat) N =  5
   \<and> gcd (11::nat) N =  1
   \<and> gcd (12::nat) N =  3
   \<and> gcd (13::nat) N =  1
   \<and> gcd (14::nat) N =  1
   \<and> gcd (15::nat) N = 15
   \<and> gcd (16::nat) N =  1"
  unfolding N_def by eval

theorem Q2_ysc4_min_order_lower_bound:
  "N div 15 > (2::nat)^60"
  unfolding N_def by eval

theorem Q2_all_orders_practical:
  "(\<forall> k \<in> {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}.
     N div gcd k N > (2::nat)^60)"
  unfolding N_def by eval

end
