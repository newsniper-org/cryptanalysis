#!/usr/bin/env python3
"""
yttrium-LM Rotational / Rotational-XOR (RX) 정밀 분석 — 소규모 직접측정 (GPU 금지).

라운드 함수 (yttrium_lm_diff.cu / yttrium_round_decay.cu 와 bit-동일, RC ι 옵션):
  (ι)        state[r mod w] ^= RC[r]           (비반복 SHA256_K)
  reduction  xp_i = ROTL_A(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), ε=[+,-,+,-,+,-,+,-]
  combiner   t = F(S);  y_i = ROTR_B(xp_i ⊞ t)     (A,B)=(8,9)
  σ          y_i ← α^{k_i}·y_i  (GF(2^n) red), k=[1,2,3,5,7,11,13,17]
  π          new_i = y_{P[i]}

RX 모델: rotational pair (x, ROTL_γ(x)); RX-pair (x, ROTL_γ(x)⊕δ).
  RX-prob = Pr_x[ R^R(ROTL_γ(x)⊕δin) == ROTL_γ(R^R(x)) ⊕ δout ].

numpy 벡터화 (n=32 uint32, n=16 uint32 mask) — 빠른 대량 샘플.
정직: best RX-prob 는 경험적 상한(증명 아님). n<32 는 축소판.
"""
import sys
import math
import numpy as np

def log(*a):
    print(*a); sys.stdout.flush()

# ---------------- 벡터화 라운드 (n=32 또는 n=16 마스크) ----------------
class Yttrium:
    def __init__(self, n, red, A, B, eps, sig_k, P, terms, RC=None):
        self.n = n; self.M = (np.uint64(1) << np.uint64(n)) - np.uint64(1)
        self.Mpy = (1 << n) - 1
        self.red = red; self.A = A; self.B = B
        self.eps = eps; self.sig_k = sig_k; self.P = P; self.terms = terms; self.RC = RC
        self.w = len(eps)

    def rotl(self, x, k):
        n = self.n; k %= n
        if k == 0:
            return x
        M = self.Mpy
        return ((x << np.uint64(k)) | (x >> np.uint64(n - k))) & np.uint64(M)

    def rotr(self, x, k):
        return self.rotl(x, (self.n - (k % self.n)) % self.n)

    def alpha_once(self, v):
        # v: uint64 array, value < 2^n
        n = self.n; M = self.Mpy
        top = (v >> np.uint64(n - 1)) & np.uint64(1)
        out = ((v << np.uint64(1)) & np.uint64(M)) ^ (top * np.uint64(self.red))
        return out

    def alfp(self, v, k):
        for _ in range(k):
            v = self.alpha_once(v)
        return v

    def F(self, s):
        acc = np.zeros_like(s)
        t = self.terms
        for j in range(0, len(t), 2):
            acc ^= self.rotl(s, t[j]) & self.rotl(s, t[j + 1])
        return s ^ acc

    def round(self, state, r=0):
        # state: list of w uint64 arrays (each value < 2^n)
        n = self.n; M = self.Mpy
        st = list(state)
        if self.RC is not None:
            idx = r % self.w
            st[idx] = st[idx] ^ np.uint64(self.RC[r % len(self.RC)])
        xp = [self.rotl(st[i], self.A) for i in range(self.w)]
        S = np.zeros_like(st[0])
        for i in range(self.w):
            if self.eps[i] > 0:
                S = (S + xp[i]) & np.uint64(M)
            else:
                S = (S - xp[i]) & np.uint64(M)
        t = self.F(S)
        y = [self.rotr((xp[i] + t) & np.uint64(M), self.B) for i in range(self.w)]
        for lane, k in enumerate(self.sig_k):
            if k:
                y[lane] = self.alfp(y[lane], k)
        return [y[self.P[i]] for i in range(self.w)]

    def runR(self, state, R):
        cur = state
        for r in range(R):
            cur = self.round(cur, r)
        return cur

# ---------------- RX 확률 측정 ----------------
def rx_prob(Y, gamma, delta_in, delta_out, R, N, seed=0):
    n = Y.n; M = Y.Mpy; w = Y.w
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << n, size=N, dtype=np.uint64) for _ in range(w)]
    xr = [(Y.rotl(x[i], gamma) ^ np.uint64(delta_in[i])) for i in range(w)]
    cx = Y.runR([a.copy() for a in x], R)
    cxr = Y.runR([a.copy() for a in xr], R)
    match = np.ones(N, dtype=bool)
    for i in range(w):
        target = Y.rotl(cx[i], gamma) ^ np.uint64(delta_out[i])
        match &= (cxr[i] == target)
    return int(match.sum()) / N

def search_rx_gamma(Y, R, gammas, N, seed=0):
    w = Y.w; zero = [0] * w
    best = (0.0, None)
    for g in gammas:
        if g == 0:
            continue
        p = rx_prob(Y, g, zero, zero, R, N, seed=seed)
        if p > best[0]:
            best = (p, g)
    return best

# ---------------- op-level (정확, 전수 n=8) ----------------
def alpha_exhaustive_commute(n, red, k, gamma):
    M = (1 << n) - 1
    def rotl(v, g):
        g %= n
        return ((v << g) | (v >> (n - g))) & M if g else v
    def alpha(v):
        top = v >> (n - 1)
        return ((v << 1) & M) ^ (red if top else 0)
    def alfp(v):
        for _ in range(k):
            v = alpha(v)
        return v
    tot = 1 << n
    ok = sum(1 for v in range(tot) if alfp(rotl(v, gamma)) == rotl(alfp(v), gamma))
    return ok / tot

def alpha_sample_commute(n, red, k, gamma, N, seed=2):
    M = (1 << n) - 1
    rng = np.random.default_rng(seed)
    v = rng.integers(0, 1 << n, size=N, dtype=np.uint64)
    def rotl(x, g):
        g %= n
        if g == 0:
            return x
        return ((x << np.uint64(g)) | (x >> np.uint64(n - g))) & np.uint64(M)
    def alpha(x):
        top = (x >> np.uint64(n - 1)) & np.uint64(1)
        return ((x << np.uint64(1)) & np.uint64(M)) ^ (top * np.uint64(red))
    def alfp(x):
        for _ in range(k):
            x = alpha(x)
        return x
    lhs = alfp(rotl(v, gamma))
    rhs = rotl(alfp(v), gamma)
    return int((lhs == rhs).sum()) / N

def add_rot_prob(n, gamma, N, seed=1):
    M = (1 << n) - 1
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 1 << n, size=N, dtype=np.uint64)
    y = rng.integers(0, 1 << n, size=N, dtype=np.uint64)
    def rotl(v, g):
        g %= n
        if g == 0:
            return v
        return ((v << np.uint64(g)) | (v >> np.uint64(n - g))) & np.uint64(M)
    lhs = rotl((x + y) & np.uint64(M), gamma)
    rhs = (rotl(x, gamma) + rotl(y, gamma)) & np.uint64(M)
    return int((lhs == rhs).sum()) / N


if __name__ == "__main__":
    PI8 = [7, 4, 1, 6, 3, 0, 5, 2]
    EPS8 = [1, -1, 1, -1, 1, -1, 1, -1]
    SIGK_ALL8 = [1, 2, 3, 5, 7, 11, 13, 17]
    SIGK_EMPTY = [0] * 8
    TERMS32 = [7, 17, 3, 21, 9, 29]
    TERMS16 = [7, 17, 3, 21, 9, 29]  # mod 16 inside rotl
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"

    if stage in ("1", "all"):
        log("== [1] α^k vs ROTL_γ commute (n=8 전수; rotational 핵심) ==")
        for k in (1, 2, 3, 17):
            row = []
            for g in (1, 2, 3, 8):
                p = alpha_exhaustive_commute(8, 0x1D, k, g)
                row.append(f"γ={g}:{p:.4f}")
            log(f"  k={k:2d}  " + "  ".join(row))
        log("  α^k(n=32) commute 샘플:")
        for k in (1, 2, 17):
            row = []
            for g in (1, 8):
                p = alpha_sample_commute(32, 0x400007, k, g, 1 << 20)
                lg = -math.log2(max(p, 1e-9))
                row.append(f"γ={g}:p={p:.5f}(-log2={lg:.1f})")
            log(f"  k={k:2d}  " + "  ".join(row))
        log("")

    if stage in ("2", "all"):
        log("== [2] modular-add ⊞ rotational 확률 ==")
        for n in (16, 32):
            row = []
            for g in (1, 2, 8):
                p = add_rot_prob(n, g, 1 << 21)
                lg = -math.log2(max(p, 1e-9))
                row.append(f"γ={g}:{p:.4f}(-log2={lg:.2f})")
            log(f"  n={n}  " + "  ".join(row))
        log("")

    if stage in ("3", "all"):
        log("== [3] 라운드 RX-확률 R=1..6 (순수 rotational δ=0, best γ) n=32 w=8 all-8 σ ==")
        Y32 = Yttrium(32, 0x400007, 8, 9, EPS8, SIGK_ALL8, PI8, TERMS32, RC=None)
        N = 1 << 20
        for R in range(1, 7):
            p, g = search_rx_gamma(Y32, R, list(range(1, 32)), N)
            lg = -math.log2(max(p, 1e-9))
            floor = "  [<=3/N floor]" if p <= 3.0 / N else ""
            log(f"  R={R}: best rot-prob={p:.7f} (γ={g}) -log2={lg:.2f}{floor}")
        log("")

    if stage in ("4", "all"):
        log("== [4] ablation: empty-σ (framing only) vs all-8 σ, n=32 R=1..4 (N=2^18) ==")
        N = 1 << 18
        Ye = Yttrium(32, 0x400007, 8, 9, EPS8, SIGK_EMPTY, PI8, TERMS32, RC=None)
        Ya = Yttrium(32, 0x400007, 8, 9, EPS8, SIGK_ALL8, PI8, TERMS32, RC=None)
        # ablation은 γ=8 (워드정렬, add-friendly) 만 주로 본다 + 작은 γ-sweep
        gammas = [1, 2, 4, 8, 16]
        for R in range(1, 5):
            pe, ge = search_rx_gamma(Ye, R, gammas, N)
            pa, ga = search_rx_gamma(Ya, R, gammas, N)
            lge = -math.log2(max(pe, 1e-9)); lga = -math.log2(max(pa, 1e-9))
            log(f"  R={R}: empty-σ p={pe:.7f}(γ={ge},-log2={lge:.2f})  "
                f"all-8 p={pa:.7f}(γ={ga},-log2={lga:.2f})")
        log("")

    if stage in ("5", "all"):
        # RC 무력화는 σ를 끈 상태에서 isolate 해야 RC효과만 보임 (σ-on이면 σ가 먼저 죽임)
        log("== [5] RC(비반복) 상수보정: empty-σ 에서 RC-on vs RC-off isolate (n=32 R=1..3, N=2^18) ==")
        N = 1 << 18
        RC32 = [0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
                0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5]
        Yon = Yttrium(32, 0x400007, 8, 9, EPS8, SIGK_EMPTY, PI8, TERMS32, RC=RC32)
        Yoff = Yttrium(32, 0x400007, 8, 9, EPS8, SIGK_EMPTY, PI8, TERMS32, RC=None)
        gammas = [1, 2, 4, 8, 16]
        for R in range(1, 4):
            pon, gon = search_rx_gamma(Yon, R, gammas, N)
            poff, goff = search_rx_gamma(Yoff, R, gammas, N)
            lon = -math.log2(max(pon, 1e-9)); loff = -math.log2(max(poff, 1e-9))
            log(f"  R={R}: RC-on p={pon:.7f}(γ={gon},-log2={lon:.2f})  "
                f"RC-off p={poff:.7f}(γ={goff},-log2={loff:.2f})")
        log("")
