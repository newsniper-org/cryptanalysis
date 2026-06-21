#!/usr/bin/env python3
"""
Extract the EXACT 1-dim GF(2)-inactive survivor at R=8 (the single direction the
backbone fails to observe after 8 rounds) and characterize it:
  - which state bits it touches (is it MSB-only? carry-free?),
  - whether it is additively prob-1 inactive (carry test),
  - its correlation as an 8-round prob-1/near linear relation.

Then probe the deeper question: the staircase rank=32R is *maximal* growth (no early
deficiency). We test if ANY choice of sigma powers / framing rotations would create a
real (additive prob-1) unobservable subspace -> attributes the strength to spec params.
"""
import numpy as np
from ssm_unobservable import (build_linear_columns, apply_map, gf2_rank,
                              STATE, N_BITS, W, rotl, rotr, alpha_pow, P_PI,
                              SIG_K, ROT_A, ROT_B, MASK, RED)

EPS = [1, -1, 1, -1, 1, -1, 1, -1]


def inactive_basis_after(Acols, Crows, R):
    """Basis of {v : C A^j v = 0 for j=0..R-1} = kernel of stacked functionals.
       We have functionals f (rows over input bits). Kernel = vectors orthogonal to all.
       Compute as right-kernel via building the functional matrix and Gaussian elim."""
    funcs = []
    Ajcols = [1 << j2 for j2 in range(STATE)]
    for j in range(R):
        for r in range(N_BITS):
            cr = Crows[r]
            fr = 0
            for m in range(STATE):
                if bin(cr & Ajcols[m]).count("1") & 1:
                    fr |= 1 << m
            funcs.append(fr)
        Ajcols = [apply_map(Acols, c) for c in Ajcols]
    # kernel of funcs (each func is a row, want v with <func,v>=0 all funcs)
    # Build augmented: reduce rows; kernel via standard method on the row space.
    # Represent each func row; do elimination tracking pivot columns; free cols -> kernel basis.
    rows = [f for f in funcs if f]
    # Gaussian elimination to RREF over GF(2)
    pivots = {}
    basis = []
    for v in rows:
        cur = v
        for p, bv in basis:
            if (cur >> p) & 1:
                cur ^= bv
        if cur:
            p = cur.bit_length() - 1
            basis.append((p, cur))
            basis.sort(key=lambda t: -t[0])
            pivots[p] = cur
    pivot_cols = set(pivots.keys())
    free_cols = [c for c in range(STATE) if c not in pivot_cols]
    kernel = []
    for fc in free_cols:
        v = 1 << fc
        # back-substitute: for each pivot, set pivot bit to cancel
        for p in sorted(pivot_cols):
            if (pivots[p] & v).bit_count() & 1:
                v ^= (1 << p)
        kernel.append(v)
    return kernel


def describe_vec(v):
    bits = [(b // N_BITS, b % N_BITS) for b in range(STATE) if (v >> b) & 1]
    return bits


def additive_inactive_prob(delta_words, trials=200000, seed=1):
    """Measure prob over random x that the additive reduction S is unchanged by delta.
       S = sum eps_i ROTL8(x_i) mod 2^32."""
    rng = np.random.default_rng(seed)
    cnt = 0
    D = delta_words
    for _ in range(trials):
        x = [int(rng.integers(0, 1 << N_BITS)) for _ in range(W)]
        xd = [x[i] ^ D[i] for i in range(W)]
        S = 0
        Sd = 0
        for i in range(W):
            term = rotl(x[i], ROT_A)
            termd = rotl(xd[i], ROT_A)
            if EPS[i] > 0:
                S = (S + term) & MASK
                Sd = (Sd + termd) & MASK
            else:
                S = (S - term) & MASK
                Sd = (Sd - termd) & MASK
        if S == Sd:
            cnt += 1
    return cnt / trials


def main():
    Acols, Crows = build_linear_columns()
    print("=== R=8 GF(2)-inactive survivor (1-dim) ===")
    ker8 = inactive_basis_after(Acols, Crows, 8)
    print(f"dim(inactive after 8 rounds) = {len(ker8)}")
    for v in ker8:
        bits = describe_vec(v)
        print(f"  survivor touches {len(bits)} state bits:")
        # group by word
        byword = {}
        for (wi, bi) in bits:
            byword.setdefault(wi, []).append(bi)
        for wi in sorted(byword):
            print(f"    word[{wi}]: bits {sorted(byword[wi])}")
        # additive test
        D = [0] * W
        for (wi, bi) in bits:
            D[wi] |= 1 << bi
        p = additive_inactive_prob(D, trials=100000)
        print(f"    additive prob-1 inactive (ΔS=0) measured prob = {p:.5f}")
        is_msb = all(bi == N_BITS - 1 for (wi, bi) in bits)
        print(f"    MSB-only? {is_msb}  (MSB-only => carry-free => additively exact)")

    print("\n=== R=7 inactive basis (32-dim) bit-weight distribution ===")
    ker7 = inactive_basis_after(Acols, Crows, 7)
    print(f"dim = {len(ker7)}")
    # are these low-weight (exploitable) or dense?
    weights = sorted(bin(v).count("1") for v in ker7)
    print(f"  Hamming weights of basis vecs: min={weights[0]} max={weights[-1]} "
          f"median={weights[len(weights)//2]}")
    # how many are MSB-supported only?
    msb_mask = 0
    for wi in range(W):
        msb_mask |= 1 << (wi * N_BITS + (N_BITS - 1))
    msb_only = sum(1 for v in ker7 if v & ~msb_mask == 0)
    print(f"  basis vecs supported on MSBs only: {msb_only}/{len(ker7)}")


if __name__ == "__main__":
    main()
