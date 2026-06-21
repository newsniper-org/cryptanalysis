#!/usr/bin/env python3
"""
Assess the guess-and-determine attack enabled by the degree-collapse observation:
guessing the per-round broadcast t reduces yttrium to a degree<=3 GF(2) system.

Questions answered with exact small-scale measurement:
 (Q1) Is the residual (guess-t) degree really bounded (independent of width n)? -> the carry
      of a single modular add x + const has ANF degree up to n-1 in the WORST case (long
      carry), NOT 3. The n=4 test showing max=3 might be width artifact. Re-measure at n=5,6
      to see if residual degree grows with n (=> at n=32 the 'linearized' system is still
      high-degree => guess-t gives NO real advantage).
 (Q2) Consistency cost: the guessed t_r are NOT free 32-bit words; t_r = F(S_r) and
      S_r = zero-sum-reduce(ROTL8(state_r)). So the guess space is constrained. Measure the
      image size of S over one round (is S uniform / full 2^32?) -> determines real guess cost.
 (Q3) Net: does guess-and-determine beat 2^{state}? Compute the break-even.
"""
import numpy as np


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
    raise RuntimeError(f"no primitive for n={n}")


def carry_degree(n):
    """ANF degree of the map x -> (x + c) mod 2^n for FIXED random c (the residual add nonlin)."""
    M = (1 << n) - 1
    idx = np.arange(1 << n)
    popc = np.array([bin(i).count("1") for i in range(1 << n)], dtype=np.int16)
    maxd = 0
    # worst-case c chosen to maximize carry propagation; test all c, take max degree
    worst = 0
    for c in range(1 << n):
        out = np.array([(x + c) & M for x in range(1 << n)], dtype=np.int64)
        dmax = 0
        for b in range(n):
            tt = ((out >> b) & 1).astype(np.uint8)
            i = 1
            while i < (1 << n):
                mask = (idx & i) != 0
                tt[mask] ^= tt[idx[mask] ^ i]
                i <<= 1
            nz = np.nonzero(tt)[0]
            d = int(popc[nz].max()) if nz.size else 0
            dmax = max(dmax, d)
        worst = max(worst, dmax)
    return worst


def guess_t_residual_degree(n, w, sig_k, P, eps, red, R):
    """ANF max-degree of the R-round map with the t-sequence hardcoded (per a ref input)."""
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

    def rnd(words, ft=None):
        xp = [rotl(words[i], 1) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S) if ft is None else ft
        y = [rotr((xp[i] + t) & M, 2) for i in range(w)]
        y = [apow(y[i], sig_k[i]) for i in range(w)]
        return [y[P[i]] for i in range(w)], t

    ref = [1, 2, 3, 4][:w] + [0] * (w - 4) if w > 4 else [1, 2, 3, 4][:w]
    cur = list(ref)
    tseq = []
    for r in range(R):
        cur, t = rnd(cur)
        tseq.append(t)

    N = n * w
    size = 1 << N
    idx = np.arange(size)
    popc = np.array([bin(i).count("1") for i in range(size)], dtype=np.int16)
    out_all = np.zeros((N, size), dtype=np.uint8)
    for code in range(size):
        ws = [(code >> (i * n)) & M for i in range(w)]
        for r in range(R):
            ws, _ = rnd(ws, ft=tseq[r])
        ov = 0
        for i in range(w):
            ov |= (ws[i] & M) << (i * n)
        for b in range(N):
            out_all[b, code] = (ov >> b) & 1
    maxd = 0
    for b in range(N):
        tt = out_all[b].copy()
        i = 1
        while i < size:
            mask = (idx & i) != 0
            tt[mask] ^= tt[idx[mask] ^ i]
            i <<= 1
        nz = np.nonzero(tt)[0]
        d = int(popc[nz].max()) if nz.size else 0
        maxd = max(maxd, d)
    return maxd, tseq


def S_image_size(n, w, eps, samples=200000):
    """How surjective is S over one round? Sample distribution of S=zero-sum-reduce(ROTL8(x))."""
    import random
    random.seed(5)
    M = (1 << n) - 1
    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M
    seen = set()
    N = n * w
    full = (1 << N) <= 200000
    if full:
        for code in range(1 << N):
            ws = [(code >> (i * n)) & M for i in range(w)]
            xp = [rotl(ws[i], 1) for i in range(w)]
            S = 0
            for i in range(w):
                S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
            seen.add(S)
    else:
        for _ in range(samples):
            ws = [random.randint(0, M) for _ in range(w)]
            xp = [rotl(ws[i], 1) for i in range(w)]
            S = 0
            for i in range(w):
                S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
            seen.add(S)
    return len(seen), (1 << n)


if __name__ == "__main__":
    print("### (Q1) residual carry degree of single modular add x+c, by width n ###")
    for n in range(3, 13):
        print(f"  n={n}: worst-case ANF degree of x->(x+c) = {carry_degree(n)}  (= n-1 means full carry)")

    print("\n### (Q1b) guess-t residual map degree, faithful widths ###")
    for (n, w) in [(4, 4), (5, 3), (6, 3)]:
        red = find_prim(n)
        sig = [1, 2, 3, 5][:w]
        P = list(range(1, w)) + [0]
        eps = [1, -1, 1, -1][:w] if w >= 4 else [1, -1, 1][:w]
        if w == 3:
            eps = [1, -1, 1]
        for R in [1, 2, 3]:
            try:
                d, ts = guess_t_residual_degree(n, w, sig, P, eps, red, R)
                print(f"  n={n} w={w} N={n*w} R={R}: guess-t residual max-degree = {d}  (N-1={n*w-1})")
            except Exception as e:
                print(f"  n={n} w={w} R={R}: {e}")

    print("\n### (Q2) image size of S over one round (guess-space of t) ###")
    for (n, w) in [(4, 4), (5, 4), (6, 3), (8, 2)]:
        sz, full = S_image_size(n, w, [1, -1, 1, -1][:w] if w == 4 else ([1, -1, 1] if w == 3 else [1, -1]))
        print(f"  n={n} w={w}: |image(S)| ~ {sz} / {full}  ({100*sz/full:.1f}% surjective)")
