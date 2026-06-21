#!/usr/bin/env python3
"""
DECISIVE test: do the short-period left-invariants of the backbone A give a
PROB-1 (or high-corr) linear approximation through the *real nonlinear* round?

A left-invariant w with w^T A^p = w^T means, in the linear backbone,
    w . x_{t+p} = w . x_t   (always).
Under the real round, x_{t+1} = A x_t XOR B*F(C x_t) XOR rc_t.  So
    w . x_{t+1} = w.(A x_t) XOR w.(B F(C x_t)) XOR w.rc_t
For w to give a deterministic linear relation we need w.(B F(.)) to vanish, i.e.
    w must be ORTHOGONAL to the injection image B  (and to A^j B for the p-step).
If w^T A^p = w^T AND w^T A^j B = 0 for j=0..p-1, then over p rounds:
    w . x_{t+p} = w . x_t  XOR  (constant from RC)        -- holds with PROBABILITY 1.
That is a prob-1 linear distinguisher with period p => devastating if it exists.

We compute, for each period p, the subspace of left-invariants, intersect with
the F-blind condition, and report the dimension.  dim>0 at small p = real break.
Then we EMPIRICALLY verify any survivor on the full nonlinear permute.
"""
import sys, random
sys.path.insert(0,"/home/ybi/cryptanalysis/milp")
import ssm_backbone as bb
import ssm_bm_reach as nl   # reuse round_full, B_columns

N=256; W=8; MASK32=(1<<32)-1
P_PI=[7,4,1,6,3,0,5,2]; SIG_K=[1,2,3,4,5,6,7,9]; ROT_B=9

def apply_cols(cols,v):
    o=0;j=0
    while v:
        if v&1:o^=cols[j]
        v>>=1;j+=1
    return o
def parity(x): return bin(x).count("1")&1
def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for x in basis: cur=min(cur,cur^x)
        if cur: basis.append(cur);basis.sort(reverse=True)
    return len(basis)

def left_kernel(colmat):
    """w s.t. for every column c in colmat: parity(w & c)=0.  Return basis (list of ints)."""
    # treat columns as constraints (rows of the constraint matrix indexed by input-bit positions of w)
    # Constraint: sum_b w_b * c_b = 0.  So each column c is a linear form on w.
    # Solve: kernel of the matrix whose ROWS are the columns c.
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
    A=bb.build_A_columns()
    Bc=B_columns()
    print("== F-blind short-period left-invariants (PROB-1 linear relation candidates) ==")
    print("w^T A^p = w^T  AND  w^T A^j B = 0  for j=0..p-1   => prob-1 over p rounds\n")
    for p in [1,2,3,4,6,7,8,12,16,24]:
        Ap=bb.mat_pow(A,p)
        ApI=[Ap[j]^(1<<j) for j in range(N)]          # columns of (A^p - I)
        inv_basis=left_kernel(ApI)                      # w^T A^p = w^T
        # now impose F-blind: w . (A^j B col) = 0 for all j<p, all B columns
        constraints=list(ApI)  # already enforced via basis; rebuild full system:
        cons=[]
        Apow=[1<<j for j in range(N)]
        for j in range(p):
            for bcol in Bc:
                cons.append(apply_cols(Apow,bcol))
            Apow=bb.mat_mul(A,Apow)
        # full system: w must satisfy (A^p-I) and all F-blind constraints
        full=ApI+cons
        fblind=left_kernel(full)
        print(f"  p={p:2d}: left-invariants dim={len(inv_basis):2d} | F-blind survivors dim={len(fblind)}")
        survivors_p = (fblind, p) if len(fblind)>0 else None
        if fblind:
            # EMPIRICAL verify on full nonlinear permute
            w=fblind[0]
            random.seed(123)
            ok=0; tot=2000
            for _ in range(tot):
                st=[random.getrandbits(32) for _ in range(W)]
                def dot(state):
                    val=0
                    for i in range(W): val^=parity(((w>>(i*32))&MASK32)&state[i])
                    return val
                a=dot(st)
                cur=list(st)
                for r in range(p):
                    cur,_=nl.round_full(cur,r)
                b=dot(cur)
                if a==b: ok+=1
            print(f"        EMPIRICAL prob(w.x_p == w.x_0) over real round = {ok}/{tot} = {ok/tot:.4f}")

    print("\n(If all F-blind survivor dims are 0 for small p: NO prob-1 backbone linear relation")
    print(" survives the nonlinear round -> the F-injection is positioned to break every short")
    print(" linear invariant.  This is the design goal; SSM confirms/refutes it directly.)")
