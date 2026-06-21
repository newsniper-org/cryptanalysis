#!/usr/bin/env python3
"""
NOVEL algebraic angle: per-round nonlinear budget = ONE shared 32-bit t = F(S).
If the attacker GUESSES the R values t_0..t_{R-1} (one 32-bit word per round), the entire
permute becomes a single GF(2)-AFFINE map  out = L_g(in) XOR c_g  (g = guessed t-sequence),
because:
   - ROTL8, ROTR9, sigma(alpha^k), pi are all GF(2)-linear,
   - the only nonlinearity is t (broadcast add) and the modular-add carries.
BUT modular add x'_i + t has carries that are nonlinear in (x'_i, t). However if t is FIXED
(guessed) and we also treat the add as the affine map x -> x + const... the carry from
x'_i + t is still nonlinear in x'_i. So guessing t alone does NOT linearize: the carries of
the 8 modular adds remain. This file MEASURES exactly how much guessing buys:

Test A: per round, given S (=> t), is y_i = ROTR9(x'_i + t) AFFINE in x'_i? No (carry). But
        the consistency constraint  S = sum eps_i x'_i  must hold. The real leverage is the
        Lai-Massey 'zero-sum' structure: S depends on ALL lanes, and t feeds back into ALL.

Test B (the actual MITM/guess-determine cost): For R rounds, the unknowns are the input
        (256 bits). The guessed quantities are {S_r}_{r<R} (32 bits each). GIVEN all S_r,
        does the system become solvable by GF(2)-linear algebra + carry-propagation
        (i.e. degree collapses)? We measure the GF(2) ANF degree of one output bit as a
        function of input bits, WITH S_r treated as known constants (the 'linearized-by-guess'
        degree) vs WITHOUT (true degree). If guessing S_r drops degree to 1, then a
        guess-and-determine with 32R guessed bits + linear solve breaks R rounds at cost 2^{32R}
        -- only useful if 32R < 256, i.e. R<=7 for the 256-bit security, but the consistency
        of guesses must be checkable cheaply.

We do this on narrow width (n per lane) faithfully (carry chain preserved for n>=4).
"""
import itertools
import numpy as np

def make(n, w, sig_k, P, A_rot, B_rot, eps, red):
    M = (1 << n) - 1

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alpha(v):
        return (((v << 1) & M) ^ (red if (v >> (n - 1)) & 1 else 0))

    def apow(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    if n >= 8:
        TERMS = [(7 % n, 17 % n), (3 % n, 21 % n), (9 % n, 29 % n)]
    else:
        TERMS = [(1, n // 2), (2 % n or 1, n - 1), (3 % n or 1, (n - 2) % n or 1)]

    def F(s):
        acc = s
        for (r1, r2) in TERMS:
            acc ^= rotl(s, r1) & rotl(s, r2)
        return acc & M

    def Sval(words):
        xp = [rotl(words[i], A_rot) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        return S

    def rnd(words, force_t=None):
        xp = [rotl(words[i], A_rot) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S) if force_t is None else force_t
        y = [rotr((xp[i] + t) & M, B_rot) for i in range(w)]
        y = [apow(y[i], sig_k[i]) for i in range(w)]
        return [y[P[i]] for i in range(w)], S, t

    return rnd, Sval, F, M


def anf_degree_of_map(n, w, eval_fn):
    """eval_fn: list of w words (each n bits) -> list of w words. Return (min,max) ANF degree
    over all output bits, via Mobius transform. Requires N=n*w <= 22 or so."""
    N = n * w
    M = (1 << n) - 1
    size = 1 << N
    # build truth table for each of N output bits
    out_bits = np.zeros((N, size), dtype=np.uint8)
    for code in range(size):
        ws = [(code >> (i * n)) & M for i in range(w)]
        o = eval_fn(ws)
        ov = 0
        for i in range(w):
            ov |= (o[i] & M) << (i * n)
        for b in range(N):
            out_bits[b, code] = (ov >> b) & 1
    idx = np.arange(size)
    popc = np.array([bin(i).count("1") for i in range(size)], dtype=np.int16)
    mind, maxd = N, 0
    for b in range(N):
        tt = out_bits[b].copy()
        i = 1
        while i < size:
            mask = (idx & i) != 0
            tt[mask] ^= tt[idx[mask] ^ i]
            i <<= 1
        nz = np.nonzero(tt)[0]
        d = int(popc[nz].max()) if nz.size else 0
        maxd = max(maxd, d)
        mind = min(mind, d)
    return mind, maxd


if __name__ == "__main__":
    # faithful-ish narrow config: n=4, w=4 (N=16). carry chain length 4 (vs 32 full) but present.
    n, w = 4, 4
    red = 0x13  # primitive deg-4? we just need a permutation alpha; check order
    # find primitive
    def find_prim(n):
        Mx = (1 << n) - 1
        for r in range(3, 1 << n, 2):
            v = 1
            seen = set()
            for _ in range((1 << n) - 1):
                seen.add(v)
                top = v >> (n - 1)
                v = ((v << 1) & Mx) ^ (r if top else 0)
            if len(seen) == (1 << n) - 1 and v == 1:
                return r
        raise RuntimeError
    red = find_prim(n)
    sig_k = [1, 2, 3, 5]
    P = [3, 0, 1, 2]
    eps = [1, -1, 1, -1]
    print(f"### guess-t linearization test (n={n}, w={w}, N={n*w}, red={hex(red)}) ###")

    for R in range(1, 5):
        rnd, Sval, F, M = make(n, w, sig_k, P, 1, 2, eps, red)

        # true map: R rounds
        def true_map(ws, R=R):
            cur = list(ws)
            for r in range(R):
                cur, S, t = rnd(cur)
            return cur

        mind, maxd = anf_degree_of_map(n, w, true_map)
        print(f"  R={R}: TRUE map ANF degree  min={mind} max={maxd}  (N-1={n*w-1})")

    # guess-t: fix the t-sequence to the values induced by ONE reference input, then
    # ask the degree of the map with those t's HARDCODED (= the 'linearized by correct guess' map).
    # If degree collapses to small, guess-and-determine is cheap PER guess; cost = product of t-space.
    print("\n  -- with t-sequence HARDCODED to a reference trajectory's t's (guess-and-determine) --")
    ref_in = [1, 2, 3, 4]
    for R in range(1, 5):
        rnd, Sval, F, M = make(n, w, sig_k, P, 1, 2, eps, red)
        # compute reference t-sequence
        cur = list(ref_in)
        tseq = []
        for r in range(R):
            cur, S, t = rnd(cur)
            tseq.append(t)

        def guess_map(ws, R=R, tseq=tseq):
            cur = list(ws)
            for r in range(R):
                cur, S, t = rnd(cur, force_t=tseq[r])
            return cur

        mind, maxd = anf_degree_of_map(n, w, guess_map)
        print(f"  R={R}: GUESS-t map ANF degree min={mind} max={maxd}  "
              f"(if max small => carries remain nonlinear; guessing t alone insufficient)")
