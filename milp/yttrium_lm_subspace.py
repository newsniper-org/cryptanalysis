#!/usr/bin/env python3
"""
yttrium-LM (권고안) inactive-subspace 정확 경계 — GF(2) 선형대수.

권고 라운드 = 영합(zero-sum) Lai-Massey + 결합기 framing + **all-8 σ (GF α^k)**:
  (ι)        state[r mod 8] ⊕= RC[r]
  reduction  xp_i = ROTL_a(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), ε=[+,-,+,-,+,-,+,-], Σε=0
  combiner   t = F(S);  y_i = ROTR_b(xp_i ⊞ t)          (a,b)=(8,9)
  σ          y_i ← α^{k_i}·y_i  ∀i,  k=[1,2,3,5,7,11,13,17]   (GF(2^32), red 0x400007)
  π          new_i = y_{P[i]}

본 도구는 TWO 측정을 모두 낸다(정직성: 두 척도가 갈린다 — 둘 다 보고):

(A) 확률-1 MSB-비활성 부분공간 (additive 차분 모델, 정확).
    공통 t의 가산은 GF(2)-선형이 아니므로 ΔS=0(=F 비활성)이어도 +t carry가 Δ를 섞는다.
    확률 1로 가산을 항등 통과하는 비트는 MSB 뿐(add=xor at MSB). 따라서 prob-1 비활성 =
       { v≠0 : 각 라운드 Lin^r(v)의 비-MSB=0  AND  MSB 부호합=0 },  Lin=π∘σ∘ROTR_b∘ROTL_a.
    측정상 권고안 R*=2.  *주의(실측 전 = 예상)*: 이 R*는 σ 커버리지와 무관(framing이 주역).

(B) GF(2)-선형 inactive 부분공간 (inactive_subspace.py 양식, ⊕-sum proxy, 정확 LA).
    이 척도에서 σ-GLM baseline은 R*=8, 권고안(all-8 σ)은 R*≈9 로 *낮아지지 않는다*.
    이는 GF(2)-선형 모델이 가산 reduction의 carry를 못 보아 과대평가하는 artifact이며,
    그 inactive 차분의 실제 가산 통과확률은 ≈0.5 (prob-1 아님). 정직하게 둘 다 출력한다.

(C) 진짜 차분 저항(고확률 truncated 차분)은 GPU best-DP(yttrium_lm_diff.cu)가 측정한다 —
    그쪽에서 σ 커버리지가 결정적(부분 σ{0,4}는 MSB-쌍이 R≈3까지 고DP 생존, all-8 σ는 R=2서 붕괴).
    이 파일은 prob-1/GF(2)-선형 *정확* 경계만 담당.

실행: python3 yttrium_lm_subspace.py   (GPU 불필요)
정직: (A)는 prob-1(MSB) *정확* 경계. (B)는 GF(2)-선형 *정확* 경계. 절대 trail 경계 아님.
"""


def make_alpha(n, red):
    M = (1 << n) - 1

    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))
    return alpha


def gf2_rank(cols):
    basis = []
    for v in cols:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
            basis.sort(reverse=True)
    return len(basis)


def _backbone(n, w, red, sigma, P, a, b, framing=True):
    """선형 backbone Lin = π∘σ∘ROTR_b∘ROTL_a (broadcast t는 차분 0 가정)."""
    M = (1 << n) - 1
    alpha = make_alpha(n, red)

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def words(state):
        return [(state >> (i * n)) & M for i in range(w)]

    def pack(ws):
        s = 0
        for i, x in enumerate(ws):
            s |= (x & M) << (i * n)
        return s

    def Lin(state):
        ws = words(state)
        if framing:
            ws = [rotl(x, a) for x in ws]
            ws = [rotr(x, b) for x in ws]
        for (lane, k) in sigma:
            ws[lane] = alfp(ws[lane], k)
        return pack([ws[P[i]] for i in range(w)])
    return Lin, words, M


# ---------- (A) prob-1 MSB-inactive 부분공간 (additive 모델) ----------
def inactive_dim_msb(n, w, red, sigma, P, a, b, R, framing=True):
    Lin, words, M = _backbone(n, w, red, sigma, P, a, b, framing)
    N = n * w
    cols = []
    for k in range(N):
        cur = 1 << k
        col = 0
        bp = 0
        for r in range(R):
            ws = words(cur)
            for x in ws:                       # 비-MSB 비트 = 0 (확률-1 통과는 MSB만)
                col |= (x & (M ^ (1 << (n - 1)))) << bp
                bp += n
            mx = 0                             # MSB 부호합(=XOR of MSB) = 0
            for x in ws:
                mx ^= (x >> (n - 1)) & 1
            col |= mx << bp
            bp += 1
            cur = Lin(cur)
        cols.append(col)
    return N - gf2_rank(cols)


# ---------- (B) GF(2)-선형 inactive 부분공간 (⊕-sum proxy) ----------
def inactive_dim_gf2(n, w, red, sigma, P, a, b, R, framing=True):
    Lin, words, M = _backbone(n, w, red, sigma, P, a, b, framing)
    N = n * w

    def xorsum(state):
        r = 0
        for x in words(state):
            r ^= x
        return r
    cols = []
    for k in range(N):
        cur = 1 << k
        col = 0
        for r in range(R):
            col |= xorsum(cur) << (r * n)
            cur = Lin(cur)
        cols.append(col)
    return N - gf2_rank(cols)


def sweep(name, fn, n, w, red, sigma, P, a, b, Rmax, framing=True):
    print(f"== {name} (state {n*w} bit = {w}x{n})  a={a} b={b} framing={framing} ==")
    Rstar = None
    for R in range(1, Rmax + 1):
        d = fn(n, w, red, sigma, P, a, b, R, framing)
        tag = ""
        if d == 0 and Rstar is None:
            Rstar = R
            tag = "  <- R*"
        print(f"  R={R:2d}: dim(inactive) = {d:4d}{tag}")
        if d == 0:
            break
    print(f"  => R* = {Rstar}\n")
    return Rstar


if __name__ == "__main__":
    PI = [7, 4, 1, 6, 3, 0, 5, 2]
    red = 0x400007
    a, b = 8, 9
    SIG_ALL8 = [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7), (5, 11), (6, 13), (7, 17)]
    SIG_04 = [(0, 1), (4, 3)]
    SIG_EVEN4 = [(0, 1), (2, 2), (4, 3), (6, 5)]

    print("###### (A) 확률-1 MSB-비활성 부분공간 (additive 모델, 정확) ######\n")
    sweep("권고: all-8 σ k=1,2,3,5,7,11,13,17 (a,b)=(8,9)",
          inactive_dim_msb, 32, 8, red, SIG_ALL8, PI, a, b, 8)
    sweep("대조: even-4 σ{0,2,4,6}", inactive_dim_msb, 32, 8, red, SIG_EVEN4, PI, a, b, 8)
    sweep("대조: 부분 σ{0,4}", inactive_dim_msb, 32, 8, red, SIG_04, PI, a, b, 8)
    sweep("ablation: EMPTY σ (framing only) — framing이 prob-1 주역임을 노출",
          inactive_dim_msb, 32, 8, red, [], PI, a, b, 8)
    sweep("ablation: all-8 σ, framing OFF (a=b=0) — σ 단독 효과",
          inactive_dim_msb, 32, 8, red, SIG_ALL8, PI, 0, 0, 8, framing=False)

    print("###### (B) GF(2)-선형 inactive 부분공간 (⊕-sum proxy, 정확) ######")
    print("# 정직: 이 척도는 carry를 못 봐 과대평가. σ 커버리지가 R*를 낮추지 못함.\n")
    sweep("권고: all-8 σ (GF(2)-선형 척도)",
          inactive_dim_gf2, 32, 8, red, SIG_ALL8, PI, a, b, 12)
    sweep("baseline: σ{0,4} (GF(2)-선형 척도)",
          inactive_dim_gf2, 32, 8, red, SIG_04, PI, a, b, 12)

    print("###### n=64 (yhash-large 대응) prob-1 MSB-비활성 ######\n")
    sweep("권고형 n=64 all-8형 σ",
          inactive_dim_msb, 64, 16, 0x1B,
          [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7), (5, 11),
           (6, 13), (7, 17), (8, 19), (9, 23), (10, 29), (11, 31),
           (12, 37), (13, 41), (14, 43), (15, 47)],
          [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2], 8, 9, 8)
