#!/usr/bin/env python3
"""
yttrium-LM boomerang / sandwich (BCT) small-scale empirical + theory.

Faithful replica of the GPU round (yttrium_lm_diff.cu) at reduced width n (w=8 lanes):
  (ι)        state[r mod 8] ^= RC[r]            (RC optional; differential => cancels, omit)
  reduction  xp_i = ROTL_a(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), ε=[+,-,+,-,+,-,+,-]
  combiner   t = F(S);  y_i = ROTR_b(xp_i ⊞ t)
  σ          y_i ← α^{k_i}·y_i   k=[1,2,3,5,7,11,13,17]  (GF(2^n), red)
  π          new_i = y_{P[i]}

Measurements:
  (1) full-cipher boomerang return probability over E = E1∘E0 (R rounds split rb+rc)
      classic boomerang: P(C->C') with input diff a, switch diff d.
      Estimate P = #{ E^-1(E(x)+d) ^ E^-1(E(x+a)+d) == a } / N    (4-tuple test)
  (2) additive-combiner BCT focus: the ONLY non-GF(2)-affine primitive per round that
      the boomerang switch must cross is the broadcast add  v_i = xp_i ⊞ t.
      BCT of modular addition z=x⊞y over input diffs is well understood; here t is a
      *shared* broadcast so the switch couples all 8 lanes through one S.
  (3) sandwich: middle layer E_m = the add+σ, measure r=P(boomerang through E_m) directly.

GPU/nvcc forbidden here (orchestrator's job). Pure python, n=8 (and n=16 spot check).
Honesty: empirical estimates w/ finite N; report log2 and CI-ish via repeat.
"""
import random
import math

# ---- generic round builder at width n, w=8 lanes ----
PI8 = [7, 4, 1, 6, 3, 0, 5, 2]
SIG_ALL8 = [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7), (5, 11), (6, 13), (7, 17)]
EPS8 = [1, -1, 1, -1, 1, -1, 1, -1]
# F core fixed offsets (mod n)
FTERMS = [(7, 17), (3, 21), (9, 29)]


def build(n, red, a, b, sigma=SIG_ALL8, P=PI8, eps=EPS8):
    M = (1 << n) - 1
    w = 8

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alpha(v):
        top = (v >> (n - 1)) & 1
        return (((v << 1) & M) ^ (red if top else 0)) & M

    def alpha_inv(v):
        # red bit0 must be 1 for this inverse form
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

    Pinv = [0] * w
    for i in range(w):
        Pinv[P[i]] = i

    def rnd(state):
        xp = [rotl(state[i], a) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, b) for i in range(w)]
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
        S = 0
        for i in range(w):
            S = (S + v[i]) & M if eps[i] > 0 else (S - v[i]) & M
        t = F(S)
        xp = [(v[i] - t) & M for i in range(w)]
        return [rotr(xp[i], a) for i in range(w)]

    def E(state, R):
        cur = list(state)
        for _ in range(R):
            cur = rnd(cur)
        return cur

    def Einv(state, R):
        cur = list(state)
        for _ in range(R):
            cur = rnd_inv(cur)
        return cur

    return dict(n=n, M=M, w=w, rnd=rnd, rnd_inv=rnd_inv, E=E, Einv=Einv,
                rotl=rotl, rotr=rotr, alfp=alfp, alfp_inv=alfp_inv, F=F)


# ---------- boomerang 4-tuple test over full R = rb+rc ----------
def boomerang_prob(ctx, R, a_in, d_out, N, seed=0):
    """P = #{ Einv(E(x)+d) XOR Einv(E(x+a)+d) == a } / N."""
    rng = random.Random(seed)
    w = ctx['w']; M = ctx['M']; E = ctx['E']; Einv = ctx['Einv']
    cnt = 0
    for _ in range(N):
        x = [rng.randrange(M + 1) for _ in range(w)]
        xa = [(x[i] ^ a_in[i]) & M for i in range(w)]
        c1 = E(x, R); c2 = E(xa, R)
        c3 = [(c1[i] ^ d_out[i]) & M for i in range(w)]
        c4 = [(c2[i] ^ d_out[i]) & M for i in range(w)]
        p3 = Einv(c3, R); p4 = Einv(c4, R)
        if all(((p3[i] ^ p4[i]) & M) == a_in[i] for i in range(w)):
            cnt += 1
    return cnt / N


# ---------- additive-combiner BCT (modular add) ----------
def add_bct_entry(n, dx, dy, N=None):
    """BCT of z = x ⊞ y (mod 2^n) w.r.t. XOR diffs, input-side (dx,dy)->(dx,dy).
    BCT(dx,dy) = #{(x,y): ((x+y) - ((x^dx)+(y^dy)) ... boomerang) }. We use the
    standard modular-add boomerang return count over all (x,y)."""
    M = (1 << n) - 1
    cnt = 0
    tot = 1 << (2 * n)
    for x in range(1 << n):
        for y in range(1 << n):
            z = (x + y) & M
            # forward two faces with output diff = dz (we test dz = dx for broadcast? )
            # classic add-BCT: fix output diff dz; here we test the *table* differently below.
            pass
    return None  # replaced by add_combiner_bct below


def add_combiner_bct(n, dx, dz, N_full=True):
    """For the combiner v = xp ⊞ t (single lane), boomerang in xp with fixed t-diff.
    But t is broadcast (same across lanes & determined by S). We isolate the
    per-lane add boomerang: face fwd uses xp-diff=dx; switch in v uses dz; we count
    returns. This is the per-lane add-BCT with the SECOND operand (t) held diff-free
    on the forward pair but possibly perturbed by the switch.

    Standard add BCT (Boura-Canteaut / Wang-Peyrin):
      BCT_add(dx, dz) over operand x with fixed y:
        count (x,y): ((x+y) ^ dz then -y) gives back x^dx consistency.
    We compute the lane-local add boomerang return rate with t fixed (dy=0):
      r = avg over (x,t): [ inv( fwd(x,t) ^ dz, t ) ^ inv( fwd(x^dx,t)^dz, t ) == dx ]
    where fwd(x,t)=x+t (mod), inv(v,t)=v-t (mod)."""
    M = (1 << n) - 1
    cnt = 0
    tot = (1 << n) * (1 << n)
    for x in range(1 << n):
        for t in range(1 << n):
            v1 = (x + t) & M
            v2 = ((x ^ dx) + t) & M
            v3 = (v1 ^ dz) & M
            v4 = (v2 ^ dz) & M
            x3 = (v3 - t) & M
            x4 = (v4 - t) & M
            if (x3 ^ x4) == dx:
                cnt += 1
    return cnt / tot


def add_dp(n, dx, dy, dz):
    """differential prob of modular add: P[(x+y)^((x^dx)+(y^dy)) == dz]."""
    M = (1 << n) - 1
    cnt = 0
    for x in range(1 << n):
        for y in range(1 << n):
            if (((x + y) & M) ^ (((x ^ dx) + (y ^ dy)) & M)) == dz:
                cnt += 1
    return cnt / (1 << (2 * n))


if __name__ == "__main__":
    print("### additive-combiner per-lane add boomerang (BCT) ###")
    print("# v=x⊞t, switch diff dz in v, forward diff dx in x, t held fixed (dy=0).")
    print("# n=8 exhaustive over (x,t).")
    n = 8
    tests = [(0x80, 0x80), (0x01, 0x01), (0x80, 0x40), (0x01, 0x02),
             (0xFF, 0xFF), (0x80, 0x00), (0x00, 0x80), (0x40, 0x40)]
    for dx, dz in tests:
        r = add_combiner_bct(n, dx, dz)
        lg = (-math.log2(r)) if r > 0 else float('inf')
        print(f"  dx=0x{dx:02X} dz=0x{dz:02X}: r={r:.6f} = 2^-{lg:.2f}")

    print("\n### compare: add differential DP (dy=0) ###")
    for dx, dz in [(0x80, 0x80), (0x01, 0x01), (0x80, 0x40), (0x40, 0x40)]:
        p = add_dp(n, dx, 0, dz)
        lg = (-math.log2(p)) if p > 0 else float('inf')
        print(f"  add-DP dx=0x{dx:02X} dy=0 dz=0x{dz:02X}: {p:.6f} = 2^-{lg:.2f}")
