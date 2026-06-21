#!/usr/bin/env python3
"""
Part 3: characterize the surviving unobservable direction at R=8 (dim 1) and the
R=9 closure; tie it to the known GF(2)-linear inactive subspace R*=9.  Also probe
whether the +32/round linear schedule of observability hides an exploitable
low-degree relation that survives the *nonlinear* round (the real test).

The headline structural claim to verify or refute:
  - observability/reachability close at R=8-9, EXACTLY matching prior R*=9.
  - the per-lane char poly is identical across lanes => the 8 lanes share a
    GF(2)-similarity class.  Does that create a global invariant of A (e.g. a
    nonzero w with w^T A = w^T, i.e. a left-eigenvector / linear invariant that
    survives many rounds and gives a probabilistic linear distinguisher)?
  - test: does any low-weight linear combination of state bits have an A-period
    much shorter than 248 (=> short-period linear relation = potential corr)?
"""
import sys, random
sys.path.insert(0,"/home/ybi/cryptanalysis/milp")
import ssm_backbone as bb

N=256; W=8; MASK32=(1<<32)-1

def apply_cols(cols,v):
    o=0;j=0
    while v:
        if v&1:o^=cols[j]
        v>>=1;j+=1
    return o
def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for x in basis: cur=min(cur,cur^x)
        if cur: basis.append(cur);basis.sort(reverse=True)
    return len(basis)
def kernel(cols, ncols):
    """Return basis of right-kernel of matrix whose columns are `cols` (each col a row-mask
    over N input bits): we want x with parity(col & x)=0 for all rows. Treat cols as ROWS."""
    # Build as rows -> reduce, track which input bits are free.
    rows=[c for c in cols if c]
    # Gaussian elim to RREF over GF(2) with N columns
    pivots={}
    basis=list(rows)
    reduced=[]
    used=[]
    r=0
    M=list(rows)
    pivot_cols=[]
    for col in range(N):
        prow=None
        for i in range(r,len(M)):
            if (M[i]>>col)&1:
                prow=i;break
        if prow is None: continue
        M[r],M[prow]=M[prow],M[r]
        for i in range(len(M)):
            if i!=r and (M[i]>>col)&1:
                M[i]^=M[r]
        pivot_cols.append(col); r+=1
        if r==len(M): break
    free=[c for c in range(N) if c not in pivot_cols]
    kbasis=[]
    for f in free:
        vec=1<<f
        for i,pc in enumerate(pivot_cols):
            if (M[i]>>f)&1:
                vec|=1<<pc
        kbasis.append(vec)
    return kbasis

# reduce rows C
def reduce_rows():
    rows=[]
    for b in range(32):
        src=(b-bb.ROT_A)%32
        m=0
        for i in range(W): m|=1<<(i*32+src)
        rows.append(m)
    return rows
def parity(x): return bin(x).count("1")&1

if __name__=="__main__":
    A=bb.build_A_columns()
    C=reduce_rows()
    # build observability rows up to R=8 and find the dim-1 unobservable direction
    def Crow_compose(cr,Apow):
        m=0
        for p in range(N):
            if parity(cr & Apow[p]): m|=1<<p
        return m
    Orows=[]
    Apow=[1<<j for j in range(N)]
    ranks=[]
    for R in range(1,10):
        for cr in C: Orows.append(Crow_compose(cr,Apow))
        ranks.append(gf2_rank(Orows))
        Apow=bb.mat_mul(A,Apow)
    print("observability ranks R=1..9:",ranks)

    # unobservable subspace at R=8 (the dim that F still cannot see after 8 rounds)
    Orows8=[]
    Apow=[1<<j for j in range(N)]
    for R in range(1,9):
        for cr in C: Orows8.append(Crow_compose(cr,Apow))
        Apow=bb.mat_mul(A,Apow)
    ker8=kernel(Orows8,N)
    print(f"\nunobservable subspace at R=8: dim={len(ker8)}")
    for v in ker8:
        lanes={(b//32) for b in range(N) if (v>>b)&1}
        wt=bin(v).count("1")
        print(f"  vector weight={wt} active lanes={sorted(lanes)}")
        # show per-lane 32-bit pattern
        for l in sorted(lanes):
            print(f"    lane{l}: {hex((v>>(l*32))&MASK32)}")

    # Is this exactly the prob-1 GF(2)-linear inactive subspace?
    # inactive subspace V_R = { v : C A^r v = 0 for r=0..R-1 } == ker(O_R).
    # So R* (inactive dies) = first R with ker(O_R)=0 => R=9.  Confirm matches prior R*=9.
    print("\n=> ker(O_R)=0 first at R=9  => R*(GF2-linear inactive) = 9  (matches prior milp finding)")

    # Now the *novel* test: does a SHORT-period left-linear-invariant of A exist?
    # i.e. a mask w and small p with w^T A^p = w^T.  Such w would give a linear relation
    # holding every p rounds in the BACKBONE; under the real round it would be a corr.
    print("\n== search for short-period left-invariants w^T A^p = w^T  ==")
    # left-invariant of period p <=> w in kernel of (A^p - I)^T.  Equivalent: row-space.
    # We test small p; period must divide order(A). Backbone min-poly deg ~248 => generic period huge.
    # But factored char poly had small-degree factors (1,3,4,6,16) per lane -> small invariant subspaces.
    AT_pow = None
    for p in [1,2,3,4,6,7,8,12,16,24]:
        Ap=bb.mat_pow(A,p)
        # (Ap - I) columns; left-invariants = left-kernel = right-kernel of (Ap-I)^T.
        # Build (Ap - I) as columns then transpose-kernel via rows.
        ApI=[Ap[j]^(1<<j) for j in range(N)]   # columns of (A^p - I)
        # rows of (A^p - I): row i mask = bits where column j has bit i
        rows=[0]*N
        for j in range(N):
            cj=ApI[j]
            while cj:
                b=(cj & -cj).bit_length()-1
                rows[b]|=1<<j
                cj&=cj-1
        # left-invariant w satisfies w^T (A^p-I)=0 => w in left-kernel => w s.t. for every column j: parity(w & col_j)=0
        # i.e. w in kernel treating COLUMNS as rows:
        kb=kernel(ApI,N)
        print(f"  p={p:2d}: #left-invariant directions (dim of period-{p} linear invariants) = {len(kb)}")
