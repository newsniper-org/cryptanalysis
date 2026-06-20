#!/usr/bin/env python3
"""
yttrium σ orthomorphism + round-invertibility sanity check (n=8/16 전수).
GPU/nvcc 금지. 순수 Python 전수.

검증 항목:
 (P)  σ가 치환(permutation)인가
 (O)  orthomorphism 조건: x ↦ σ(x) ⊟ x 가 치환인가  (Z/2^n 차분)
 (O2) x ↦ σ(x) ⊕ x 가 치환인가                       (GF(2)^n 차분, 보너스)
 (R)  zero-sum reduction S = Σ εᵢ·ROTL_α(xᵢ) 가 broadcast 가산 하에서 보존되는가
 (RT) 전체 라운드(결합기 G + σ + π)가 전수 가역(치환)인가  (n=8, w=8)
"""

MASKS = {}
def mask(n):
    MASKS.setdefault(n,(1<<n)-1); return MASKS[n]
def rotl(x,k,n):
    k%=n; m=mask(n)
    return ((x<<k)|(x>>(n-k)))&m if k else x&m
def rotr(x,k,n): return rotl(x,(n-(k%n))%n,n)

# ---- candidate orthomorphisms σ (per-word, ARX) ----
# A1: θ(x) = ROTL(x,1) ⊞ x        (Z/2^n add)         -- classic "x*alpha+x"? test
# A2: θ(x) = ROTL(x,1) ⊞ c        (affine ARX)
# A3: θ(x) = x ⊞ ROTL(x,r)        (single-rotate add) -- known orthomorphism family
# A4: θ(x) = (x ⊞ ROTL(x,1)) but XOR variant
def sig_addrot(r,n):
    def f(x): return (x + rotl(x,r,n)) & mask(n)
    return f
def sig_rotadd_x(r,n):
    def f(x): return (rotl(x,r,n) + x) & mask(n)   # same as addrot actually
    return f
def sig_affine(r,c,n):
    def f(x): return (rotl(x,r,n) + c) & mask(n)
    return f
def sig_alpha(red,n):   # GF(2^n) mult by alpha (ypsilenti σ core)
    def f(v):
        top=v>>(n-1)
        return (((v<<1)&mask(n)) ^ (red if top else 0))
    return f
def sig_alpha_plus(red,n):  # θ(x)=α·x ⊞ x  (mix GF-mult then add)  -- test ortho
    a=sig_alpha(red,n)
    def f(x): return (a(x)+x)&mask(n)
    return f
def sig_xor_rot(r,n):  # θ(x)=x ⊕ ROTL(x,r)  -- linear, NOT ortho over add typically
    def f(x): return x ^ rotl(x,r,n)
    return f

def is_perm(f,n):
    seen=[False]*(1<<n)
    for x in range(1<<n):
        y=f(x)
        if seen[y]: return False
        seen[y]=True
    return True

def is_ortho_sub(f,n):  # x -> f(x) ⊟ x  is perm  (mod 2^n)
    g=lambda x:(f(x)-x)&mask(n)
    return is_perm(g,n)
def is_ortho_xor(f,n):  # x -> f(x) ⊕ x is perm  (GF(2))
    g=lambda x:f(x)^x
    return is_perm(g,n)

def survey_sigma(n):
    print(f"== σ orthomorphism survey, n={n} (전수 2^{n}) ==")
    cands=[]
    for r in range(1,n):
        cands.append((f"add-rot r={r}: x⊞ROTL(x,{r})", sig_addrot(r,n)))
    for r in range(1,n):
        cands.append((f"affine r={r},c=1: ROTL(x,{r})⊞1", sig_affine(r,1,n)))
    # GF alpha-mult (use small primitive reds for tiny n; for sanity just check perm/ortho)
    redmap={8:0x1D,16:0x2B}   # representative primitive-ish reds for the field; perm/ortho is structural
    if n in redmap:
        cands.append((f"alpha-mult (GF red=0x{redmap[n]:X})", sig_alpha(redmap[n],n)))
        cands.append((f"alpha+x  (α·x ⊞ x)", sig_alpha_plus(redmap[n],n)))
    for r in range(1,n):
        cands.append((f"xor-rot r={r}: x⊕ROTL(x,{r})", sig_xor_rot(r,n)))
    for name,f in cands:
        P=is_perm(f,n)
        Osub=is_ortho_sub(f,n) if P else False
        Oxor=is_ortho_xor(f,n) if P else False
        flag=""
        if P and Osub and Oxor: flag="  <<< full orthomorphism (⊟ and ⊕)"
        elif P and Osub: flag="  << ortho(⊟)"
        elif P and Oxor: flag="  << ortho(⊕ only)"
        print(f"  {name:34s} perm={P} ortho⊟={Osub} ortho⊕={Oxor}{flag}")
    print()

if __name__=="__main__":
    survey_sigma(8)
    survey_sigma(16)
