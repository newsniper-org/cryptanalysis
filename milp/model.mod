/*
  YSC4-p 워드-수준 차분 트레일 MILP 모델 (GNU MathProg).
  Solver: glpsol --math model.mod
*/

param R, default 16;        /* 라운드 수 */
set W := 0..15;
set ROUNDS := 0..R;        /* 0..R 포함 (R+1개 상태) */

/* π 워드 순열: P[i] = (5i+7) mod 16 */
param P{i in W} :=
  if i = 0 then 7
  else if i = 1 then 12
  else if i = 2 then 1
  else if i = 3 then 6
  else if i = 4 then 11
  else if i = 5 then 0
  else if i = 6 then 5
  else if i = 7 then 10
  else if i = 8 then 15
  else if i = 9 then 4
  else if i = 10 then 9
  else if i = 11 then 14
  else if i = 12 then 3
  else if i = 13 then 8
  else if i = 14 then 13
  else 2;

/* 변수: 워드 활성 인디케이터 */
var x{r in ROUNDS, i in W}, binary;     /* 라운드 r 시작 시 워드 i 활성 */
var T{r in ROUNDS}, binary;             /* T^r 활성 (broadcast 차분) */
var y{r in ROUNDS, i in W}, binary;     /* broadcast 직후 워드 i 활성 */

/* T^r = parity of sum_i x^r_i
   (각 워드별 단일 비트 활성을 가정한 정확한 모델).
*/
var q{r in ROUNDS}, integer, >= 0;
s.t. T_parity{r in ROUNDS}: sum{i in W} x[r,i] = 2 * q[r] + T[r];

/* Broadcast 후 y_i 활성 모델링:
   - y = 0 if x = T = 0 (둘 다 비활성)
   - y = 1 if (x=1, T=0) or (x=0, T=1)  (배타적 활성)
   - y ∈ {0, 1} if x = T = 1  (attacker가 δ = T 식 cancellation 선택 가능)
*/
s.t. y_upper{r in ROUNDS, i in W}: y[r,i] <= x[r,i] + T[r];
s.t. y_lower_x{r in ROUNDS, i in W}: y[r,i] >= x[r,i] - T[r];
s.t. y_lower_T{r in ROUNDS, i in W}: y[r,i] >= T[r] - x[r,i];

/* σ-층은 활성 보존 — y와 동일 (별도 변수 불필요) */

/* π 적용: x^{r+1}_i = y^r_{P[i]} */
s.t. pi_transition{r in 0..R-1, i in W}: x[r+1, i] = y[r, P[i]];

/* 초기 조건: 최소 한 워드 활성 (non-trivial trail) */
s.t. nonzero_input: sum{i in W} x[0, i] >= 1;

/* 목적: 전체 trail의 활성 워드 수 최소화 */
minimize total_active: sum{r in ROUNDS, i in W} x[r, i];

solve;

printf "===== TRAIL RESULT =====\n";
printf "Rounds: %d\n", R;
printf "Total active words: %d\n", total_active;
printf "Per-round active counts:\n";
for {r in ROUNDS} {
  printf "  r=%d: count=%d  T=%d\n", r, sum{i in W} x[r,i], T[r];
}
printf "Per-round active word indices (where x[r,i]=1):\n";
for {r in ROUNDS, i in W: x[r,i] > 0.5} {
  printf "  r=%d, i=%d\n", r, i;
}

end;
