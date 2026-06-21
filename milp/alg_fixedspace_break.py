#!/usr/bin/env python3
"""
DECISIVE test for my angle: the GF(2) backbone A = pi.sigma.ROTR9.ROTL8 has a fixed space
ker(A-I) of dim 2 (sibling SSM finding). Control theory says: a fixed vector v (A v = v)
that is ALSO unobservable through the reduction C (so F is never excited) AND survives the
modular-add carries would be a prob-1 INVARIANT / iterative characteristic of UNBOUNDED depth
=> a structural break far worse than R*=9.

This file (self-contained, spec-exact, validated vs ymodel) computes:
  1. exact backbone A (256x256 GF2), rank, ker(A-I) basis (the fixed space),
  2. for each fixed vector v: is C_lin(v)=0 ? (unobservable => F not excited at GF2-linear level)
  3. EMPIRICAL prob-1 test on the FULL round: does input difference v propagate to v with
     probability 1 over random states? (i.e. is v a genuine prob-1 differential of the real
     nonlinear round, not just the linearized backbone?) -- this is the honest verdict.
"""
import random
from ymodel import (round_full, permute, rc, SIG_K, P_PI, ROT_A, ROT_B, EPS_PLUS, RED,
                    rotl, rotr, alpha_pow, f, zerosum_reduce)

W = 8
NL = 32
M32 = (1 << 32) - 1
N = 256


def round_backbone_state(state):
    xp = [rotl(state[i], ROT_A) for i in range(W)]
    y = [alpha_pow(rotr(xp[i], ROT_B), SIG_K[i]) for i in range(W)]
    return [y[P_PI[i]] for i in range(W)]


def st2int(st):
    v = 0
    for i in range(W):
        v |= (st[i] & M32) << (i * 32)
    return v


def int2st(v):
    return [(v >> (i * 32)) & M32 for i in range(W)]


def build_Acol():
    cols = []
    for j in range(N):
        st = [0] * W
        st[j // 32] = 1 << (j % 32)
        cols.append(st2int(round_backbone_state(st)))
    return cols


def matvec(cols, v):
    y = 0
    j = 0
    x = v
    while x:
        if x & 1:
            y ^= cols[j]
        x >>= 1
        j += 1
    return y


def gf2_rank(vec_list):
    basis = []
    for v in vec_list:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
            basis.sort(reverse=True)
    return len(basis)


def gf2_kernel_basis(cols):
    """Kernel of the linear map whose columns are `cols` (each a 256-bit int).
    Returns list of 256-bit ints spanning {x : sum_j x_j * col_j = 0}.
    Standard: augment with identity, reduce."""
    n = len(cols)
    # rows of augmented [col_j | e_j]; we reduce on the col part (256 bits) carrying e_j (n bits)
    rows = []
    for j in range(n):
        rows.append((cols[j], 1 << j))
    basis = []  # list of (pivot_mask_value, combo) reduced
    kernel = []
    # Gaussian elimination over the 'value' part; track combination
    pivots = []  # (leading_bit, value, combo)
    for (val, combo) in rows:
        v = val
        c = combo
        for (lb, pv, pc) in pivots:
            if (v >> lb) & 1:
                v ^= pv
                c ^= pc
        if v == 0:
            kernel.append(c)  # this combination of columns = 0
        else:
            lb = v.bit_length() - 1
            pivots.append((lb, v, c))
    return kernel  # each is an n-bit combo (here n=256) representing a kernel vector


def main():
    Acols = build_Acol()
    # validate
    random.seed(3)
    for _ in range(2000):
        st = [random.randint(0, M32) for _ in range(W)]
        if int2st(matvec(Acols, st2int(st))) != round_backbone_state(st):
            print("A VALIDATION FAILED")
            return
    print("A validated vs round_backbone (2000 randoms): OK")
    print(f"rank(A) = {gf2_rank(Acols)} (256 = invertible)")

    # A - I  columns:  (A-I) e_j = A e_j XOR e_j
    AmI = [Acols[j] ^ (1 << j) for j in range(N)]
    rk = gf2_rank(AmI)
    print(f"rank(A-I) = {rk}  => dim ker(A-I) = fixed space = {N - rk}")

    # kernel basis of (A-I)
    ker = gf2_kernel_basis(AmI)
    # filter to actual independent kernel vectors
    ker = [k for k in ker if k != 0]
    kb = []
    for k in ker:
        cur = k
        for b in kb:
            cur = min(cur, cur ^ b)
        if cur:
            kb.append(cur)
            kb.sort(reverse=True)
    print(f"fixed-space basis vectors ({len(kb)}):")
    for v in kb:
        st = int2st(v)
        print("   v =", [hex(x) for x in st], " popcount=", bin(v).count("1"))

    # C_lin observation: C_lin(v) = XOR_i ROTL8(v_i)
    def C_lin(v):
        st = int2st(v)
        s = 0
        for i in range(W):
            s ^= rotl(st[i], ROT_A)
        return s & M32

    print("\n-- Is each fixed vector unobservable (C_lin = 0)? (unobservable+fixed = candidate break) --")
    for v in kb:
        print(f"   C_lin(v) = {hex(C_lin(v))}  -> {'UNOBSERVABLE' if C_lin(v)==0 else 'observable (F excited)'}")

    # Decisive: empirical prob-1 differential test on the FULL nonlinear round.
    # For fixed vector v (backbone-invariant), does round_full(x XOR v) XOR round_full(x) == v
    # for ALL x? If yes for a single round -> iterate -> prob-1 invariant => break.
    print("\n-- EMPIRICAL: does fixed vector v act as prob-1 differential of the FULL round? --")
    for v in kb:
        dv = int2st(v)
        cnt = 0
        trials = 20000
        match = 0
        # use round r=0
        for _ in range(trials):
            x = [random.randint(0, M32) for _ in range(W)]
            xv = [x[i] ^ dv[i] for i in range(W)]
            o0 = round_full(x, 0)
            o1 = round_full(xv, 0)
            od = [o0[i] ^ o1[i] for i in range(W)]
            if od == dv:
                match += 1
        print(f"   v(pc={bin(v).count('1')}): round_full diff==v in {match}/{trials} "
              f"= 2^{(0 if match==0 else __import__('math').log2(match/trials)):.2f}" if match else
              f"   v(pc={bin(v).count('1')}): round_full diff==v in 0/{trials} (never)")

    # Also: linear combinations (whole 2-dim fixed space) -- test all 3 nonzero combos
    print("\n-- test all nonzero vectors of the fixed space (full round prob-1) --")
    nz = []
    for mask in range(1, 1 << len(kb)):
        v = 0
        for i in range(len(kb)):
            if (mask >> i) & 1:
                v ^= kb[i]
        nz.append(v)
    for v in nz:
        dv = int2st(v)
        trials = 5000
        match = 0
        for _ in range(trials):
            x = [random.randint(0, M32) for _ in range(W)]
            xv = [x[i] ^ dv[i] for i in range(W)]
            od = [round_full(x, 0)[i] ^ round_full(xv, 0)[i] for i in range(W)]
            if od == dv:
                match += 1
        print(f"   fixed-vec popcount={bin(v).count('1')}: prob-1 holds {match}/{trials}")


if __name__ == "__main__":
    main()
