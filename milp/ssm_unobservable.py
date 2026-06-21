#!/usr/bin/env python3
"""
NOVEL ANGLE — control-theoretic state-space model of the GF(2)-linear backbone.

yttrium round (Delta-domain, when F is *inactive* i.e. dt=0):
    x'_i = ROTL8(x_i)                      (framing)
    S    = sum eps_i x'_i                   (zero-sum reduction; the ONLY thing F sees)
    [dt=0 inactive branch]
    y_i  = ROTR9(x'_i + 0) = ROTR9(x'_i)    (ARX add of t=0)
    y_i  = alpha^{k_i}(y_i)                 (sigma; GF(2)-linear)
    new  = pi(y)                            (word permutation)

So over GF(2), the *linear backbone* is
    A = pi o sigma(alpha^k) o ROTR9 o ROTL8          (256x256 over GF(2))
and the nonlinearity F observes the state through the *output map*
    C = [ S = sum eps_i ROTL8(x_i) ]                  (32 x 256 over GF(2);
         eps signs vanish mod 2 -> C row r = XOR_i ROTL8(x_i) bit).

CONTROL-THEORY OBJECT:  the *unobservable subspace*
    Q = largest A-invariant subspace contained in ker(C)
      = intersection_{j>=0} ker(C A^j).
A nonzero delta in Q propagates with dt=0 EVERY round => a probability-1
(GF(2)-linear) inactive characteristic of UNBOUNDED depth -> structural break
of the round backbone. dim(Q)=0 means the all-8 sigma fully closes the hole.

We ALSO compute the per-round inactive dimension dim(intersection_{j<R} ker(C A^j))
to recover the R* (depth at which the GF(2)-inactive subspace dies) and compare to
the prior R*=9 claim. And the OBSERVABILITY rank profile rank([C;CA;...;CA^{R-1}]).

This is the headline SSM object the prior docs gestured at but did NOT compute as
the formal unobservable subspace / observability staircase.

Honesty note: this is the GF(2) linearization. Carries in the additive reduction can
KILL a GF(2)-inactive delta (prob<1). We compute the GF(2) object first (exact, fast),
then in ssm_additive_check.py test whether any survivor is *additively* prob-1 inactive.
"""

import numpy as np

N_BITS = 32
W = 8
STATE = N_BITS * W  # 256
RED = 0x400007
P_PI = [7, 4, 1, 6, 3, 0, 5, 2]
SIG_K = [1, 2, 3, 4, 5, 6, 7, 9]
ROT_A = 8   # ROTL
ROT_B = 9   # ROTR
EPS = [1, -1, 1, -1, 1, -1, 1, -1]  # signs vanish over GF(2)

MASK = (1 << N_BITS) - 1


def rotl(x, k):
    k %= N_BITS
    return x & MASK if k == 0 else ((x << k) | (x >> (N_BITS - k))) & MASK


def rotr(x, k):
    return rotl(x, (N_BITS - (k % N_BITS)) % N_BITS)


def alpha(v):
    top = (v >> (N_BITS - 1)) & 1
    return (((v << 1) & MASK) ^ (RED if top else 0)) & MASK


def alpha_pow(v, k):
    for _ in range(k):
        v = alpha(v)
    return v


# ---- bit-matrix helpers over GF(2), columns as Python ints (bit i = coeff of basis e_i) ----
# We represent a 256-bit vector as a Python int (bit j set => component j is 1).
# A linear map M is a list of 256 ints: M[j] = image of basis vector e_j (as 256-bit int).

def apply_map(Mcols, v):
    """v is int; Mcols[j] is image of e_j. Output = XOR over set bits j of Mcols[j]."""
    out = 0
    j = 0
    vv = v
    while vv:
        if vv & 1:
            out ^= Mcols[j]
        vv >>= 1
        j += 1
    return out


def word_bit(w_idx, b_idx):
    return w_idx * N_BITS + b_idx


def build_linear_columns():
    """Build A (256 cols, each a 256-bit int) for the inactive (dt=0) backbone,
       and C rows (32 functionals -> we store C as 32 ints over 256 input bits)."""
    # For each input basis bit (word wi, bit bi) compute image under one round backbone.
    Acols = []
    for wi in range(W):
        for bi in range(N_BITS):
            # input state: only this bit set
            words = [0] * W
            words[wi] = 1 << bi
            # framing ROTL8
            xp = [rotl(words[i], ROT_A) for i in range(W)]
            # dt=0 branch: y_i = ROTR9(xp_i); sigma; pi
            y = [rotr(xp[i], ROT_B) for i in range(W)]
            y = [alpha_pow(y[i], SIG_K[i]) for i in range(W)]
            new = [y[P_PI[i]] for i in range(W)]
            # pack to 256-bit int
            col = 0
            for i in range(W):
                col |= new[i] << (i * N_BITS)
            Acols.append(col)
    # C: row r = bit r of S = XOR_i ROTL8(x_i)  (over GF2, eps signs vanish)
    # S bit r as a linear functional on the 256 input bits:
    Crows = []
    for r in range(N_BITS):
        row = 0
        for i in range(W):
            # bit r of ROTL8(x_i) = bit (r-8 mod 32) of x_i
            src = (r - ROT_A) % N_BITS
            row |= 1 << word_bit(i, src)
        Crows.append(row)
    return Acols, Crows


def funcs_of_CAj(Acols, Crows, j):
    """Return the 32 linear functionals  C A^j  as ints over 256 input bits.
       C A^j applied to x = C(A^j x). As functionals: (C A^j)_r (x) = <Crow_r, A^j x>.
       We compute A^j as columns then compose."""
    # compute A^j columns
    cols = list(range(STATE))  # identity columns
    Ajcols = [1 << j2 for j2 in range(STATE)]  # identity
    for _ in range(j):
        Ajcols = [apply_map(Acols, c) for c in Ajcols]
    # functional (C A^j)_r = row vector: coefficient on input bit m =
    #   <Crow_r, A^j e_m> = parity of (Crow_r AND Ajcols[m])
    out = []
    for r in range(N_BITS):
        fr = 0
        cr = Crows[r]
        for m in range(STATE):
            if bin(cr & Ajcols[m]).count("1") & 1:
                fr |= 1 << m
        out.append(fr)
    return out


def gf2_rank(rows):
    basis = []
    for v in rows:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
            basis.sort(reverse=True)
    return len(basis), basis


def observability_profile(Acols, Crows, Rmax):
    """rank of [C; CA; ...; CA^{R-1}] and dim of inactive subspace = 256 - rank."""
    all_funcs = []
    Ajcols = [1 << j2 for j2 in range(STATE)]  # A^0 = I
    print(f"{'R':>3} {'obs_rank':>9} {'dim_inactive':>13}  note")
    Rstar = None
    for R in range(1, Rmax + 1):
        # functionals C A^{R-1}
        for r in range(N_BITS):
            cr = Crows[r]
            fr = 0
            for m in range(STATE):
                if bin(cr & Ajcols[m]).count("1") & 1:
                    fr |= 1 << m
            all_funcs.append(fr)
        rank, _ = gf2_rank(all_funcs)
        dim_inact = STATE - rank
        tag = ""
        if dim_inact == 0 and Rstar is None:
            Rstar = R
            tag = " <- R* (GF(2)-inactive subspace dies)"
        print(f"{R:>3} {rank:>9} {dim_inact:>13}{tag}")
        # advance A^{R}
        Ajcols = [apply_map(Acols, c) for c in Ajcols]
    return Rstar, all_funcs


def main():
    print("=== SSM control-theoretic analysis of yttrium GF(2)-linear backbone ===\n")
    Acols, Crows = build_linear_columns()
    print(f"State dim = {STATE}, observation (F input) dim = {N_BITS}")
    rC, _ = gf2_rank(Crows)
    print(f"rank(C) = {rC}  (F sees a {rC}-dim projection of the 256-bit state)\n")

    print("Observability staircase  rank([C;CA;...;CA^(R-1)])  and inactive dim:")
    Rstar, _ = observability_profile(Acols, Crows, 16)
    print(f"\n=> GF(2)-inactive (unobservable-after-R) dies at R* = {Rstar}")
    print("   (unobservable subspace Q = limit = inactive dim at R*; here", end=" ")
    print("dim(Q)=0 means all-8 sigma fully closes the linear hole.)")


if __name__ == "__main__":
    main()
