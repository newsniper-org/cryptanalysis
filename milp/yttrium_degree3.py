#!/usr/bin/env python3
"""
yttrium-LM 차수성장 — 더 큰 N(=16,18,20)까지. 정확 Möbius(빠른 reshape 버전).
초점: min_deg(출력비트 중 최저 ANF차수)가 N-1 에 도달하는 R (=integral/cube 소멸).
또한 라운드별 (R1 차수, R2, ...) 의 N-의존성으로 풀폭 외삽 근거 확보.
"""
import numpy as np
from yttrium_degree2 import make_round


def fast_mobius(tt, N):
    """tt: uint8 array length 2^N. in-place GF(2) Möbius via reshape butterfly."""
    a = tt.reshape([2] * N)
    for axis in range(N):
        # a[...,1,...] ^= a[...,0,...] along this axis
        idx1 = [slice(None)] * N
        idx0 = [slice(None)] * N
        idx1[axis] = 1
        idx0[axis] = 0
        a[tuple(idx1)] ^= a[tuple(idx0)]
    return a.reshape(-1)


def degrees(n, w, red, sig_k, P, A, B, eps, Rmax, verbose=True):
    N = n * w
    rnd, M = make_round(n, w, red, sig_k, P, A, B, eps)
    size = 1 << N
    cur = np.arange(size, dtype=np.int64)
    popc = np.zeros(size, dtype=np.int16)
    # popcount table
    for k in range(N):
        popc[(np.arange(size) >> k) & 1 == 1] += 1
    out = []
    bij = True
    for R in range(1, Rmax + 1):
        nxt = np.empty(size, dtype=np.int64)
        for x in range(size):
            st = int(cur[x])
            ws = [(st >> (i * n)) & M for i in range(w)]
            ws2 = rnd(ws)
            v = 0
            for i in range(w):
                v |= (ws2[i] & M) << (i * n)
            nxt[x] = v
        cur = nxt
        if np.unique(cur).size != size:
            bij = False
        maxd, mind = 0, N
        for b in range(N):
            tt = ((cur >> b) & 1).astype(np.uint8)
            coeff = fast_mobius(tt, N)
            nz = np.nonzero(coeff)[0]
            d = int(popc[nz].max()) if nz.size else 0
            maxd = max(maxd, d)
            mind = min(mind, d)
        out.append((maxd, mind))
        if verbose:
            print(f"  R={R}: max_deg={maxd:3d}  min_deg={mind:3d}  bij={bij}  (N-1={N-1})")
    return out, N, bij


if __name__ == "__main__":
    import sys
    PRIM = {4: 0x3, 5: 0x5, 6: 0x3, 7: 0x3, 8: 0x1d}
    configs = [
        ("w2 n8", 8, 2, [1, 2], [1, 0], 8, 9, [1, -1]),
        ("w3 n6", 6, 3, [1, 2, 3], [2, 0, 1], 3, 4, [1, -1, 1]),  # Sum eps=1 != 0 -> non-bij? handle
        ("w4 n5", 5, 4, [1, 2, 3, 1], [3, 0, 1, 2], 2, 3, [1, -1, 1, -1]),
    ]
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for (lab, n, w, sk, P, A, B, eps) in configs:
        if which != "all" and which not in lab:
            continue
        print(f"== {lab}: N={n*w} ==")
        degrees(n, w, PRIM[n], sk, P, A, B, eps, 6)
        print()
