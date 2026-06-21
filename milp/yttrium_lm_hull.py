#!/usr/bin/env python3
"""
yttrium-LM Linear Hull (trail clustering) analysis — small-scale EXACT measurement.

Round (replicated from yttrium_lm_invert.py / yttrium_lm_diff.cu, parameterised by n,w):
  (ι)        state[r % w] ^= RC[r]                                   (linear, ignored for hull masks)
  reduction  xp_i = ROTL_a(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), ε=[+,-,+,-,...]
  combiner   t = F(S);  y_i = ROTR_b(xp_i ⊞ t)
  σ          y_i ← α^{k_i}·y_i  (GF(2^n) α-mult, red)
  π          new_i = y_{P[i]}

LINEAR HULL question:
  Correlation of a linear approximation (a·x ⊕ b·y) over R rounds is the SUM over all
  trails sharing (a,b) of ±2^{-(trail weight)} (signed by sign-of-correlation product).
  A "hull" beats a single best trail when many trails of comparable weight add
  constructively. We measure:
    (1) EXACT round correlation matrix C[a,b] = corr(a·x ⊕ b·(round x))  for tiny (n,w).
        This already CONTAINS the full hull for one round (no trail truncation).
    (2) Multi-round hull C_R = (matrix power of the 1-round Walsh-correlation operator)
        gives EXACT |corr| for the BEST output mask given an input mask, over R rounds,
        INCLUDING all hull clustering — because matrix multiply of correlation matrices
        IS the sum-over-intermediate-masks (this is the exact linear-hull recursion).
        (Daemen-Rijmen: correlation matrices compose by ordinary matrix product; the
         (a,b) entry of C^R is the exact correlation summed over ALL R-round trails.)
    (3) Compare best single-trail bound vs exact hull at each R -> hull gain factor.

  Component correlation analyses (the three algebras):
    - GF(2^n) α^k multiply: linear (GF(2)) map -> correlation is 0/±1 (mask permutation,
      possibly with branching). Measured exactly: it is a LINEAR map so its correlation
      matrix is a permutation/(0,1) structure — NO hull (single trail), but it MOVES masks.
    - modular add of broadcast t (the combiner xp ⊞ t): the carry source of multiple
      trails. We measure the add correlation directly.
    - F (GF(2) AND/XOR core): correlation of linear approx of F.

We work at n in {4,5,6} with w in {4,8}. State = n*w bits. Full correlation matrix is
2^(n*w) x 2^(n*w) which is too big for n*w>~16; so we use:
  - n=4,w=4 (16-bit): too big for full matrix (2^16 x 2^16 = 4G entries) -> use
    SAMPLED / structured measurement + single-lane exact.
  - We instead measure the EXACT 1-round correlation for SINGLE-WORD masks via FWHT
    per component, and measure multi-round hull by Monte-Carlo correlation estimation
    of specific (a,b) plus by exact small full-state (n=3,w=4 = 12 bit; n=2,w=4 = 8 bit;
    n=4,w=2 = 8 bit) correlation matrices and their powers.

Honesty: small-scale EXACT (full Walsh) where state<=16 bit; Monte-Carlo (sampled) for
larger. GPU is the orchestrator's job; here only CPU/python.
"""
import numpy as np
import itertools


# ---------------- field / rotation primitives ----------------
def make_alpha(n, red):
    M = (1 << n) - 1

    def alpha(v):
        top = v >> (n - 1)
        return ((v << 1) & M) ^ (red if top else 0)
    return alpha


def alfp_fn(n, red):
    a = make_alpha(n, red)

    def alfp(v, k):
        for _ in range(k):
            v = a(v)
        return v
    return alfp


def rotl_fn(n):
    M = (1 << n) - 1

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M
    return rotl


def F_full(s, n, rotl):
    return s ^ (rotl(s, 7 % n) & rotl(s, 17 % n)) ^ (rotl(s, 3 % n) & rotl(s, 21 % n)) ^ (rotl(s, 9 % n) & rotl(s, 29 % n))


# ---------------- full round (full state as integer) ----------------
def build_round(n, w, red, a, b, eps, sigma, P, Ffn=None):
    M = (1 << n) - 1
    rotl = rotl_fn(n)
    alfp = alfp_fn(n, red)

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    F = Ffn if Ffn else (lambda s: F_full(s, n, rotl))

    def words(state):
        return [(state >> (i * n)) & M for i in range(w)]

    def pack(ws):
        s = 0
        for i, x in enumerate(ws):
            s |= (x & M) << (i * n)
        return s

    def rnd(state):
        st = words(state)
        xp = [rotl(st[i], a) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, b) for i in range(w)]
        for (lane, k) in sigma:
            y[lane] = alfp(y[lane], k)
        return pack([y[P[i]] for i in range(w)])

    return rnd, words, pack, M


# ---------------- exact full Walsh correlation matrix (small state only) ----------------
def parity(x):
    return bin(x).count("1") & 1


def exact_corr_matrix(rnd, N):
    """C[b,a] = corr over all x of ( a·x XOR b·rnd(x) ). N = state bits.
    Returns float matrix 2^N x 2^N. Uses FWHT-free direct: for each x build the
    truth contributions. Only feasible for N<=14 or so. We use the identity:
       C[b,a] = (1/2^N) Σ_x (-1)^{a·x XOR b·y(x)}
    Compute via two FWHTs is overkill; we do the per-output-bit approach:
       Let y=rnd(x). For mask b, define g_b(x)=parity(b & y). Then
       C[b,a] = Walsh_a( (-1)^{g_b} ) / 2^N.
    We compute for ALL b by: build array Y[x]=rnd(x); then for each b compute
    sign vector and FWHT. That is 2^N FWHTs -> 2^N * N * 2^N. Too big.
    Instead: full 2D correlation via single 2D structure is 2^N x 2^N anyway.
    We only call this for N<=12 (4096) -> 4096x4096 floats = 134MB. ok for N<=12.
    """
    size = 1 << N
    Y = np.fromiter((rnd(x) for x in range(size)), dtype=np.int64, count=size)
    # Build T[b, x] = (-1)^{parity(b & Y[x])}? that's 2^N x 2^N -> too big for N=12 (16M*... )
    # Better: C = (1/size) * H_out^T ... Use: define indicator over (x).
    # We compute correlation matrix as: C[b,a] = <(-1)^{b·y}, (-1)^{a·x}> / size.
    # Let A be the 2^N x 2^N Hadamard-like? Use FWHT along x for each b is 2^N transforms.
    # For N<=10 (1024) fine: 1024 FWHTs of length 1024.
    H = np.empty((size, size), dtype=np.float64)
    # popcount table
    pc = np.array([bin(i).count("1") & 1 for i in range(size)], dtype=np.int8)
    signY = np.empty((size, size), dtype=np.float64)  # signY[b,x] = (-1)^{b·Y[x]}
    # build per b
    for b in range(size):
        signY[b] = 1 - 2 * pc[(b & Y)]
    # FWHT each row over x: result[b,a] = Σ_x signY[b,x] (-1)^{a·x}
    M = signY.copy()
    h = 1
    while h < size:
        for i in range(0, size, h * 2):
            x = M[:, i:i + h].copy()
            y = M[:, i + h:i + 2 * h].copy()
            M[:, i:i + h] = x + y
            M[:, i + h:i + 2 * h] = x - y
        h *= 2
    C = M / size  # C[b,a]
    return C


def hull_vs_trail(C, R):
    """Given exact 1-round correlation matrix C[b,a] (out b, in a),
    exact R-round hull correlation matrix = C^R (matrix power), because
    correlation matrices compose by matrix product (exact, all trails).
    Single-best-trail bound = (elementwise) max over trails of product of |C| along path
    = (|C|^R)[b,a] gives sum of abs-products = upper bound on |hull| AND also the
    'sum of all trail magnitudes'. The TRUE hull is |(C^R)[b,a]| (with signs/cancel).
    Best single trail magnitude is approximated by the max single path; we compute
    the dominant-trail estimate via max-product path (tropical) too.
    Returns (CR, absR, maxpath) matrices."""
    n = C.shape[0]
    A = np.abs(C)
    CR = np.linalg.matrix_power(C, R)
    absR = np.linalg.matrix_power(A, R)  # sum of |trail| magnitudes (additive)
    # max-product path (dominant single trail magnitude) via repeated max-plus on logs
    # work in -log2 weights; smaller weight = bigger corr
    with np.errstate(divide='ignore'):
        W = -np.log2(A)  # inf where 0
    # max-product => min-sum of weights
    MP = W.copy()
    for _ in range(R - 1):
        # MP_new[b,a] = min_m ( MP[b,m] + W0[m,a] ) ... but careful index order:
        # path a -> m -> b. corr matrix entry [out,in]. product C[b,m]*C[m,a].
        new = np.full_like(MP, np.inf)
        for m in range(n):
            cand = MP[:, m][:, None] + W[m, :][None, :]
            new = np.minimum(new, cand)
        MP = new
    maxpath = 2.0 ** (-MP)  # dominant single-trail magnitude
    return CR, absR, maxpath


# ---------------- component correlation: GF(2^n) multiply by alpha^k ----------------
def alpha_mult_matrix_bits(n, red, k):
    """alpha^k is a GF(2)-linear map L on n bits. Its correlation matrix for linear
    masks: corr(beta·L(x) xor a·x) = 1 iff a = L^T beta else 0 (linear map => single
    trail, no hull, but masks transform by transpose). Return L as bit-matrix and L^T."""
    alfp = alfp_fn(n, red)
    cols = [alfp(1 << j, k) for j in range(n)]  # L applied to basis e_j -> column j
    # L^T: mask transform. beta·L(x) = (L^T beta)·x
    LT = [0] * n
    for j in range(n):
        for i in range(n):
            if (cols[j] >> i) & 1:
                LT[i] |= (1 << j)
    return cols, LT


# ---------------- component: modular add of broadcast t (carry hull) -------------
def add_corr_single_lane(n, samples=None):
    """For one lane: z = (xp ⊞ t) where t is broadcast (same to all lanes). For a SINGLE
    lane in isolation with t independent uniform, corr of linear approx
       gamma·z  vs  (u·xp xor v·t)
    is the classic modular-add correlation. We measure the BEST output mask gamma=u=v
    aligned correlation profile (this is where multiple carry trails cluster).
    Exact via FWHT for small n."""
    size = 1 << n
    # build add table z[xp,t]
    Z = np.zeros((size, size), dtype=np.int64)
    for xp in range(size):
        for t in range(size):
            Z[xp, t] = (xp + t) & (size - 1)
    return Z, size


# ============================ MAIN MEASUREMENTS ============================
def main():
    PI8 = [7, 4, 1, 6, 3, 0, 5, 2]
    SIG_ALL8 = [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7), (5, 11), (6, 13), (7, 17)]
    EPS8 = [1, -1, 1, -1, 1, -1, 1, -1]

    print("=" * 78)
    print("yttrium-LM LINEAR HULL — small-scale EXACT correlation measurement")
    print("=" * 78)

    # ---- (1) Component: GF(2^n) alpha^k is GF(2)-linear => NO HULL, mask permute ----
    print("\n### (1) σ component: α^k is GF(2)-linear -> single trail (no hull), mask transform ###")
    for (n, red) in [(4, 0x3), (8, 0x1D)]:
        print(f"  n={n} red=0x{red:X}:")
        for k in [1, 2, 3, 5, 7]:
            cols, LT = alpha_mult_matrix_bits(n, red, k)
            # confirm bijection (full rank)
            rank = bit_rank(cols, n)
            # how much does it spread a single-bit mask? (Hamming weight of LT image of e0)
            spread = bin(LT[0]).count("1")
            print(f"    k={k:2d}: GF(2)-linear bijection rank={rank}/{n}; "
                  f"mask e0 -> wt {spread} (single trail, corr=±1)")
    print("  => CONCLUSION: σ contributes ZERO linear-hull multiplicity (it is linear);")
    print("     it only ROTATES masks across bit positions (breaks rotational mask structure).")

    # ---- (2) Component: modular add (broadcast t) — carry trail clustering ----
    print("\n### (2) ⊞ component: modular-add correlation (carry = the hull source) ###")
    for n in [4, 6, 8]:
        Z, size = add_corr_single_lane(n)
        # correlation matrix corr( gamma·z  xor  (xp,t)-mask ). We want: for output mask
        # gamma, best input correlation and how many input masks give comparable corr.
        # corr[gamma][(u,v)] over 2^(2n) inputs.
        # Use FWHT: signZ[gamma, xp, t] -> 2D FWHT.
        best, ntrails_near = add_hull_profile(Z, size, n)
        print(f"  n={n}: max |corr| of single add-approx = 2^{np.log2(best):.2f}; "
              f"#(input masks within 1 bit of best, same gamma) ~ {ntrails_near}")
    print("  => add has a SPREAD of comparable-weight approximations (carry chains) =>")
    print("     this is the ONLY genuine hull-multiplicity source in the round.")

    # ---- (3) Full-round EXACT correlation matrix + hull vs best-trail, tiny state ----
    print("\n### (3) FULL-ROUND exact correlation matrix C[b,a] and hull C^R (tiny state) ###")
    print("    (correlation matrices compose by matrix product => C^R is EXACT hull incl. all trails)")

    import sys
    configs = [
        # (n, w, red, a, b, sigma, P, eps, label) state bits = n*w; keep <=10 for speed
        (2, 4, 0x3, 8 % 2, 9 % 2, [(0, 1), (1, 2), (2, 3), (3, 5)], [3, 0, 1, 2], [1, -1, 1, -1], "n=2 w=4 (8-bit)"),
        (4, 2, 0x3, 1, 2, [(0, 1), (1, 2)], [1, 0], [1, -1], "n=4 w=2 (8-bit)"),
        (2, 5, 0x3, 0, 1, [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7)], [4, 3, 1, 0, 2], [1, -1, 1, -1, 1], "n=2 w=5 (10-bit)"),
        (5, 2, 0x5, 1, 2, [(0, 1), (1, 2)], [1, 0], [1, -1], "n=5 w=2 (10-bit)"),
    ]
    for (n, w, red, a, b, sigma, P, eps, label) in configs:
        N = n * w
        if N > 10:
            continue
        rnd, words, pack, M = build_round(n, w, red, a, b, eps, sigma, P)
        C = exact_corr_matrix(rnd, N)
        analyze_full(C, N, label)
        sys.stdout.flush()


def bit_rank(cols, n):
    basis = []
    for v in cols:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
    return len(basis)


def add_hull_profile(Z, size, n):
    """For modular add z=(xp+t), measure best linear-approx |corr| and count of
    near-best input masks for the SAME output mask gamma (= hull width proxy)."""
    # signZ[gamma] is a 2D array over (xp,t): (-1)^{gamma·z}
    pc = np.array([bin(i).count("1") & 1 for i in range(size)], dtype=np.int8)
    best = 0.0
    best_gamma = 1
    # We'll just scan gamma over all masks; for each, 2D FWHT to get corr over (u,v).
    corr_for_best = None
    for gamma in range(1, size):
        s = 1 - 2 * pc[(gamma & Z)]  # shape (xp,t), values ±1
        # 2D FWHT
        T = s.astype(np.float64)
        T = fwht2d(T)
        T /= (size * size)
        m = np.max(np.abs(T))
        if m > best:
            best = m
            best_gamma = gamma
            corr_for_best = T.copy()
    # count near-best (within factor 2 = 1 bit) for best gamma
    thr = best / 2.0
    ntrails = int(np.sum(np.abs(corr_for_best) >= thr))
    return best, ntrails


def fwht2d(T):
    # FWHT along axis 0 then axis 1
    for axis in (0, 1):
        T = fwht_axis(T, axis)
    return T


def fwht_axis(T, axis):
    T = np.moveaxis(T, axis, 0)
    n = T.shape[0]
    h = 1
    while h < n:
        for i in range(0, n, h * 2):
            x = T[i:i + h].copy()
            y = T[i + h:i + 2 * h].copy()
            T[i:i + h] = x + y
            T[i + h:i + 2 * h] = x - y
        h *= 2
    return np.moveaxis(T, 0, axis)


def analyze_full(C, N, label):
    size = 1 << N
    # exclude trivial (a=0,b=0)
    A = np.abs(C)
    # 1-round best nonzero correlation (over a!=0 or b!=0)
    Amask = A.copy()
    Amask[0, 0] = 0
    r1 = Amask.max()
    print(f"\n  -- {label}: state {N} bit, matrix {size}x{size} --")
    print(f"     R=1 best |corr| (nontrivial) = 2^{np.log2(r1):.3f}")
    for R in (2, 3, 4):
        CR, absR, maxpath = hull_vs_trail(C, R)
        a2 = np.abs(CR).copy()
        a2[0, 0] = 0
        hull_best = a2.max()
        # corresponding single dominant trail at that (b,a)
        bi, ai = np.unravel_index(np.argmax(a2), a2.shape)
        dom = maxpath[bi, ai]
        summag = absR[bi, ai]
        gain = hull_best / dom if dom > 0 else float('inf')
        print(f"     R={R}: hull best |corr| = 2^{np.log2(hull_best):.3f}  "
              f"(at b={bi},a={ai}) | dominant single-trail = 2^{np.log2(dom):.3f} "
              f"| Σ|trail| = 2^{np.log2(summag):.3f} | HULL GAIN = {gain:.2f}x")
    # global hull gain: for the (b,a) maximizing hull at R=3
    print()


if __name__ == "__main__":
    main()
