#!/usr/bin/env python3
"""
SSM / control-theory / sequence-ID analysis of yttrium's GF(2) linear backbone.

Builds on ssm_backbone.py's verified A (256x256 GF(2)).  Round modeled as

    x_{t+1} = A x_t  XOR  B * F(C x_t)  XOR  rc_t          (state-space form)

A = pi . sigma(alpha^k) . ROTR9 . ROTL8     (GF(2)-linear backbone, t=0)
C = reduce map: S = sum eps_i ROTL8(x_i)    (the scalar fed to F; 256 -> 32)
    over GF(2), -1 == +1, so C row r picks bit (r) of XOR_i ROTL8(x_i).
B = injection of t into all lanes via y_i = ROTR9(x'_i + t):
    GF(2)-linearized, +t injects t into every lane then ROTR9 then sigma then pi.

We compute:
  (1) char poly / min poly of A  (sympy GF(2)) and of per-lane A^8 blocks.
  (2) order of A (smallest m with A^m = I).
  (3) OBSERVABILITY of the F-channel: can the scalar S=Cx be predicted /
      does the linear backbone make the F-input sequence have low linear
      complexity?  Observability matrix O = [C; C A; C A^2; ...].
  (4) CONTROLLABILITY/reachability of the injection B: does t reach all of
      state, or is there an unreachable invariant subspace (structural weakness)?
  (5) Berlekamp-Massey linear complexity of REAL output-bit sequences from the
      full (nonlinear) round, to see if linear backbone leaks predictable structure.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/ybi/cryptanalysis/milp")
import ssm_backbone as bb

N = 256
W = 8
WB = 32
MASK32 = (1 << 32) - 1
EPS_PLUS = [True, False, True, False, True, False, True, False]

# ---------- integer-column matrix helpers (columns as 256-bit ints) ----------
def apply_cols(cols, v):
    out = 0; j = 0; vv = v
    while vv:
        if vv & 1:
            out ^= cols[j]
        vv >>= 1; j += 1
    return out

def mat_mul(A, B):
    return [apply_cols(A, B[j]) for j in range(N)]

def identity_cols():
    return [1 << j for j in range(N)]

def is_identity(M):
    return all(M[j] == (1 << j) for j in range(N))

def gf2_rank_intcols(cols):
    basis = []
    for v in cols:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur); basis.sort(reverse=True)
    return len(basis)

# ---------- (C) reduce map: S_b = XOR_i ROTL8(x_i)_b over GF(2) ----------
def reduce_rows():
    """Return list of 32 ints (each a 256-bit mask) s.t. bit b of S = parity(row_b & x)."""
    rows = []
    for b in range(WB):
        mask = 0
        # S bit b = XOR over lanes i of (ROTL8(x_i))_b = XOR_i x_i[(b-8) mod 32]
        src_bit = (b - bb.ROT_A) % WB
        for i in range(W):
            mask |= 1 << (i * WB + src_bit)
        rows.append(mask)
    return rows

def parity(x):
    return bin(x).count("1") & 1

# ============================================================
if __name__ == "__main__":
    A = bb.build_A_columns()
    print("== A backbone ==")
    print(f"rank(A) = {gf2_rank_intcols(A)}")

    # ---- (2) multiplicative order of A ----
    # Since pi is an 8-cycle, A^8 is block-diagonal; each lane block = alpha^{Kprod}.ROTR8
    # composed.  order(A) = 8 * order(per-lane block) lcm.  Compute directly by repeated squaring search.
    A8 = bb.mat_pow(A, 8)
    # per-lane block of A^8 for lane 0: extract 32x32 submatrix
    def lane_block(M, lane):
        sub = []
        for b in range(WB):
            col = M[lane * WB + b]
            # restrict to lane's 32 bits
            v = (col >> (lane * WB)) & MASK32
            sub.append(v)
        return sub  # 32 columns, 32-bit ints

    # order of a 32x32 gf2 matrix given as 32 int-cols
    def mm32(A, B):
        def ap(cols, v):
            o = 0; j = 0
            while v:
                if v & 1: o ^= cols[j]
                v >>= 1; j += 1
            return o
        return [ap(A, B[j]) for j in range(WB)]
    def id32():
        return [1 << j for j in range(WB)]
    def order32(M, cap=(1 << 33)):
        # order divides 2^32-1 times small factor; use the fact block = alpha^c . rot.
        cur = M; e = 1
        I = id32()
        while cur != I:
            cur = mm32(cur, M); e += 1
            if e > cap:
                return None
        return e

    # Instead of brute order (could be 2^32), characterize each lane block's char poly via sympy.
    import sympy
    from sympy import GF, Matrix, symbols, Poly

    def block_to_sympy(M32):
        # M32: 32 columns (int). Build 32x32 0/1 sympy matrix
        rows = [[ (M32[c] >> r) & 1 for c in range(WB)] for r in range(WB)]
        return Matrix(rows)

    print("\n== per-lane A^8 block char/min polynomials over GF(2) ==")
    x = symbols("x")
    lane_orders = []
    for lane in range(W):
        blk = lane_block(A8, lane)
        Msp = block_to_sympy(blk)
        cp = Msp.charpoly(x)
        cp_gf2 = Poly(cp.as_expr(), x, modulus=2)
        facts = sympy.factor_list(cp_gf2)
        # minimal poly
        mp = Msp.minimal_polynomial(x) if hasattr(Msp, "minimal_polynomial") else None
        deg_factors = [(Poly(f, x, modulus=2).degree(), m) for f, m in facts[1]]
        print(f"  lane {lane} (sigma^{bb.SIG_K[lane]}): charpoly factors (deg,mult) over GF(2) = {sorted(deg_factors)}")

    # ---- char poly of full A (256) via per-lane: A's char poly relates to A^8 blocks ----
    print("\n== full A: minimal polynomial degree (Krylov) ==")
    # minimal poly of A acting on a random vector via Krylov sequence + Berlekamp-Massey on bit-streams
    # Compute Krylov dim: smallest d s.t. {v, Av, ..., A^d v} dependent, for a generic v.
    def krylov_min_deg(A, v0, maxd=N + 2):
        seq = [v0]
        cur = v0
        for _ in range(maxd):
            cur = apply_cols(A, cur)
            seq.append(cur)
        # find min poly: rank of vectors
        # incremental rank
        basis = []
        deg = 0
        for k, v in enumerate(seq):
            cur = v
            for b in basis:
                cur = min(cur, cur ^ b)
            if cur:
                basis.append(cur); basis.sort(reverse=True); deg = k + 1
            else:
                return k  # first dependency at A^k v
        return len(seq)
    import random
    random.seed(1)
    degs = []
    for _ in range(5):
        v0 = random.getrandbits(N)
        degs.append(krylov_min_deg(A, v0))
    print(f"  Krylov min-poly degree (generic vector) = {degs}  (full state dim {N})")

    # ---- (3) OBSERVABILITY of the F-input scalar S = C x through linear backbone ----
    # O = [C ; C A ; C A^2 ; ... ]  -- does the sequence of reduce-values determine state?
    # rank of observability matrix; unobservable subspace = ker O = states invisible to F.
    Crows = reduce_rows()
    print("\n== observability of F-channel: O_R = [C; CA; ...; C A^{R-1}] ==")
    O = []
    Apow = identity_cols()
    prev_rank = 0
    for R in range(1, 20):
        # rows of C A^{R-1}: each reduce-row composed with Apow.  row . (Apow x) = (row^T Apow) . x
        # row is a mask over output of Apow; we need mask m s.t. parity(m & x) = parity(Crow & (Apow x)).
        # Apow x in terms of x: (Apow x)_b = parity(col... ) -- easier: transpose action.
        # (Crow . Apow) as a functional on x: for each bit position p of x, coefficient =
        #   parity( Crow & (Apow applied to e_p) ) = parity( Crow & Apow[p] ).
        newrows = []
        for cr in Crows:
            m = 0
            for p in range(N):
                if parity(cr & Apow[p]):
                    m |= 1 << p
            newrows.append(m)
        O.extend(newrows)
        r = gf2_rank_intcols(O)
        unobs = N - r
        flag = ""
        if unobs == 0 and prev_rank < N:
            flag = "  <- fully observable (F sees all state directions)"
        print(f"  R={R:2d}: rank(O_R)={r:3d}  unobservable dim = {unobs}{flag}")
        prev_rank = r
        if unobs == 0:
            break
        Apow = mat_mul(A, Apow)
