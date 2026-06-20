#!/usr/bin/env python3
"""
확률-1 (선형/비활성) 차분의 정확한 경계 — GF(2) 선형대수 (SMT 불필요, timeout 없음).

비활성 라운드는 ΔS=0 ⟹ Δt=F(ΔS)=0 ⟹ 라운드가 *순수 선형* Lin = π∘σ (broadcast 0).
따라서 "R 라운드 내내 F를 회피하는(=확률 1) 비활성 차분"의 집합은
   V_R = { v≠0 : XORsum(Lin^r v) = 0,  r=0..R-1 }
로 정확한 선형 부분공간. dim V_R 를 R별로 구하고, dim=0 이 되는 최소 R = R*
(= 확률-1 선형 차분이 더는 존재하지 않는 라운드 수).

R* 미만의 라운드 수를 쓰는 압축/종결은 *bare 순열* 차원에서 확률-1 선형 차분을
가진다 = 트레일 기반 차분 저항이 확립되지 않음(라운드 수 정당화 미흡).
"""

def make_alpha(n, red):
    def alpha(v):
        top = v >> (n-1)
        return (((v << 1) & ((1<<n)-1)) ^ (red if top else 0))
    return alpha

def lin_factory(n, w, red, sigma, P):
    alpha = make_alpha(n, red)
    def apply_pow(v, k):
        for _ in range(k): v = alpha(v)
        return v
    mask = (1<<n)-1
    def words(state): return [(state>>(i*n))&mask for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s |= (x & mask) << (i*n)
        return s
    def Lin(state):
        ws = words(state)
        for (lane,k) in sigma:
            ws[lane] = apply_pow(ws[lane], k)
        new = [ws[P[i]] for i in range(w)]
        return pack(new)
    def xorsum(state):
        ws = words(state); s=0
        for x in ws: s ^= x
        return s
    return Lin, xorsum

def gf2_rank(cols):
    """rank of list of column-integers over GF(2)."""
    basis = []
    for v in cols:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def inactive_dim(n, w, red, sigma, P, R):
    N = n*w
    Lin, xorsum = lin_factory(n, w, red, sigma, P)
    # column k = concat_{r<R} xorsum(Lin^r e_k)  (R*n bits)
    cols = []
    for k in range(N):
        v = 1 << k
        col = 0
        cur = v
        for r in range(R):
            xs = xorsum(cur)            # n bits
            col |= xs << (r*n)
            cur = Lin(cur)
        cols.append(col)
    rank = gf2_rank(cols)
    return N - rank                      # dim of inactive subspace

def sweep(name, n, w, red, sigma, P, Rmax):
    print(f"== {name} (state {n*w} bit = {w}×{n}) ==")
    Rstar = None
    for R in range(1, Rmax+1):
        d = inactive_dim(n, w, red, sigma, P, R)
        tag = ""
        if d == 0 and Rstar is None:
            Rstar = R; tag = "  <- R* (확률-1 선형 차분 소멸)"
        print(f"  R={R:2d}: dim(inactive subspace) = {d:4d}{tag}")
        if d == 0:
            break
    print(f"  => R* = {Rstar}  (R < {Rstar} 라운드는 확률-1 선형 차분 보유)")
    return Rstar

if __name__ == "__main__":
    # ypsilenti: n=32, w=8, red=0x400007, sigma lanes 0(α¹),4(α³), P_PI
    sweep("ypsilenti perm", 32, 8, 0x400007, [(0,1),(4,3)],
          [7,4,1,6,3,0,5,2], 20)
    print()
    # yhash/ysc4: n=64, w=16, red=0x1B, sigma 0,4,8,12 (α^1,3,5,7), P
    sweep("yhash/ysc4 perm", 64, 16, 0x1B, [(0,1),(4,3),(8,5),(12,7)],
          [7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2], 24)
