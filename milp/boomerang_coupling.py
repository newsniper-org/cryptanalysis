#!/usr/bin/env python3
"""
The crux: does broadcast-t + zero-sum S + interleaved σ(α^k) break or preserve the
ARX boomerang "free switch" (BCT-1) that the per-lane add enjoys?

Per-lane add alone: BCT has MANY prob-1 entries (boomerang_bct.py showed dx=0x80,
dz=0x40 returns w.p. 1 though add-DP=0). Classic ARX boomerang threat.

yttrium differences that can KILL it:
 (i)  t is BROADCAST: same t added to all 8 lanes; t = F(S), S=Σ ε_i ROTL_a(x_i).
      The switch (XOR d_out at output) propagates back through π^-1, σ^-1=α^-k, ROTL_b,
      then the SUBTRACT -t. For the boomerang to "click", the two recombined faces must
      see CONSISTENT t. If the switch perturbs S (hence t) differently on the two faces,
      the -t cancellation fails => BCT collapses from 1 to ~2^-something.
 (ii) σ=α^k between add and next add is a GF(2)-LINEAR but rotation-NON-preserving map.
      It moves the clean MSB/lsb add-BCT diffs into messy multi-bit diffs, so they no
      longer hit the prob-1 add-BCT cells on the next round's add.

Here we measure ONE real round used as the switch middle, isolating these:
  middle(state) = round = [ROTL_a, S, t=F(S), v_i=ROTR_b(xp_i+t), σ, π]
We do a *generalized* boomerang where the switch diff is applied at the round OUTPUT
(post σ,π) and we measure the return through round^-1, for various (a_in,d_out).
We then ABLATE: (a) replace broadcast t by independent per-lane t_i (kills coupling),
(b) remove σ, (c) make S not zero-sum, to see which structure carries the switch.
"""
import random
import math
from boomerang_bct import SIG_ALL8, PI8, EPS8, FTERMS


def make_round(n, red, a, b, broadcast=True, use_sigma=True, zero_sum=True):
    M = (1 << n) - 1
    w = 8
    eps = EPS8 if zero_sum else [1] * w
    sigma = SIG_ALL8 if use_sigma else []
    P = PI8

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alpha(v):
        top = (v >> (n - 1)) & 1
        return (((v << 1) & M) ^ (red if top else 0)) & M

    def alpha_inv(v):
        if v & 1:
            return ((v ^ red) >> 1) | (1 << (n - 1))
        return v >> 1

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    def alfp_inv(v, k):
        for _ in range(k):
            v = alpha_inv(v)
        return v

    def F(s):
        acc = 0
        for (p, q) in FTERMS:
            acc ^= rotl(s, p) & rotl(s, q)
        return s ^ acc

    def rnd(state):
        xp = [rotl(state[i], a) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        if broadcast:
            t = F(S)
            tv = [t] * w
        else:
            # per-lane independent t derived from each lane (kills broadcast coupling)
            tv = [F(xp[i]) for i in range(w)]
        y = [rotr((xp[i] + tv[i]) & M, b) for i in range(w)]
        for (lane, k) in sigma:
            y[lane] = alfp(y[lane], k)
        return [y[P[i]] for i in range(w)]

    def rnd_inv(state):
        y = [0] * w
        for i in range(w):
            y[P[i]] = state[i]
        for (lane, k) in sigma:
            y[lane] = alfp_inv(y[lane], k)
        v = [rotl(y[i], b) for i in range(w)]
        if broadcast:
            S = 0
            for i in range(w):
                S = (S + v[i]) & M if eps[i] > 0 else (S - v[i]) & M
            t = F(S)
            tv = [t] * w
            xp = [(v[i] - t) & M for i in range(w)]
        else:
            # invert per-lane: v_i = xp_i + F(xp_i); not bijective in general -> use
            # forward-only test for this ablation (skip inv correctness, only fwd boomerang
            # via 2 indep encryptions not available). We approximate by table search n small.
            xp = [None] * w
            for i in range(w):
                for cand in range(M + 1):
                    if ((cand + F(cand)) & M) == v[i]:
                        xp[i] = cand
                        break
                if xp[i] is None:
                    xp[i] = 0
        return [rotr(xp[i], a) for i in range(w)]

    return dict(n=n, M=M, w=w, rnd=rnd, rnd_inv=rnd_inv)


def boomerang(ctx, R, a_in, d_out, N, seed=0):
    rng = random.Random(seed)
    w = ctx['w']; M = ctx['M']

    def E(s):
        for _ in range(R):
            s = ctx['rnd'](s)
        return s

    def Ei(s):
        for _ in range(R):
            s = ctx['rnd_inv'](s)
        return s
    cnt = 0
    for _ in range(N):
        x = [rng.randrange(M + 1) for _ in range(w)]
        xa = [(x[i] ^ a_in[i]) & M for i in range(w)]
        c1 = E(x); c2 = E(xa)
        c3 = [(c1[i] ^ d_out[i]) & M for i in range(w)]
        c4 = [(c2[i] ^ d_out[i]) & M for i in range(w)]
        p3 = Ei(c3); p4 = Ei(c4)
        if all(((p3[i] ^ p4[i]) & M) == a_in[i] for i in range(w)):
            cnt += 1
    return cnt


def lg(p):
    return float('inf') if p <= 0 else -math.log2(p)


def D(w, M, pairs):
    v = [0] * w
    for (lane, val) in pairs:
        v[lane] = val & M
    return v


if __name__ == "__main__":
    n = 8; red = 0x1D; a, b = 0, 1; w = 8; M = 255
    N = 1 << 18

    print("### 1-round switch boomerang: full recommended round (broadcast t, σ, zero-sum) ###")
    ctx = make_round(n, red, a, b, broadcast=True, use_sigma=True, zero_sum=True)
    # candidate switch diffs: single-lane MSB at output, and a few multi-lane
    diffs = [D(w, M, [(0, 0x80)]), D(w, M, [(0, 0x01)]), D(w, M, [(3, 0x80)]),
             D(w, M, [(0, 0x80), (4, 0x80)]), D(w, M, [(0, 0x80), (1, 0x80)])]
    for ai in diffs:
        best = (0, None)
        for di in diffs:
            c = boomerang(ctx, 1, ai, di, N)
            if c > best[0]:
                best = (c, di)
        print(f"  a={['%02X' % v for v in ai]} best d={['%02X' % v for v in best[1]]}"
              f"  r={best[0]}/{N}=2^-{lg(best[0] / N):.2f}")

    print("\n### 2-round switch boomerang (broadcast,σ,zero-sum) ###")
    best = (0, None, None)
    for ai in diffs:
        for di in diffs:
            c = boomerang(ctx, 2, ai, di, 1 << 16)
            if c > best[0]:
                best = (c, ai, di)
    print(f"  best a={['%02X' % v for v in best[1]]} d={['%02X' % v for v in best[2]]}"
          f"  r={best[0]}/{1 << 16}=2^-{lg(best[0] / (1 << 16)):.2f}")

    print("\n### ABLATION A: NO σ (use_sigma=False) — does σ kill the switch? ###")
    ctx2 = make_round(n, red, a, b, broadcast=True, use_sigma=False, zero_sum=True)
    for ai in diffs[:3]:
        best = (0, None)
        for di in diffs:
            c = boomerang(ctx2, 1, ai, di, N)
            if c > best[0]:
                best = (c, di)
        print(f"  a={['%02X' % v for v in ai]} best d={['%02X' % v for v in best[1]]}"
              f"  r={best[0]}/{N}=2^-{lg(best[0] / N):.2f}")

    print("\n### ABLATION B: NO σ, 2-round switch — switch survives deeper w/o σ? ###")
    best = (0, None, None)
    for ai in diffs:
        for di in diffs:
            c = boomerang(ctx2, 2, ai, di, 1 << 16)
            if c > best[0]:
                best = (c, ai, di)
    print(f"  best a={['%02X' % v for v in best[1]]} d={['%02X' % v for v in best[2]]}"
          f"  r={best[0]}/{1 << 16}=2^-{lg(best[0] / (1 << 16)):.2f}")
