#!/usr/bin/env python3
"""
Investigate the dim-2 fixed space ker(A-I) of the EXACT backbone and the low-period
invariant subspaces. Then test whether these are (a) prob-1 invariant DIFFERENCES of the
FULL (nonlinear, RC-on) round, or (b) merely linear-backbone artifacts killed by F/carry.

A fixed vector v of A satisfies A v = v. As a DIFFERENCE, the round maps
   Delta -> A Delta  XOR  [F-path difference]
The F-path difference vanishes iff the reduction difference DeltaS = 0 AND the shared +t
addition does not mix Delta (true at prob 1 only on MSBs, since add=xor on MSB).
So a fixed vector that is *also MSB-only* and *zero-sum under the reduction* is a
candidate prob-1 invariant difference. We check exactly.
"""
import numpy as np
from inv_backbone import build_A, gf2_rank

from inv_yttrium import yt32, EPS

def nullspace_basis(M):
    """Basis of right-nullspace of GF(2) matrix M (cols)."""
    m,n=M.shape
    rows=[int(''.join(map(str,M[i].tolist())),2) for i in range(m)]
    # gaussian elim with pivot tracking on columns
    pivots={}
    for r in rows:
        cur=r
        for p,br in pivots.items():
            if (cur>>(n-1-p))&1: cur^=br
        if cur:
            # leading col
            p=n-1-(cur.bit_length()-1)
            pivots[p]=cur
    pivcols=set(pivots.keys())
    free=[c for c in range(n) if c not in pivcols]
    basis=[]
    for fc in free:
        vec=[0]*n; vec[fc]=1
        for p,br in pivots.items():
            if (br>>(n-1-fc))&1: vec[p]=1
        basis.append(vec)
    return basis

def vec_to_state(vec, n=32):
    return [sum(vec[i*n+j]<<j for j in range(n)) for i in range(8)]

def hw_state(st): return sum(bin(w).count('1') for w in st)

if __name__=="__main__":
    A=build_A(); N=A.shape[0]
    AmI=(A^np.eye(N,dtype=np.uint8))
    nb=nullspace_basis(AmI)
    print(f"fixed space ker(A-I): dim={len(nb)}")
    yt=yt32()
    for bi,vec in enumerate(nb):
        st=vec_to_state(vec)
        print(f"\n fixed vector #{bi}: state words = {[hex(w) for w in st]}  HW={hw_state(st)}")
        # is it MSB-only?
        msb_only = all((w & 0x7fffffff)==0 for w in st)
        print(f"   MSB-only? {msb_only}")
        # zero-sum under reduction of x' = ROTL_8(delta)? reduction sign-sum of x'_i
        xp=[yt.rotl(w,yt.rota) for w in st]
        # DeltaS over GF(2)/additive: for a difference, S diff = sum eps_i xp_i mod 2^32
        ds=0
        for i in range(8):
            if EPS[i]>0: ds=(ds+xp[i])&0xffffffff
            else: ds=(ds-xp[i])&0xffffffff
        print(f"   reduction-diff DeltaS (additive) = {hex(ds)}")
        # TEST as prob-1 difference of the FULL round over random x
        import random
        rng=random.Random(2024)
        outdiffs=set(); R=1
        for _ in range(20000):
            x=[rng.randrange(1<<32) for _ in range(8)]
            xd=[x[i]^st[i] for i in range(8)]
            ox=yt.perm(x,R); oxd=yt.perm(xd,R)
            od=tuple(ox[i]^oxd[i] for i in range(8))
            outdiffs.add(od)
            if len(outdiffs)>3: break
        prob1 = (len(outdiffs)==1)
        print(f"   prob-1 difference of FULL round (R=1)? {prob1}  (#distinct out-diffs seen={len(outdiffs)})")
        if prob1:
            od=next(iter(outdiffs))
            # is out-diff == A*delta (i.e. linear-consistent) and does the SUBSPACE iterate?
            print(f"     out-diff = {[hex(w) for w in od]}")
