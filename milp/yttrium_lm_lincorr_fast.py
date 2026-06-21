#!/usr/bin/env python3
"""
yttrium-LM 전체 라운드 best 선형 상관 — 축소폭, 벡터화 경험적 측정 (빠른판).
패리티를 bit-trick(XOR-fold)으로 벡터화. n=16 으로 실제 회전 (a,b)=(8,9) 보존.
정직: 경험적 상한, floor=1/sqrt(Nsamp). 절대 hull 아님.
"""
import numpy as np

PI = [7,4,1,6,3,0,5,2]
EPS = [1,-1,1,-1,1,-1,1,-1]
RC = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
      0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3]

def scale_terms(terms32, n):
    out = []
    for k in terms32:
        kk = max(1, round(k * n / 32)) % n
        if kk == 0: kk = 1
        out.append(kk)
    return out

def parity64(x):
    # x: uint array; return parity (0/1) via XOR-fold (works up to 64-bit)
    x = x ^ (x >> np.uint64(32))
    x = x ^ (x >> np.uint64(16))
    x = x ^ (x >> np.uint64(8))
    x = x ^ (x >> np.uint64(4))
    x = x ^ (x >> np.uint64(2))
    x = x ^ (x >> np.uint64(1))
    return (x & np.uint64(1)).astype(np.int8)

def make_perm(n, w, red, sigk, a, b, terms):
    M = np.uint64((1 << n) - 1)
    Mpy = (1 << n) - 1
    def rotl(x, k):
        k %= n
        if k == 0: return x
        return ((x << np.uint64(k)) | (x >> np.uint64(n-k))) & M
    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)
    redv = np.uint64(red)
    def alpha(x):
        top = (x >> np.uint64(n-1)) & np.uint64(1)
        return ((x << np.uint64(1)) & M) ^ np.where(top == 1, redv, np.uint64(0))
    def alfp(x, k):
        for _ in range(k):
            x = alpha(x)
        return x
    def Fvec(s):
        acc = np.zeros_like(s)
        for i in range(0, len(terms), 2):
            acc ^= rotl(s, terms[i]) & rotl(s, terms[i+1])
        return s ^ acc
    def perm(state, R):
        ws = [state[i].copy() for i in range(w)]
        for r in range(R):
            ws[r % 8] = ws[r % 8] ^ np.uint64(RC[r % len(RC)] & Mpy)
            xp = [rotl(ws[i], a) for i in range(w)]
            S = np.zeros_like(ws[0])
            for i in range(w):
                S = (S + xp[i]) & M if EPS[i] > 0 else (S - xp[i]) & M
            t = Fvec(S)
            y = [rotr((xp[i] + t) & M, b) for i in range(w)]
            for i in range(w):
                if sigk[i]:
                    y[i] = alfp(y[i], sigk[i])
            ws = [y[PI[i]] for i in range(w)]
        return ws
    return perm, Mpy

def best_corr(perm, n, w, R, Nsamp, n_masks, rng):
    Mpy = (1 << n) - 1
    state = [rng.integers(0, 1 << n, size=Nsamp, dtype=np.uint64) for _ in range(w)]
    out = perm(state, R)
    # precompute per-lane state/out as is
    best = 0.0; info = None
    inv = 1.0 / Nsamp
    for _ in range(n_masks):
        amask = [0]*w; bmask = [0]*w
        na = int(rng.integers(1, 4)); nb = int(rng.integers(1, 4))
        for _ in range(na):
            amask[int(rng.integers(0,w))] |= (1 << int(rng.integers(0,n)))
        for _ in range(nb):
            bmask[int(rng.integers(0,w))] |= (1 << int(rng.integers(0,n)))
        if not any(amask) or not any(bmask):
            continue
        pa = np.zeros(Nsamp, dtype=np.uint64)
        for i in range(w):
            if amask[i]:
                pa ^= state[i] & np.uint64(amask[i])
        pb = np.zeros(Nsamp, dtype=np.uint64)
        for i in range(w):
            if bmask[i]:
                pb ^= out[i] & np.uint64(bmask[i])
        p = parity64(pa ^ pb)
        s = int(p.sum())  # number of 1s
        corr = abs(2.0 * (Nsamp - s) * inv - 1.0)  # agree = Nsamp - s (p=0 means a·x = b·y)
        if corr > best:
            best = corr; info = (amask, bmask)
    return best, info

if __name__ == "__main__":
    import sys
    rng = np.random.default_rng(2024)
    n = 16; w = 8; a, b = 8, 9
    sigk = [1,2,3,5,7,11,13,17]
    terms = scale_terms([7,17,3,21,9,29], n)
    perm, Mpy = make_perm(n, w, red=0x1002D, sigk=sigk, a=a, b=b, terms=terms)  # primitive-ish red for n=16
    Nsamp = 1 << 18  # 256K -> floor ~2^-9
    floor = 1.0/np.sqrt(Nsamp)
    print(f"reduced n={n} w={w} state={n*w}bit (a,b)=({a},{b}) all-8 σ k={sigk}", flush=True)
    print(f"terms(rot)={terms}; Nsamp=2^{int(np.log2(Nsamp))} floor=2^-{-np.log2(floor):.1f}", flush=True)
    print("저무게 마스크(1~3레인 single-bit) 경험적 best |corr|. 절대경계 아님.\n", flush=True)
    Rmax = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for R in range(1, Rmax+1):
        nm = 2000 if R <= 2 else 4000
        best, inf = best_corr(perm, n, w, R, Nsamp, nm, rng)
        wt = -np.log2(best) if best > 0 else float('inf')
        flag = "  <= noise floor (실제 더 작음)" if best <= floor*2.5 else ""
        print(f"  R={R}: best |corr| ~ {best:.6f} = 2^-{wt:.2f}{flag}", flush=True)
