#!/usr/bin/env python3
"""
F 차분 weight = rank(L_δ) 정확 계산 (affine 구조 — bitlevel-analysis.md §1).

F(s) = s ⊕ (s⋘a ∧ s⋘b) ⊕ (s⋘c ∧ s⋘d).
F(s)⊕F(s⊕δ) = const(δ) ⊕ L_δ(s),  L_δ(s) = (s⋘a ∧ δ⋘b) ⊕ (δ⋘a ∧ s⋘b)
                                          ⊕ (s⋘c ∧ δ⋘d) ⊕ (δ⋘c ∧ s⋘d)
weight(δ) = rank_GF2(L_δ),   DP_F(δ→·) = 2^(-weight(δ)).
"""
import itertools, random
random.seed(12345)

def rotl(x, k, n):
    k %= n
    return ((x << k) | (x >> (n - k))) & ((1 << n) - 1)

def gf2_rank(cols, n):
    rws = list(cols); rank = 0
    for bitpos in range(n - 1, -1, -1):
        bm = 1 << bitpos
        piv = next((i for i in range(len(rws)) if rws[i] & bm), None)
        if piv is None:
            continue
        rank += 1
        pr = rws[piv]
        for i in range(len(rws)):
            if i != piv and (rws[i] & bm):
                rws[i] ^= pr
        rws[piv] = 0
    return rank

def Ldelta_cols(delta, rot, n):
    a, b, c, d = rot
    ra, rb, rc, rd = (rotl(delta, k, n) for k in (a, b, c, d))
    cols = []
    for j in range(n):
        e = 1 << j
        cols.append((rotl(e, a, n) & rb) ^ (ra & rotl(e, b, n))
                    ^ (rotl(e, c, n) & rd) ^ (rc & rotl(e, d, n)))
    return cols

def weight(delta, rot, n):
    return gf2_rank(Ldelta_cols(delta, rot, n), n)

def analyze(name, n, rot, nrand=200000):
    mn = 10**9; arg = None
    for hw in (1, 2, 3):
        for bits in itertools.combinations(range(n), hw):
            d = 0
            for bb in bits:
                d |= 1 << bb
            w = weight(d, rot, n)
            if 0 < w < mn:
                mn, arg = w, (hw, d)
    for _ in range(nrand):
        d = random.getrandbits(n)
        if d:
            w = weight(d, rot, n)
            if 0 < w < mn:
                mn, arg = w, ("rand", d)
    hw1 = [weight(1 << j, rot, n) for j in range(n)]
    print(f"== {name} (n={n}, rot={rot}) ==")
    print(f"  HW1 weight: min={min(hw1)} max={max(hw1)}")
    print(f"  min nonzero weight (HW<=3 전수 + {nrand} 랜덤) = {mn}  "
          f"=> 활성 라운드당 max DP = 2^-{mn}  (argmin type={arg[0]})")
    return mn

if __name__ == "__main__":
    analyze("ypsilenti F", 32, (7, 17, 3, 13))
    analyze("yhash/ysc4 F", 64, (13, 37, 5, 23))
