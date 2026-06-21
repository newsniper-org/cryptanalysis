#!/usr/bin/env python3
"""Validate the deg<=2 invariant search: feed a map with a KNOWN quadratic invariant
   and confirm the search recovers it. Then a map with no invariant (random perm)."""
import random
from inv_search import monomials, eval_mon, gf2_solve_kernel

def search_generic(perm, N, deg=2, nsamples=None):
    mons=monomials(N,deg); nm=len(mons)
    if nsamples is None: nsamples=min(1<<N, max(4*nm,2000))
    pts=list(range(1<<N)) if (1<<N)<=4*nm and N<=20 else None
    if pts is None:
        rng=random.Random(7); seen=set(); pts=[]
        while len(pts)<nsamples:
            x=rng.randrange(1<<N)
            if x in seen: continue
            seen.add(x); pts.append(x)
    rows=[]
    for x in pts:
        rx=perm(x)
        row=0
        for idx,m in enumerate(mons):
            if eval_mon(m,x)^eval_mon(m,rx): row|=1<<idx
        rows.append(row|(1<<nm))
    null,_=gf2_solve_kernel(rows,nm+1)
    nt=[]
    for v in null:
        nz=[i for i in range(1,nm) if (v>>i)&1]
        if nz: nt.append(nz)
    return mons,null,nt

if __name__=="__main__":
    N=8
    # KNOWN invariant: g(x)=x0*x1 ^ x2 ; build perm P with g(P x)=g(x).
    # Simplest: P = identity on bits used by g but permute others -> g invariant.
    # Use P: swap x4<->x5, x6<->x7, leave x0..x3. Then g=x0x1^x2 invariant.
    def perm_known(x):
        b=[(x>>i)&1 for i in range(N)]
        b[4],b[5]=b[5],b[4]; b[6],b[7]=b[7],b[6]
        return sum(bi<<i for i,bi in enumerate(b))
    mons,null,nt=search_generic(perm_known,N,deg=2)
    print(f"[known-invariant perm] nullspace dim={len(null)} nontrivial={len(nt)}")
    found=False
    for nz in nt:
        labs=set()
        for i in nz: labs.add(mons[i])
        if (0,1) in labs and (2,) in labs:
            found=True
    print("  recovered g=x0x1^x2 (and friends)?", "YES" if found else "among "+str(len(nt))+" nontrivial")
    # show a few
    for nz in nt[:5]:
        print("   g=", " + ".join("*".join(f"x{b}" for b in mons[i]) for i in nz))

    # control: a strong nonlinear permutation (AES-like small) should have FEW/no low-deg invariants
    random.seed(99)
    perm_tab=list(range(1<<N)); random.shuffle(perm_tab)
    def perm_rand(x): return perm_tab[x]
    mons2,null2,nt2=search_generic(perm_rand,N,deg=2)
    print(f"[random perm] nullspace dim={len(null2)} nontrivial={len(nt2)} (expect ~0 nontrivial)")
