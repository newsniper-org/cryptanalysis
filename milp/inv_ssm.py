#!/usr/bin/env python3
"""
SSM control-theory analysis of yttrium's GF(2) backbone.

State recursion (difference / linear backbone form):
    x_{t+1} = A x_t  (+ B f_t)        f_t = F-injection (the only nonlinearity), scalar->state
    'observed' via C = reduction (what F sees).
Control-theory tools over GF(2):
  - Reachability of the F-injection: R = [B, AB, A^2 B, ...]; if rank(R) < N there is an
    A-invariant subspace UNREACHABLE by F  => a difference there is never 'repaired' by F
    => potential invariant subspace (structural weakness IF it also dodges F's observation).
  - Observability of the reduction: O = [C; C A; C A^2; ...]; ker(O) = states invisible to F
    across all rounds => differences there pass F inactive forever (this is exactly the
    GF(2)-linear inactive subspace, R* = first R with dim ker(O_R)=0).
  - Intersection: a difference in ker(O) ∩ (A-invariant) that B cannot reach is a genuine
    invariant subspace of the linearized cipher.

We build B and C as GF(2)-linear approximations:
  C: the reduction S = sum eps_i ROTL_8(x_i). As a GF(2) MAP this is NOT linear (carries),
     but its TOP-bit (MSB) and its XOR-projection are linear proxies. We use the standard
     XOR-sum proxy AND the exact MSB proxy, matching the two measures in yttrium-lm-results.
  B: t enters every lane as ROTR_9(.+t) then alpha^k then pi. The shared broadcast of a
     scalar t into 8 lanes (each lane same t pre-ARX) gives B = column-broadcast through
     the linear post-ops.
"""
import numpy as np
from inv_backbone import build_A, gf2_rank, matpow, rot_mat, alpha_mat
from inv_yttrium import SIG_K, P_PI, ROT_A, ROT_B, RED32, EPS

N=256; n=32

def order_of_A_fast(A, n=32):
    """order(A) divides lcm over invariant factors. We bound by checking A^t=I for t over
       divisor candidates of (2^n-1)*lcm(rotation orders, 8). Use repeated squaring tests."""
    I=np.eye(A.shape[0],dtype=np.uint8)
    # candidate: order divides ord(alpha)=2^32-1 composed structure; just test a set of
    # multiplicatively-built exponents to find the true order via factor of 2^32-1.
    # 2^32-1 = 3*5*17*257*65537. Test products.
    base=2**32-1
    facs=[3,5,17,257,65537]
    # also rotation/pi periods: lcm could multiply by small numbers; test t in {base*m} small m
    # First check if A^base == I
    def powI(e): return np.array_equal(matpow(A,e),I)
    res={}
    res['A^(2^32-1)==I']=powI(base)
    res['A^8==I']=powI(8)
    res['A^(8*(2^32-1))==I']=powI(8*base)
    res['A^(2^32-1)//... ']=None
    return res

def C_xorsum(n=32):
    """XOR-sum proxy reduction: S_bit = XOR over lanes of ROTL_8(x_i)_bit. n x N matrix."""
    L=rot_mat(n,True,ROT_A)
    C=np.zeros((n,8*n),dtype=np.uint8)
    for lane in range(8):
        C[:,lane*n:(lane+1)*n]=L   # XOR of all lanes (eps ignored in GF(2): -1==+1)
    return C%2

def C_msb(n=32):
    """Exact prob-1 MSB proxy: only the MSB sign-sum is linear-prob-1. 1 x N row =
       XOR of MSBs of ROTL_8(x_i) = XOR of bit (msb-ROT_A) of x_i."""
    C=np.zeros((1,8*n),dtype=np.uint8)
    src_bit=(n-1-ROT_A)%n  # ROTL_8 sends bit src_bit -> MSB
    for lane in range(8):
        C[0,lane*n+src_bit]=1
    return C

def observability_Rstar(A,C,Rmax=14):
    """First R with dim ker(O_R)=0, O_R=[C;CA;...;CA^{R-1}]. Returns dims per R and R*."""
    rows=[]
    cur=C.copy()
    dims=[]
    Rstar=None
    for R in range(1,Rmax+1):
        rows.append(cur.copy())
        O=np.vstack(rows)%2
        r=gf2_rank(O)
        d=A.shape[0]-r
        dims.append((R,d))
        if d==0 and Rstar is None: Rstar=R
        cur=(cur@A)%2
    return dims, Rstar

def B_broadcast(n=32):
    """t enters: y_i = ROTR_9(x'_i + t); difference path of t into lane i is ROTR_9 applied
       to t (the +t adds t to each lane pre-ROTR), then alpha^{k_i}, then pi routes.
       The F-injection image B (N x n): column space = where a scalar Delta-t lands."""
    A_a=alpha_mat(n,RED32)
    R=rot_mat(n,False,ROT_B)
    B=np.zeros((8*n,n),dtype=np.uint8)
    for outlane in range(8):
        src=P_PI[outlane]
        ak=matpow(A_a, SIG_K[src])
        Lpost=(ak@R)%2          # alpha^{k_src} o ROTR_9  applied to t
        B[outlane*n:(outlane+1)*n, :]=Lpost
    return B%2

def reachability(A,B):
    """rank of [B,AB,A^2B,...] until saturates."""
    cols=B.copy()
    blocks=[B.copy()]
    cur=B.copy()
    prev=-1
    for _ in range(20):
        Rmat=np.hstack(blocks)%2
        r=gf2_rank(Rmat.T)  # rank counts independent columns
        if r==prev: break
        prev=r
        cur=(A@cur)%2
        blocks.append(cur.copy())
    return prev

if __name__=="__main__":
    A=build_A()
    print("=== SSM analysis of exact backbone A (256x256) ===")
    print("\n[order of A]")
    for k,v in order_of_A_fast(A).items():
        if v is not None: print(f"  {k}: {v}")

    print("\n[Observability of F's reduction-input over rounds]  (= GF(2)-linear inactive subspace)")
    Cx=C_xorsum(); dims,Rs=observability_Rstar(A,Cx,Rmax=14)
    print("  XOR-sum proxy:")
    for R,d in dims: print(f"    R={R:2d}: dim ker(O_R)={d}")
    print(f"    => GF(2)-linear inactive R* = {Rs}")
    Cm=C_msb(); dims2,Rs2=observability_Rstar(A,Cm,Rmax=14)
    print("  MSB proxy:")
    for R,d in dims2: print(f"    R={R:2d}: dim ker(O_R)={d}")
    print(f"    => MSB-linear inactive R* = {Rs2}")

    print("\n[Reachability of F-injection B]")
    B=B_broadcast()
    rk=reachability(A,B)
    print(f"  rank[B,AB,...] = {rk} of {N}  (=> unreachable-by-F invariant subspace dim {N-rk})")
