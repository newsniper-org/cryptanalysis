#!/usr/bin/env python3
"""
Verify EXACTLY (not sampled) whether the candidate "S-inactive" diffs at n=16 are
genuinely probability-1, or just high-probability artifacts of 1200-sample testing.

For round-1 S-inactivity of an ADDITIVE diff D:
   ΔS = sum_i eps_i [ ROTL_a(x_i ⊞ D_i) - ROTL_a(x_i) ]   (mod 2^n)
We need ΔS = 0 for ALL x. Per-lane the term g_i(x_i) = ROTL_a(x_i ⊞ D_i) - ROTL_a(x_i)
depends only on x_i, so we can EXHAUSTIVELY check each lane (2^n values) and see whether
the multiset of per-lane contributions sums to 0 for every combination -> only possible
if each lane's contribution is CONSTANT (x-independent). So: is g_i(x_i) constant in x_i?
That's an exact, cheap, per-lane 2^n check.

Then for the SUM to be identically 0: sum_i eps_i * c_i = 0 where c_i is the (constant)
per-lane contribution. If any g_i is NON-constant, ΔS is x-dependent => NOT prob-1.

This is the rigorous version of the MSB-lemma generalized to arbitrary D_i.
"""
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    return m,rotl

def lane_contrib_constant(n,a_rot,Di):
    """is ROTL_a(x ⊞ Di) - ROTL_a(x) constant over all x? return (is_const, value_or_set)."""
    m,rotl=mk(n)
    vals=set()
    for x in range(1<<n):
        g=(rotl((x+Di)&m,a_rot)-rotl(x,a_rot))&m
        vals.add(g)
        if len(vals)>1 and (1<<n)>1024 and len(vals)>4:
            # short-circuit large n once clearly non-constant
            return False, vals
    return (len(vals)==1), vals

def check_diff_prob1(n,a_rot,eps,D):
    """exact: is ΔS=0 prob-1 for additive diff D in round-1 reduction?"""
    m=(1<<n)-1
    contribs=[]
    for i,Di in enumerate(D):
        isc,vals=lane_contrib_constant(n,a_rot,Di)
        if not isc:
            return False, f"lane {i} Di={Di:x} non-constant contribution ({len(vals)} distinct) -> NOT prob-1"
        contribs.append((eps[i]*next(iter(vals)))%(1<<n))
    total=sum(contribs)%(1<<n)
    return (total==0), f"sum eps*c = {total:x} (0 => prob-1 inactive)"

if __name__=="__main__":
    n=16; a_rot=5; eps=[1,-1,1,-1,1,-1,1,-1]
    print(f"=== EXACT per-lane check, n={n}, a={a_rot} ===")
    # candidates flagged by sampling as 'S-inactive':
    samples_flagged=[
        {0:1,5:1}, {2:2,3:2}, {2:1,5:1}, {4:1,5:1}, {4:1,7:1}, {4:2,7:2},
        {1:1,2:1}, {3:2,6:2},
    ]
    for fl in samples_flagged:
        D=[0]*8
        for ln,v in fl.items(): D[ln]=v
        ok,msg=check_diff_prob1(n,a_rot,eps,D)
        print(f"  D={ {k:('%x'%v) for k,v in fl.items()} }: prob1={ok}  [{msg}]")

    print("\n=== MSB-pre reference (the proposal's acknowledged class) ===")
    m,rotl=mk(n)
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    msb_pre=rotr(1<<(n-1),a_rot)
    for pair in [(0,2),(0,4),(2,6)]:
        D=[0]*8; D[pair[0]]=msb_pre; D[pair[1]]=msb_pre
        ok,msg=check_diff_prob1(n,a_rot,eps,D)
        print(f"  MSBpre pair{pair} (msb_pre={msb_pre:x}): prob1={ok} [{msg}]")

    # is the sampling result a FALSE POSITIVE? exhaustively confirm one flagged diff
    print("\n=== brute reality check on D={0:1,5:1}: count ΔS!=0 over many x via full round-1 reduction ===")
    import random
    random.seed(5)
    def Sred(state):
        u=[rotl(state[i],a_rot) for i in range(8)]; S=0
        for i in range(8): S=(S+eps[i]*u[i])%(1<<n)
        return S
    D=[0]*8; D[0]=1; D[5]=1
    nz=0; N=200000
    for _ in range(N):
        x=tuple(random.randint(0,(1<<n)-1) for _ in range(8))
        x2=tuple((x[i]+D[i])&((1<<n)-1) for i in range(8))
        if (Sred(x)-Sred(x2))%(1<<n)!=0: nz+=1
    print(f"  D={{0:1,5:1}}: ΔS!=0 in {nz}/{N} random x  (0 => truly prob-1; >0 => sampling false-positive)")
