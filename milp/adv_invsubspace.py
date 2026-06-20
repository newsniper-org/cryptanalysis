#!/usr/bin/env python3
"""
Adversarial: invariant subspace under the LINEAR layer L = pi o sigma (the part that is
GF(2)-linear). Amaryllises is known to have diagonal invariant subspaces (ePrint 2022/1245
sec 7.2). The proposal's defense is 'distinct-mu' but here sigma only uses lanes {0,2,4,6}
with k=1,3,5,7 and the OTHER 4 lanes are IDENTITY. An invariant subspace of L that the
reduction S also kills (or that survives RC) would be a real weakness.

Build L over GF(2) as a (n*w) x (n*w) bit-matrix and find its invariant subspaces of small
dimension, and specifically: is the subspace {lanes 1,3,5,7 arbitrary, lanes 0,2,4,6 = 0}
or similar mapped into itself? Also compute the order of L and any low-degree invariant
factors.
"""
import random

def make_alpha_mat(n,red):
    # alpha as multiplication-by-x matrix over GF(2), n x n, acting on column vector (bit i = coeff x^i)
    # alpha(v): newbit = shift left by 1, if top set xor red.
    # represent state bit j (value's bit j). a(v)_bit: standard companion.
    M=[[0]*n for _ in range(n)]
    for j in range(n):
        v=1<<j
        top=(v>>(n-1))&1
        nv=((v<<1)&((1<<n)-1))^(red if top else 0)
        for i in range(n):
            M[i][j]=(nv>>i)&1
    return M

def matpow_gf2(M,k,n):
    # result = M^k
    R=[[1 if i==j else 0 for j in range(n)] for i in range(n)]
    base=[row[:] for row in M]
    while k:
        if k&1: R=matmul(R,base,n)
        base=matmul(base,base,n); k>>=1
    return R

def matmul(A,B,n):
    C=[[0]*n for _ in range(n)]
    for i in range(n):
        Ai=A[i]
        for kk in range(n):
            if Ai[kk]:
                Bk=B[kk]
                Ci=C[i]
                for j in range(n):
                    Ci[j]^=Bk[j]
    return C

def build_L(n,w,red,sigma,P):
    """Big matrix L (N x N), N=n*w, of L = pi o sigma over GF(2). lane lin block = alpha^k or I."""
    N=n*w
    A=make_alpha_mat(n,red)
    apows={}
    # sigma applies alpha^k to lane ln, then pi: new_lane i = old_lane P[i].
    blocks={}  # blocks[ln] = matrix applied to lane ln before pi
    I=[[1 if i==j else 0 for j in range(n)] for i in range(n)]
    for ln in range(w): blocks[ln]=[row[:] for row in I]
    for (ln,k) in sigma:
        blocks[ln]=matpow_gf2(A,k,n)
    # L maps full vector: output lane i (bits) = blocks[P[i]] applied to input lane P[i]
    L=[[0]*N for _ in range(N)]
    for i in range(w):
        src=P[i]
        B=blocks[src]
        for r in range(n):
            for c in range(n):
                L[i*n+r][src*n+c]=B[r][c]
    return L

def order_of_L(L,N,cap=200000):
    # find smallest t with L^t = I (on whole space) by repeated squaring search is hard; just iterate
    I=[[1 if i==j else 0 for j in range(N)] for j2 in range(N)] if False else None
    cur=[row[:] for row in L]
    t=1
    def is_I(M):
        for i in range(N):
            for j in range(N):
                if M[i][j]!=(1 if i==j else 0): return False
        return True
    while t<cap:
        if is_I(cur): return t
        cur=matmul(cur,L,N); t+=1
    return None

def invariant_subspace_dim(L,N):
    """Dimension of largest L-invariant subspace fixed pointwise? Instead compute fixed space
       (eigenvalue 1): ker(L - I) over GF(2)."""
    # M = L - I = L + I (gf2)
    M=[[(L[i][j]^(1 if i==j else 0)) for j in range(N)] for i in range(N)]
    return N-gf2_rank_rows(M,N)

def gf2_rank_rows(M,N):
    rows=[0]*N
    for i in range(N):
        v=0
        for j in range(N):
            if M[i][j]: v|=1<<j
        rows[i]=v
    basis=[]
    for v in rows:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

if __name__=="__main__":
    SIG=[(0,1),(2,3),(4,5),(6,7)]
    PPI=[7,4,1,6,3,0,5,2]
    print("=== L=pi o sigma invariant/fixed-space (eigenvalue-1) dimension ===")
    for n,red in [(8,0x1D),(16,0x2B)]:
        L=build_L(n,8,red,SIG,PPI)
        N=n*8
        fixdim=invariant_subspace_dim(L,N)
        print(f"  n={n} red={hex(red)} N={N}: dim(fixed space, eig=1) = {fixdim}")
        # order of L
        # cap small to avoid huge runtime; only n=8
        if n==8:
            print("    (computing order of L, may take a moment)")
            o=order_of_L(L,N,cap=2000)
            print(f"    order(L) within cap2000 = {o}")
