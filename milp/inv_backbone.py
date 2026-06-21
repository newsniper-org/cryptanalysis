#!/usr/bin/env python3
"""
EXACT GF(2) backbone matrix A of yttrium's linear layer, frozen spec (n=32, 256x256).

Round = x' = ROTL_8(x); [reduce S, F, ARX-add t]; y_i = ROTR_9(x'_i + t); sigma; pi.
The GF(2)-LINEAR backbone (the part independent of t, the only nonlinearity) is
    A = pi o sigma(alpha^k) o ROTR_9 o ROTL_8        (256x256 over GF(2))
acting per-lane: lane i gets value pi-routed; framing ROTL_8 then ROTR_9 then alpha^k.
NOTE: the ARX '+t' is shared additive and the reduction S feeds F; both are folded into
the nonlinear control path  x -> A x  +  B*F(C x).  Here B (broadcast of t through
ROTR_9 then alpha^k then pi) and C (reduction). The MSB-only prob-1 lives where +t acts
linearly (MSB). We analyze A's invariant structure (control-theoretic):
  - char/min poly, order of A
  - fixed space ker(A-I), and A-invariant subspaces via factorization of min poly
  - reachability of the F-injection image B and observability via C (over GF(2)).
"""
import numpy as np
from inv_yttrium import SIG_K, P_PI, ROT_A, ROT_B, RED32

N_BITS=32

def alpha_mat(n, red):
    """Multiplication-by-x (alpha) as n x n GF(2) matrix over column vectors (bit i = x^i coeff)."""
    M=np.zeros((n,n),dtype=np.uint8)
    full=(1<<n)-1
    for j in range(n):
        v=1<<j
        top=(v>>(n-1))&1
        nv=((v<<1)&full)^(red if top else 0)
        for i in range(n):
            M[i,j]=(nv>>i)&1
    return M

def matpow(M,k):
    n=M.shape[0]
    R=np.eye(n,dtype=np.uint8)
    base=M.copy()
    while k:
        if k&1: R=(R@base)%2
        base=(base@base)%2; k>>=1
    return R.astype(np.uint8)

def rot_mat(n, left, k):
    """ROTL_k (left=True) or ROTR_k as n x n permutation matrix on bits."""
    M=np.zeros((n,n),dtype=np.uint8)
    for j in range(n):
        # bit j -> bit (j+k) mod n  for ROTL
        dst=(j+k)%n if left else (j-k)%n
        M[dst,j]=1
    return M

def build_A(n=N_BITS, red=RED32, sig_k=SIG_K, P=P_PI, rota=ROT_A, rotb=ROT_B):
    """Full N x N (N=8n) backbone. Per-lane linear op L_lane = alpha^{k}·ROTR_rotb·ROTL_rota.
       Then pi: out lane i sourced from in lane P[i]."""
    A=alpha_mat(n,red)
    L=rot_mat(n,True,rota)      # ROTL_a
    R=rot_mat(n,False,rotb)     # ROTR_b
    Nn=8*n
    Big=np.zeros((Nn,Nn),dtype=np.uint8)
    for outlane in range(8):
        src=P[outlane]
        ak=matpow(A,sig_k[src]%((1<<n)-1) if False else sig_k[src])
        # per-lane: value v_src -> alpha^{k_src}( ROTR_b( ROTL_a( v_src ) ) )
        Llane=(ak @ ((R @ L)%2))%2
        Big[outlane*n:(outlane+1)*n, src*n:(src+1)*n]=Llane
    return Big.astype(np.uint8)

# ---------- GF(2) linear algebra ----------
def gf2_rank(M):
    A=[int(''.join(map(str,row)),2) for row in M.tolist()]
    basis=[]
    for v in A:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def order_of(A, cap=200000):
    n=A.shape[0]
    I=np.eye(n,dtype=np.uint8)
    cur=A.copy(); t=1
    while t<=cap:
        if np.array_equal(cur,I): return t
        cur=(cur@A)%2; t+=1
    return None

def min_poly_order_via_vector(A, cap=None):
    """Order of A = lcm of invariant-factor orders. We compute order by the structure:
       smallest t with A^t = I. Use the fact A is invertible (perm of bits composed w/ alpha
       invertible). We find order by factoring (2^n-1)*small via trial: since alpha has order
       2^n-1, and rotations have order dividing n, and pi has order dividing 8."""
    return order_of(A, cap=cap or 200000)

if __name__=="__main__":
    A=build_A()
    N=A.shape[0]
    print(f"=== exact backbone A: {N}x{N} GF(2), frozen spec (k={SIG_K}, red={hex(RED32)}, a={ROT_A} b={ROT_B}, P={P_PI}) ===")
    # invertible?
    print("rank(A) =", gf2_rank(A), f"(invertible iff {N})")
    # fixed space ker(A-I)
    AmI=(A^np.eye(N,dtype=np.uint8))
    print("dim ker(A - I) [fixed space, eigenvalue 1] =", N-gf2_rank(AmI))
    # A^2 - I etc: low-period invariant vectors
    for p in [2,3,4,5,6,7,8,16,24]:
        Ap=matpow(A,p)
        d=N-gf2_rank((Ap^np.eye(N,dtype=np.uint8)))
        if d>0:
            print(f"  dim ker(A^{p} - I) = {d}  (period-{p} invariant vectors)")
