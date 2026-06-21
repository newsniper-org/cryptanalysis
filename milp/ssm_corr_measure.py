#!/usr/bin/env python3
"""
Quantitative SSM linear-distinguisher bound (beyond prob-1):
For each short-period left-invariant w (w^T A^p = w^T), the real-round relation
    w . x_{t+p} XOR w . x_t = XOR_{j=0..p-1} w . (A^{p-1-j} B) F(C x_{t+j})  XOR const
holds.  The number of rounds j in which the coefficient mask  m_j = (w^T A^{p-1-j} B)
is NONZERO is the count of nonlinear F-terms the relation must cross.  Each such
F-contact costs correlation.  We:
  (1) For every left-invariant w (all periods p<=8), count nonzero F-contacts c(w).
      c(w)=0 would be prob-1 (we showed none).  Find MIN c over the invariant space.
  (2) Empirically measure |corr| of the best (min-contact) invariant through the
      real nonlinear round, to see if it beats trail-based resistance.
This is the SSM way to ask: is there a *high-correlation* short linear relation?
"""
import sys, random, math
sys.path.insert(0,"/home/ybi/cryptanalysis/milp")
import ssm_backbone as bb
import ssm_bm_reach as nl

N=256; W=8; MASK32=(1<<32)-1
P_PI=[7,4,1,6,3,0,5,2]; SIG_K=[1,2,3,4,5,6,7,9]; ROT_B=9

def apply_cols(cols,v):
    o=0;j=0
    while v:
        if v&1:o^=cols[j]
        v>>=1;j+=1
    return o
def parity(x): return bin(x).count("1")&1
def left_kernel(colmat):
    rows=[c for c in colmat if c]
    M=list(rows); r=0; pivot_cols=[]
    for col in range(N):
        prow=None
        for i in range(r,len(M)):
            if (M[i]>>col)&1: prow=i;break
        if prow is None: continue
        M[r],M[prow]=M[prow],M[r]
        for i in range(len(M)):
            if i!=r and (M[i]>>col)&1: M[i]^=M[r]
        pivot_cols.append(col); r+=1
        if r==len(M): break
    free=[c for c in range(N) if c not in pivot_cols]
    kb=[]
    for f in free:
        vec=1<<f
        for i,pc in enumerate(pivot_cols):
            if (M[i]>>f)&1: vec|=1<<pc
        kb.append(vec)
    return kb
def B_columns():
    cols=[]
    for jb in range(32):
        tword=1<<jb; out=0
        base=nl.rotr(tword,ROT_B)
        for i in range(W):
            yi=nl.apow(base,SIG_K[i]); inv=P_PI.index(i)
            for b in range(32):
                if (yi>>b)&1: out^=1<<(inv*32+b)
        cols.append(out)
    return cols

if __name__=="__main__":
    A=bb.build_A_columns(); Bc=B_columns()
    # precompute A^T action helper: w^T M  means new mask m where m_p = parity over outputs.
    # w . (M x) = (w^T M) . x ; coefficient mask of x given w and matrix-cols M:
    def wT_times(w, Mcols):
        m=0
        for p in range(N):
            if parity(w & Mcols[p]): m|=1<<p
        return m

    print("== min F-contact count over short-period left-invariants ==")
    for p in [1,2,3,4,6,8]:
        Ap=bb.mat_pow(A,p)
        ApI=[Ap[j]^(1<<j) for j in range(N)]
        inv_basis=left_kernel(ApI)
        if not inv_basis:
            print(f"  p={p}: no invariants"); continue
        # precompute A^{p-1-j} B masks "seen" by w: but contact depends on w. For each basis w,
        # and combos, count rounds with nonzero contact. We scan the basis vectors (and a few combos).
        # contact_j(w) = wT_times(w, A^{p-1-j} B-columns) nonzero?
        Bpows=[]
        Apw=[1<<j for j in range(N)]
        mats=[]
        cur=[1<<j for j in range(N)]
        # need A^{p-1-j} for j=0..p-1 => exponents p-1 .. 0
        powmats={0:[1<<j for j in range(N)]}
        m=[1<<j for j in range(N)]
        for e in range(1,p):
            m=bb.mat_mul(A,m); powmats[e]=m
        def contacts(w):
            c=0
            for j in range(p):
                e=p-1-j
                # masks of A^e B columns seen by w
                hit=False
                for bcol in Bc:
                    col=apply_cols(powmats[e],bcol)
                    if parity(w&col): hit=True;break
                if hit: c+=1
            return c
        # scan basis and pairwise combos
        best=None; bestw=None
        cand=list(inv_basis)
        for i in range(len(inv_basis)):
            for jj in range(i+1,len(inv_basis)):
                cand.append(inv_basis[i]^inv_basis[jj])
        for w in cand[:200]:
            if w==0: continue
            c=contacts(w)
            if best is None or c<best: best=c; bestw=w
        print(f"  p={p}: invariant dim={len(inv_basis)}  MIN F-contacts over scanned = {best} "
              f"(0 would be prob-1; >=1 => corr penalty per contact)")

    # Empirical |corr| of a min-contact period-1 invariant through 1 real round
    print("\n== empirical |corr| of best period-1 invariant over 1 real round ==")
    Ap=bb.mat_pow(A,1); ApI=[Ap[j]^(1<<j) for j in range(N)]
    inv1=left_kernel(ApI)
    random.seed(5)
    for w in inv1[:4]:
        def dot(state):
            v=0
            for i in range(W): v^=parity(((w>>(i*32))&MASK32)&state[i])
            return v
        tot=200000; s=0
        for _ in range(tot):
            st=[random.getrandbits(32) for _ in range(W)]
            a=dot(st); cur,_=nl.round_full(st,0); b=dot(cur)
            s+= 1 if a==b else 0
        corr=abs(2*s/tot-1)
        wc=-math.log2(corr) if corr>0 else float('inf')
        print(f"  w(lanes act={sum(1 for i in range(W) if (w>>(i*32))&MASK32)}): "
              f"P(eq)={s/tot:.4f}  |corr|={corr:.4f} = 2^-{wc:.2f}")
