#!/usr/bin/env python3
"""
NONLINEAR-INVARIANT search on a small-scale yttrium round, exact spec shape.

Method (Todo-Leander-Wang style):
  A Boolean function g: F2^N -> F2 is a (linear-structure) invariant of round R if
      g(R(x)) = g(x) ^ c     for all x  (fixed c in F2).
  Equivalently g + g∘R is the constant c. For the WHOLE keyed cipher to have a
  nonlinear invariant, g must be invariant under R for EVERY round-key/constant; the
  classic attack needs g invariant for the round WITHOUT the constant (linear part)
  and the constant must lie in the linear space of g.

We search the space of degree<=2 Boolean functions g over the N=n*8 state bits.
The map  T: g  |->  g + g∘R  is LINEAR over F2 on the vector space of all Boolean
functions of degree<=2 (monomials: 1, x_i, x_i x_j). We compute ker of (T restricted
modulo constants) by evaluating g+g∘R at enough sample points and solving a GF(2)
linear system: an invariant (up to additive constant) is g with g(R(x))^g(x) = const.

To keep it exhaustive/exact we use small n and may DROP RC (constant) since the
classic nonlinear-invariant attack first finds constant-free invariants of the
round map, then checks whether round constants stay inside.

We also test the AFFINE round (RC ON) for prob-1 invariant subspaces.
"""
import itertools, random
from inv_yttrium import Yt, EPS, P_PI, SIG_K, F_ROT, RED32

def monomials(N, deg):
    mons=[()]                     # constant 1
    for i in range(N): mons.append((i,))
    if deg>=2:
        for i in range(N):
            for j in range(i+1,N):
                mons.append((i,j))
    return mons

def eval_mon(mon, x):
    r=1
    for b in mon:
        r &= (x>>b)&1
    return r

def state_to_int(st, n):
    v=0
    for i,w in enumerate(st):
        v |= (w & ((1<<n)-1)) << (i*n)
    return v

def int_to_state(v, n):
    M=(1<<n)-1
    return [(v>>(i*n))&M for i in range(8)]

def gf2_solve_kernel(rows, ncols):
    """rows: list of ints (bitmask over ncols). Return basis of kernel of the matrix
       whose ROWS are these vectors, i.e. solve M v = 0 -> nullspace basis."""
    # Build column-reduced; we want nullspace of the rows-as-equations.
    M=[r for r in rows if r]
    # Gaussian elim, track pivots
    pivots={}
    basisrows=[]
    for r in M:
        cur=r
        for p,br in pivots.items():
            if (cur>>p)&1: cur^=br
        if cur:
            p=cur.bit_length()-1
            pivots[p]=cur
    pivcols=set(pivots.keys())
    freecols=[c for c in range(ncols) if c not in pivcols]
    null=[]
    for fc in freecols:
        v=1<<fc
        for p,br in pivots.items():
            if (br>>fc)&1:
                v|=1<<p
        null.append(v)
    return null, pivcols

def search_invariants(yt, n, deg=2, use_rc=True, R=1, nsamples=None):
    N=n*8
    mons=monomials(N,deg)
    nm=len(mons)
    # For each monomial m, vector (g_m + g_m∘R^R) evaluated over sample points.
    # We want g = sum c_m m with (g + g∘R) = const. So for each sample x:
    #   sum_m c_m * (m(x) ^ m(R(x))) = const_bit  (same for all x)
    # Treat const as an extra variable. Equation per sample:
    #   sum_m c_m * d_m(x)  ^  c_const = 0,  where d_m(x)=m(x)^m(R^R(x)).
    # Unknowns: c_m (nm of them) + c_const (1). Each sample gives one row.
    if nsamples is None:
        nsamples = min(1<<N, max(4*nm, 2000))
    rng=random.Random(1234)
    rows=[]
    pts=[]
    if (1<<N) <= 4*nm*4 and N<=22:
        pts=list(range(1<<N))
    else:
        seen=set()
        while len(pts)<nsamples:
            x=rng.randrange(1<<N)
            if x in seen: continue
            seen.add(x); pts.append(x)
    for x in pts:
        st=int_to_state(x,n)
        ry=yt.perm(st,R)
        rx=state_to_int(ry,n)
        row=0
        for idx,m in enumerate(mons):
            d = eval_mon(m,x) ^ eval_mon(m,rx)
            if d: row |= (1<<idx)
        # const variable at bit nm
        # equation: row . c ^ c_const = 0  => include const column
        rows.append(row | (1<<nm))   # const coefficient is always 1 (c_const present in every eq)
        # Wait: c_const appears with coeff 1 in every equation -> column nm set in every row.
    null, piv = gf2_solve_kernel(rows, nm+1)
    # interpret: solutions are c-vectors (c_m..., c_const). Filter trivial:
    #   trivial invariants = constants g=0 or g=1 (c only in const/empty monomial) and
    #   degree<=? We report nontrivial ones (some c_m for |m|>=1 nonzero).
    nontrivial=[]
    for v in null:
        # extract monomial coeffs
        cm=[ (v>>i)&1 for i in range(nm)]
        cconst=(v>>nm)&1
        # nonzero on a non-constant monomial?
        nz=[i for i in range(1,nm) if cm[i]]   # skip mons[0] = constant '1'
        if nz:
            nontrivial.append((cm,cconst,nz))
    return mons, null, nontrivial

if __name__=="__main__":
    print("=== nonlinear-invariant search (deg<=2) on scaled yttrium round ===")
    for n in [2,3]:
        yt=Yt(n, red=(0x7 if n==3 else 0x3), frot=[(1,1),(1,1),(1,1)] if n==2 else [(1,2),(1,2),(1,2)],
              rota=1, rotb=1, sig_k=SIG_K, use_rc=False)
        # NOTE: with use_rc=False we test the constant-free round (classic NLI precondition).
        mons,null,nt = search_invariants(yt, n, deg=2, use_rc=False, R=1)
        N=n*8
        print(f" n={n} N={N}: deg<=2 invariant space dim(incl const)={len(null)}, nontrivial={len(nt)}")
        for cm,cc,nz in nt[:6]:
            terms=[]
            for i in nz:
                m=mons[i]
                terms.append("*".join(f"x{b}" for b in m))
            print(f"   g = {' + '.join(terms)}  (+const={cc})")
