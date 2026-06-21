#!/usr/bin/env python3
"""
yttrium-LM Differential-Linear distinguisher (reduced width, EXACT round replication).

Round function copied verbatim from verify_n8_slope.py / yttrium_lm_diff.cu:
  xp_i = ROTL_a(x_i);  S = Sum_i eps_i*xp_i (mod 2^n), eps=[+,-,+,-,+,-,+,-]
  t = F(S) = s ^ (s<<<7 & s<<<17) ^ (s<<<3 & s<<<21) ^ (s<<<9 & s<<<29)
  y_i = ROTR_b(xp_i + t);  y_i <- alpha^{k_i}*y_i  (GF(2^n) red);  pi=[7,4,1,6,3,0,5,2]

DL distinguisher (the *direct* measurement, no trail splitting):
  For input difference delta and output mask beta, the DL correlation is
     C_DL(delta,beta) = E_x[ (-1)^{ beta . ( P_R(x) ^ P_R(x ^ delta) ) } ]
  This is exactly the correlation a DL distinguisher exploits; data cost ~ C_DL^-2.
  The "p*q^2" formula is the trail-decomposed estimate; here we measure C_DL end-to-end
  so we get the true (hull-summed) value at reduced width.

We sweep:
  (1) straight best-DP per round (anchor vs straight-differential baseline)
  (2) straight best linear |corr| per round
  (3) best DL correlation per round, searching delta in the worst-DP class (MSB-pairs +
      single bits) and beta over single-bit + low-weight masks.

Reduced width n=8, w=8 (state 64 bit). GPU forbidden; this is the small-scale honesty check.
"""
import numpy as np, math, sys

# ---------------- exact round (n parametric) ----------------
EPS = [1, -1, 1, -1, 1, -1, 1, -1]
PI  = [7, 4, 1, 6, 3, 0, 5, 2]
SIGK = [1, 2, 3, 5, 7, 11, 13, 17]

def make_round(n, a, b, red, sigk):
    M = np.uint64((1 << n) - 1)
    TERMS = [(7 % n, 17 % n), (3 % n, 21 % n), (9 % n, 29 % n)]
    def rotl(x, k):
        k %= n
        if k == 0: return x
        return ((x << np.uint64(k)) | (x >> np.uint64(n - k))) & M
    def rotr(x, k): return rotl(x, (n - (k % n)) % n)
    rv = np.uint64(red)
    def alpha(v):
        top = (v >> np.uint64(n - 1)) & np.uint64(1)
        return ((v << np.uint64(1)) & M) ^ (rv * top)
    def apow(v, k):
        for _ in range(k): v = alpha(v)
        return v
    def F(s):
        acc = s.copy()
        for (p, q) in TERMS: acc = acc ^ (rotl(s, p) & rotl(s, q))
        return acc & M
    def rnd(ws):
        u = [rotl(ws[i], a) for i in range(8)]
        S = np.zeros_like(ws[0])
        for i in range(8):
            S = (S + u[i]) & M if EPS[i] > 0 else (S - u[i]) & M
        t = F(S)
        v = [(u[i] + t) & M for i in range(8)]
        y = [rotr(v[i], b) for i in range(8)]
        y = [apow(y[i], sigk[i]) for i in range(8)]
        return [y[PI[i]] for i in range(8)]
    def perm(ws, R):
        s = [w.copy() for w in ws]
        for _ in range(R): s = rnd(s)
        return s
    return perm, int(M)

# ---------------- helpers ----------------
def parity64(x):
    x = x ^ (x >> np.uint64(32)); x = x ^ (x >> np.uint64(16))
    x = x ^ (x >> np.uint64(8));  x = x ^ (x >> np.uint64(4))
    x = x ^ (x >> np.uint64(2));  x = x ^ (x >> np.uint64(1))
    return (x & np.uint64(1)).astype(np.int8)

def delta_classes(n, full=True):
    msb = 1 << (n - 1)
    plus = [0, 2, 4, 6]; minus = [1, 3, 5, 7]
    ds = []
    for grp in (plus, minus):  # worst-DP class: same-sign MSB pairs (12)
        for i in range(4):
            for j in range(i + 1, 4):
                d = [0] * 8; d[grp[i]] = msb; d[grp[j]] = msb; ds.append(tuple(d))
    if full:
        for l in range(8):
            for bit in (0, n // 2, n - 1):
                d = [0] * 8; d[l] = 1 << bit; ds.append(tuple(d))
    return ds

# ---------------- (1)+(3) fused: straight best-DP AND best-DL in one perm pass ----------------
def best_dp_dl(perm, M, n, deltas, R, N, seed, n_betas=300):
    """One pass: for each delta compute output-diff lanes d, derive
       (a) best-DP = max collision prob of the full 8-lane diff,
       (b) best-DL corr = max over single-bit + low-weight beta of E[(-1)^{beta.d}]."""
    rng = np.random.default_rng(seed)
    best_dp = 0.0; bDdp = None
    best_dl = 0.0; bDdl = None
    for D in deltas:
        x = [rng.integers(0, M + 1, size=N, dtype=np.uint64) for _ in range(8)]
        y = [x[i] ^ np.uint64(D[i]) for i in range(8)]
        ox = perm(x, R); oy = perm(y, R)
        d = [(ox[i] ^ oy[i]) & np.uint64(M) for i in range(8)]
        # (a) DP
        key = np.zeros(N, dtype=np.uint64)
        for i in range(8):
            key |= d[i] << np.uint64(n * i)
        _, c = np.unique(key, return_counts=True)
        p = c.max() / N
        if p > best_dp: best_dp = p; bDdp = D
        # (b) DL single-bit beta
        for bl in range(8):
            dl = d[bl]
            for bb in range(n):
                s = int(((dl >> np.uint64(bb)) & np.uint64(1)).sum())
                corr = abs(1.0 - 2.0 * s / N)
                if corr > best_dl: best_dl = corr; bDdl = (D, ('bit', bl, bb))
        # (b') DL low-weight beta
        for _ in range(n_betas):
            bm = [0] * 8
            for _ in range(int(rng.integers(1, 4))): bm[int(rng.integers(0, 8))] |= 1 << int(rng.integers(0, n))
            if not any(bm): continue
            pb = np.zeros(N, dtype=np.uint64)
            for i in range(8):
                if bm[i]: pb ^= d[i] & np.uint64(bm[i])
            ps = parity64(pb); s = int(ps.sum())
            corr = abs(1.0 - 2.0 * s / N)
            if corr > best_dl: best_dl = corr; bDdl = (D, ('lw', tuple(bm)))
    return best_dp, bDdp, best_dl, bDdl

# ---------------- (2) straight best linear |corr| ----------------
def best_lin(perm, M, n, R, N, seed, n_masks=800):
    rng = np.random.default_rng(seed)
    state = [rng.integers(0, M + 1, size=N, dtype=np.uint64) for _ in range(8)]
    out = perm(state, R)
    inv = 1.0 / N; best = 0.0
    # vectorized: build all single-bit in parities and out parities, corr matrix
    Pin = []; Pout = []
    for il in range(8):
        for ib in range(n):
            am = np.uint64(1 << ib)
            Pin.append(1 - 2 * parity64(state[il] & am).astype(np.float32))
            Pout.append(1 - 2 * parity64(out[il] & am).astype(np.float32))
    Pin = np.array(Pin); Pout = np.array(Pout)
    C = (Pin @ Pout.T) * inv
    best = float(np.max(np.abs(C)))
    # low-weight random masks (vectorized parity per mask)
    for _ in range(n_masks):
        am = [0] * 8; bm = [0] * 8
        for _ in range(int(rng.integers(1, 4))): am[int(rng.integers(0, 8))] |= 1 << int(rng.integers(0, n))
        for _ in range(int(rng.integers(1, 4))): bm[int(rng.integers(0, 8))] |= 1 << int(rng.integers(0, n))
        if not any(am) or not any(bm): continue
        pa = np.zeros(N, dtype=np.uint64); pb = np.zeros(N, dtype=np.uint64)
        for i in range(8):
            if am[i]: pa ^= state[i] & np.uint64(am[i])
            if bm[i]: pb ^= out[i] & np.uint64(bm[i])
        p = parity64(pa ^ pb); s = int(p.sum())
        corr = abs(2.0 * (N - s) / N - 1.0)
        if corr > best: best = corr
    return best

# ---------------- (3) best Differential-Linear correlation ----------------
def best_dl(perm, M, n, deltas, R, N, seed, n_betas=400):
    """For each delta, compute output XOR-diff D = P_R(x) ^ P_R(x^delta);
       DL corr for mask beta = E[(-1)^{beta.D}].  Search beta over single-bit + low-weight.
       Vectorized single-bit beta scan: per lane, count column parities at once."""
    rng = np.random.default_rng(seed)
    best = 0.0; binfo = None
    bit_w = np.array([1 << b for b in range(n)], dtype=np.uint64)
    for D in deltas:
        x = [rng.integers(0, M + 1, size=N, dtype=np.uint64) for _ in range(8)]
        y = [x[i] ^ np.uint64(D[i]) for i in range(8)]
        ox = perm(x, R); oy = perm(y, R)
        d = [(ox[i] ^ oy[i]) & np.uint64(M) for i in range(8)]  # output difference lanes
        # single-bit beta exhaustive, vectorized per lane:
        # E[(-1)^{bit b of d[lane]}] = 1 - 2*mean(bit). bit = (d>>b)&1.
        for bl in range(8):
            dl = d[bl]
            # mean of each bit: popcount per bit position
            for bb in range(n):
                s = int(((dl >> np.uint64(bb)) & np.uint64(1)).sum())
                corr = abs(1.0 - 2.0 * s / N)
                if corr > best:
                    best = corr; binfo = (D, ('bit', bl, bb))
        # low-weight beta random (fewer, this is secondary)
        for _ in range(n_betas):
            bm = [0] * 8
            for _ in range(int(rng.integers(1, 4))): bm[int(rng.integers(0, 8))] |= 1 << int(rng.integers(0, n))
            if not any(bm): continue
            pb = np.zeros(N, dtype=np.uint64)
            for i in range(8):
                if bm[i]: pb ^= d[i] & np.uint64(bm[i])
            p = parity64(pb); s = int(p.sum())
            corr = abs(1.0 - 2.0 * s / N)
            if corr > best:
                best = corr; binfo = (D, ('lw', tuple(bm)))
    return best, binfo

def fmt(x):
    return f"2^-{-math.log2(x):.2f}" if x > 0 else "0"

if __name__ == "__main__":
    n = 8
    a, b = 8 % n, 9 % n   # = 0,1 (matches verify_n8_slope reduced framing)
    red = 0x1D
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1 << 22
    Rmax = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    perm, M = make_round(n, a, b, red, SIGK)
    full_d = (len(sys.argv) <= 3) or (sys.argv[3] != "worst")
    deltas = delta_classes(n, full=full_d)
    floor = 1.0 / math.sqrt(N)
    print(f"### yttrium-LM reduced n={n} w=8 (state {n*8}-bit), (a,b)=({a},{b}), all-8 sigma ###")
    print(f"# N={N}=2^{math.log2(N):.0f}  DP floor~2^-{math.log2(N):.0f}  corr floor~2^-{-math.log2(floor):.1f}")
    print(f"# {len(deltas)} delta classes (MSB-pairs + single bits)\n")

    print("R | straight-bestDP | straight-bestLIN | best-DL-corr | DL vs DP (deeper if DL>floor where DP<=floor)")
    Rmin = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    pdp = plin = pdl = None
    for R in range(Rmin, Rmax + 1):
        bdp, _, bdl, info = best_dp_dl(perm, M, n, deltas, R, N, seed=100 + R)
        blin = best_lin(perm, M, n, R, N, seed=200 + R)
        sdp = "" if pdp is None else f" (dW={-math.log2(bdp)+math.log2(pdp):+.2f})"
        sdl = "" if pdl is None else f" (dW={-math.log2(bdl)+math.log2(pdl):+.2f})"
        print(f"R={R}: DP={fmt(bdp)}{sdp} | LIN={fmt(blin)} | DL={fmt(bdl)}{sdl}", flush=True)
        pdp, plin, pdl = bdp, blin, bdl
    print(f"\n# DL info last R best: {info}")
    print(f"# floor: DP=2^-{math.log2(N):.0f}, corr=2^-{-math.log2(floor):.1f}. Values at floor are upper bounds (true smaller).")
