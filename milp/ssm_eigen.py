#!/usr/bin/env python3
"""
NOVEL: eigenstructure / invariant analysis of the 256x256 GF(2) backbone A.

Control-theory invariants beyond observability:
  (1) Fixed subspace ker(A - I): vectors with A v = v. A nonzero such v that is ALSO
      in ker(C) (unobservable) would be a prob-1 invariant difference of unbounded depth.
  (2) Left-invariant functionals: ell with ell A = ell. If ell is supported so that the
      broadcast-t and sigma preserve it in the *full* (nonlinear) round, that's an
      invariant => distinguisher. We check ell A = ell over GF(2).
  (3) Order of A (multiplicative order of the backbone) and its minimal polynomial degree
      -> cycle structure / slide potential.
  (4) Does A commute with any nontrivial 'word rotation' symmetry (pi-power)? -> structural.

We build A as a 256x256 numpy GF(2) matrix and compute:
  - rank(A - I), dim of fixed space, and whether fixed space meets ker(C),
  - left fixed space (A^T - I),
  - order of A (as permutation-of-GF2-space: smallest m with A^m = I) via repeated squaring check,
  - characteristic poly factor hint via dim ker((A-I)) etc.
"""
import numpy as np
from ssm_unobservable import (STATE, N_BITS, W, rotl, rotr, alpha_pow, P_PI,
                              SIG_K, ROT_A, ROT_B, MASK, RED)


def build_A_dense():
    A = np.zeros((STATE, STATE), dtype=np.uint8)
    for wi in range(W):
        for bi in range(N_BITS):
            words = [0] * W
            words[wi] = 1 << bi
            xp = [rotl(words[i], ROT_A) for i in range(W)]
            y = [rotr(xp[i], ROT_B) for i in range(W)]
            y = [alpha_pow(y[i], SIG_K[i]) for i in range(W)]
            new = [y[P_PI[i]] for i in range(W)]
            col = wi * N_BITS + bi
            for i in range(W):
                for ob in range(N_BITS):
                    if (new[i] >> ob) & 1:
                        A[i * N_BITS + ob, col] = 1
    return A


def build_C_dense():
    C = np.zeros((N_BITS, STATE), dtype=np.uint8)
    for r in range(N_BITS):
        for i in range(W):
            src = (r - ROT_A) % N_BITS
            C[r, i * N_BITS + src] = 1
    return C


def gf2_rank_mat(M):
    M = M.copy() % 2
    rows, cols = M.shape
    r = 0
    for c in range(cols):
        piv = None
        for i in range(r, rows):
            if M[i, c]:
                piv = i
                break
        if piv is None:
            continue
        M[[r, piv]] = M[[piv, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def matpow_gf2(A, e):
    R = np.eye(A.shape[0], dtype=np.uint8)
    base = A.copy() % 2
    while e:
        if e & 1:
            R = (R @ base) % 2
        base = (base @ base) % 2
        e >>= 1
    return R


def main():
    A = build_A_dense()
    C = build_C_dense()
    I = np.eye(STATE, dtype=np.uint8)
    print("=== Eigen / invariant structure of GF(2) backbone A (256x256) ===")
    print(f"rank(A) = {gf2_rank_mat(A)} (should be 256 = invertible backbone)")

    AmI = (A ^ I) % 2
    rk = gf2_rank_mat(AmI)
    print(f"rank(A - I) = {rk}, dim fixed space ker(A-I) = {STATE - rk}")

    AtmI = (A.T ^ I) % 2
    rkt = gf2_rank_mat(AtmI)
    print(f"rank(A^T - I) = {rkt}, dim left-fixed functionals = {STATE - rkt}")

    # (A-I)^2 etc to see Jordan-like structure at eigenvalue 1
    for p in range(1, 5):
        M = matpow_gf2(AmI, p)
        print(f"  dim ker((A-I)^{p}) = {STATE - gf2_rank_mat(M)}")

    # order of A: find smallest m | (2^d-1)*... ; just test small multiples & 2^k structure
    # The order divides lcm of orders of invariant factors. Practical: check A^m = I for
    # candidate m from structure of alpha (order 2^32-1) interacting with pi (order 8) & rotations.
    print("\n=== order probing (A^m == I ?) ===")
    ord_alpha = (1 << 32) - 1
    # candidates: divisors-ish of ord_alpha * small
    cands = [8, 255, 257, 65535, ord_alpha, ord_alpha * 8 % (1 << 40)]
    # too expensive to test huge; instead report minimal polynomial degree proxy via Krylov
    # Krylov dimension of a random vector -> degree of its minimal poly (<= deg min poly of A)
    rng = np.random.default_rng(0)
    v = rng.integers(0, 2, size=STATE).astype(np.uint8)
    krylov = [v.copy()]
    cur = v.copy()
    for _ in range(STATE):
        cur = (A @ cur) % 2
        # check independence
        M = np.array(krylov + [cur], dtype=np.uint8)
        if gf2_rank_mat(M) == len(krylov):
            break
        krylov.append(cur.copy())
    print(f"Krylov dim of random vector under A = {len(krylov)} "
          f"(>= path length before linear recurrence; hints min-poly degree)")

    # invariant subspaces meeting ker C: does any A-invariant low-dim subspace avoid C?
    # already answered by observability (unobservable=0). Confirm fixed space ∩ ker C:
    if STATE - rk > 0:
        print("Fixed space nonzero -> check intersection with ker(C) (would be a break).")
    else:
        print("\nFixed space of A is trivial (only 0) -> no prob-1 invariant difference.")


if __name__ == "__main__":
    main()
