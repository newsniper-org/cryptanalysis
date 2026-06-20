#!/usr/bin/env python3
"""
진짜 ⊟-orthomorphism (additive Lai-Massey) 광역 탐색, n=8 전수.
known constructions:
  - θ(x)=c·x with c,c-1 both odd (units) over Z/2^n: c·x and (c-1)·x both perms.
    c odd & (c-1) odd impossible (consecutive). BUT (c-1) need only be PERMUTATION of
    x↦θ(x)⊟x = (c-1)x; perm over Z/2^n ⟺ (c-1) odd. c odd too. consecutive ⟹ no. (so linear mult fails — matches survey)
  - θ(x)=x ⊞ (x≪k)?? linear, x↦θ⊟x=(x≪k) NOT perm.
  - Mixed T-function orthomorphisms: θ(x)=x ⊞ g(x) where g raises carries.
  - The classic: over Z/2^n, σ(x)=3x is orthomorphism? σ⊟id=2x not perm. no.
We brute force a broad ARX-expressible family and report any ⊟-ortho.
Also test 'lane-distinct rotation reduction' idea separately (see reduction_distinct.py-like here).
"""
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    return m,rotl
def isperm(f,n):
    seen=bytearray(1<<n)
    for x in range(1<<n):
        y=f(x)&((1<<n)-1)
        if seen[y]: return False
        seen[y]=1
    return True
def search_sub_ortho(n):
    m,rotl=mk(n)
    hits=[]
    # broad family: θ(x) = A(x) where A built from up to 2 ops mixing ⊞,⊕,ROTL,const
    cands={}
    for r in range(0,n):
        for s in range(0,n):
            for c in (0,1,3,5):
                cands[f"((x⊞{c})⊕ROTL{r})⊞ROTL?{s}"]=(lambda r,s,c:(lambda x:((((x+c)&m)^rotl(x,r))+rotl(x,s))&m))(r,s,c)
    for r in range(0,n):
        for c in (1,3,5,7):
            cands[f"ROTL(x,{r})⊞x⊞{c}"]=(lambda r,c:(lambda x:(rotl(x,r)+x+c)&m))(r,c)  # add-rot+x not perm usually
    for r in range(1,n):
        for c in (0,1,3):
            cands[f"(x⊕(x≪{r}via rotl))⊞{c}then⊕x"]=(lambda r,c:(lambda x:(((x^rotl(x,r))+c)&m)^x))(r,c)
    # T-function-ish: theta(x)=x ⊞ ((x ∧ (x≪1)))  (nonlinear carry)
    for k in range(1,n):
        cands[f"x⊞(x∧ROTL{k})"]=(lambda k:(lambda x:(x+(x&rotl(x,k)))&m))(k)
        cands[f"x⊕(x∧ROTL{k})⊞1"]=(lambda k:(lambda x:((x^(x&rotl(x,k)))+1)&m))(k)
    for name,f in cands.items():
        if not isperm(f,n): continue
        sub=isperm(lambda x:(f(x)-x)&m,n)
        xor=isperm(lambda x:(f(x)^x)&m,n)
        if sub:
            hits.append((name,sub,xor))
    print(f"== ⊟-orthomorphism hits, n={n} ==")
    if not hits: print("  (none found in broad ARX family)")
    for name,sub,xor in hits:
        print(f"  {name:34s}  ⊟={sub} ⊕={xor}")
    print()
    return hits
if __name__=="__main__":
    search_sub_ortho(8)
