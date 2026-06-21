#!/usr/bin/env python3
"""
Characterize the 2-dim FIXED space ker(A-I) and the Jordan chain at eigenvalue 1
(dim ker((A-I)^p) = 2p observed). NOVEL structural object.

Questions:
 (1) Basis of ker(A-I): what are these fixed directions? Low weight? MSB-only?
 (2) Do they intersect ker(C)? (observability said unobs=0, so NO; confirm + measure
     how 'observable' they are: |C v| weight).
 (3) The generalized eigenspace: ker((A-I)^p) grows by 2 each p. This is a size-2
     Jordan block structure repeated. Find the chain. Does the *additive* round preserve
     any of it with non-negligible prob? (test prob that delta in fixed space stays fixed
     through the REAL nonlinear round, sampling x).
 (4) ATTRIBUTION probe: which spec param creates the 2-dim fixed space? Re-run with
     SIG_K all distinct vs current; with framing rot changed. (the fixed space of the
     LINEAR backbone is an artifact of ROT/sigma/pi; we check if it is exploitable at all.)
"""
import numpy as np
from ssm_eigen import build_A_dense, build_C_dense, gf2_rank_mat
from ssm_unobservable import (STATE, N_BITS, W, rotl, rotr, alpha_pow, P_PI,
                              SIG_K, ROT_A, ROT_B, MASK, RED, alpha)

EPS = [1, -1, 1, -1, 1, -1, 1, -1]


def nullspace_gf2(M):
    """Return basis of right null space of GF(2) matrix M (rows x cols)."""
    M = M.copy() % 2
    rows, cols = M.shape
    pivcols = []
    r = 0
    Mr = M.copy()
    for c in range(cols):
        piv = None
        for i in range(r, rows):
            if Mr[i, c]:
                piv = i
                break
        if piv is None:
            continue
        Mr[[r, piv]] = Mr[[piv, r]]
        for i in range(rows):
            if i != r and Mr[i, c]:
                Mr[i] ^= Mr[r]
        pivcols.append(c)
        r += 1
        if r == rows:
            break
    pivset = set(pivcols)
    free = [c for c in range(cols) if c not in pivset]
    basis = []
    for f in free:
        v = np.zeros(cols, dtype=np.uint8)
        v[f] = 1
        # for each pivot row, solve
        for ri, c in enumerate(pivcols):
            # value at pivot col = sum of free contributions
            s = 0
            for fc in free:
                s ^= Mr[ri, fc] & v[fc]
            v[c] = s
        basis.append(v)
    return basis


def vec_words(v):
    return [int(sum(int(v[i * N_BITS + b]) << b for b in range(N_BITS))) for i in range(W)]


def describe(v):
    ws = vec_words(v)
    return ws, sum(bin(w).count("1") for w in ws)


def real_round_delta_preserve(D, trials=40000, seed=3):
    """Full nonlinear round: does delta D map to itself (D -> D) with what prob over x?
       (i.e. is D a prob-1 invariant difference of the actual round?)"""
    rng = np.random.default_rng(seed)

    def F(s):
        acc = s
        for (a, b) in [(7, 17), (3, 21), (9, 29)]:
            acc ^= rotl(s, a) & rotl(s, b)
        return acc & MASK

    def rnd(state, r=0):
        # full round (no ι for difference test; ι is constant XOR, cancels in differences)
        xp = [rotl(state[i], ROT_A) for i in range(W)]
        S = 0
        for i in range(W):
            S = (S + xp[i]) & MASK if EPS[i] > 0 else (S - xp[i]) & MASK
        t = F(S)
        y = [rotr((xp[i] + t) & MASK, ROT_B) for i in range(W)]
        y = [alpha_pow(y[i], SIG_K[i]) for i in range(W)]
        return [y[P_PI[i]] for i in range(W)]

    cnt = 0
    out_diffs = {}
    for _ in range(trials):
        x = [int(rng.integers(0, 1 << N_BITS)) for _ in range(W)]
        xd = [x[i] ^ D[i] for i in range(W)]
        o1 = rnd(x)
        o2 = rnd(xd)
        od = tuple(o1[i] ^ o2[i] for i in range(W))
        out_diffs[od] = out_diffs.get(od, 0) + 1
        if od == tuple(D):
            cnt += 1
    top = sorted(out_diffs.items(), key=lambda t: -t[1])[:3]
    return cnt / trials, top


def main():
    A = build_A_dense()
    C = build_C_dense()
    I = np.eye(STATE, dtype=np.uint8)
    AmI = (A ^ I) % 2

    fixed = nullspace_gf2(AmI)
    print(f"=== Fixed space ker(A-I): dim {len(fixed)} ===")
    for idx, v in enumerate(fixed):
        ws, wt = describe(v)
        Cv = (C @ v) % 2
        print(f"  fixed[{idx}]: total HW={wt}, words={[hex(w) for w in ws]}")
        print(f"     C v (F-observation of this dir) HW={int(Cv.sum())} "
              f"({'UNOBSERVABLE/break' if Cv.sum()==0 else 'observed -> activates F'})")
        D = ws
        p, top = real_round_delta_preserve(D)
        print(f"     REAL nonlinear round: P(D->D) = {p:.5f}")
        print(f"       top output diffs: {[(tuple(hex(z) for z in od), c) for od,c in top]}")

    # Jordan chain: ker((A-I)^2) \ ker(A-I)
    print("\n=== Jordan generalized eigenspace at eigenvalue 1 ===")
    AmI2 = (AmI @ AmI) % 2
    gen2 = nullspace_gf2(AmI2)
    print(f"dim ker((A-I)^2) = {len(gen2)}")
    # A generalized vector g satisfies (A-I)g in fixed space, (A-I)^2 g = 0.
    # depth grows by 2 each power -> chains of length up to ~? Check ker((A-I)^p) growth limit.
    prev = 0
    p = 1
    M = AmI.copy()
    growth = []
    while True:
        d = STATE - gf2_rank_mat(M)
        growth.append(d)
        if d == prev:
            break
        prev = d
        M = (M @ AmI) % 2
        p += 1
        if p > 40:
            break
    print(f"dim ker((A-I)^p) for p=1..: {growth}")
    print(f"=> stabilizes at dim {growth[-1]} (total generalized eigenspace at lambda=1)")
    print("   chain count = dim ker(A-I) = 2; max chain length = (stable dim)/2")


if __name__ == "__main__":
    main()
